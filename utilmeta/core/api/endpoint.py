from utilmeta import utils
from utilmeta.utils import exceptions as exc
from typing import Callable, Type, List, TYPE_CHECKING
from utilmeta.utils.plugin import PluginTarget, PluginEvent
from utilmeta.utils.context import ContextWrapper, Property
from utilmeta.utils.exceptions import InvalidDeclaration
from utilmeta.core.response.base import parse_responses
from utype.parser.base import BaseParser
from utype.parser.func import FunctionParser
from utype.parser.field import ParserField
from utype.parser.rule import LogicalType
import inspect
from ..request import Request, var
from ..request.properties import QueryParam, PathParam
from ..response import Response
import utype

if TYPE_CHECKING:
    from .base import API

process_request = PluginEvent("process_request", streamline_result=True)
handle_error = PluginEvent("handle_error")
process_response = PluginEvent("process_response", streamline_result=True)


class RequestContextWrapper(ContextWrapper):
    context_cls = Request
    default_property = QueryParam
    parser: FunctionParser

    def __init__(self, *args, **kwargs):
        self.header_names = []
        super().__init__(*args, **kwargs)
        # used in generate allow headers

    def init_prop(self, prop: Property, val: ParserField):  # noqa, to be inherit
        if prop.__ident__ == "header":
            for origin in val.input_origins:
                parser = getattr(origin, "__parser__", None)
                if isinstance(parser, BaseParser):
                    utils.distinct_add(
                        self.header_names, [str(v).lower() for v in parser.fields]
                    )
        elif prop.__in__ and getattr(prop.__in__, "__ident__", None) == "header":
            name = val.name.lower()
            if name not in self.header_names:
                self.header_names += name
        else:
            headers = getattr(prop, "headers", None)
            if headers and utils.multi(headers):
                utils.distinct_add(self.header_names, [str(v).lower() for v in headers])
        return prop.init(val)

    @classmethod
    def contains_file(cls, field: ParserField):
        def file_like(file_cls):
            from utilmeta.core.file import File
            from io import BytesIO

            if inspect.isclass(file_cls):
                if issubclass(file_cls, (File, BytesIO, bytearray)):
                    return True
            return False

        from utype import Rule

        if isinstance(field.type, type) and issubclass(field.type, Rule):
            # try to find List[schema]
            if (
                isinstance(field.type.__origin__, LogicalType)
                and field.type.__origin__.combinator
            ):
                for arg in field.type.__origin__.args:
                    if file_like(arg):
                        return True
            else:
                if (
                    field.type.__origin__
                    and issubclass(field.type.__origin__, list)
                    and field.type.__args__
                ):
                    # we only accept list, not tuple/set
                    arg = field.type.__args__[0]
                    if file_like(arg):
                        return True
        else:
            # try to find Optional[schema]
            for origin in field.input_origins:
                if file_like(origin):
                    return True

        return False

    def validate_method(self, method: str):
        # 1. only PUT / PATCH / POST allow to have body params
        # 2. File params not allowed in
        allow_body = method.lower() in ["post", "put", "patch"]
        for key, val in self.properties.items():
            field = val.field

            prop = val.prop
            if (
                prop.__ident__ == "body"
                or prop.__in__
                and getattr(prop.__in__, "__ident__", None) == "body"
            ):
                if not allow_body:
                    raise InvalidDeclaration(
                        f"body param: {repr(key)} not supported in method: {repr(method)}"
                    )
            else:
                if self.contains_file(field):
                    raise InvalidDeclaration(
                        f"request param: {repr(key)} used file as type declaration,"
                        f" which is not supported, file must be declared in Body or BodyParam"
                    )


class BaseEndpoint(PluginTarget):
    parser_cls = FunctionParser
    wrapper_cls = RequestContextWrapper

    PATH_REGEX = utils.PATH_REGEX
    PARSE_PARAMS = False
    # params is already parsed by the request parser
    PARSE_RESULT = False
    # result will be parsed in the end of endpoint.serve
    # STRICT_RESULT = False

    def __init__(
        self,
        f: Callable,
        *,
        method: str,
        name: str = None,
        # the attribute name of API/SDK class
        # instead of function name (maybe affected by not-@wrap decorator function)
        plugins: list = None,
        idempotent: bool = None,
        eager: bool = False,
        local_vars: dict = None,
    ):

        super().__init__(plugins=plugins)

        if not inspect.isfunction(f):
            raise TypeError(f"Invalid endpoint function: {f}")

        self.f = f
        self.method = method
        self.idempotent = idempotent
        self.eager = eager
        self.name = self.__name__ = name or f.__name__
        self.path_names = self.PATH_REGEX.findall(self.route)
        self.local_vars = local_vars

        # ---------------
        parser = self.parser_cls.apply_for(f)
        parser.resolve_forward_refs(local_vars=local_vars)
        # resolve even if local_vars is None
        self.wrapper = self.wrapper_cls(
            parser, default_properties=self.default_wrapper_properties
        )
        self.executor = self.parser.wrap(
            eager_parse=self.eager,
            parse_params=self.PARSE_PARAMS,
            parse_result=self.PARSE_RESULT,
        )

        self.sync_wrapper = None
        self.async_wrapper = None
        self.sync_executor = None
        self.async_executor = None

        # -- adapt @awaitable
        if getattr(self.f, "_awaitable", False):
            sync_func = getattr(self.f, "_syncfunc", None)
            async_func = getattr(self.f, "_asyncfunc", None)
            if sync_func:
                self.sync_wrapper = self.wrapper_cls(
                    self.parser_cls.apply_for(sync_func),
                    default_properties=self.default_wrapper_properties,
                )
                self.sync_executor = self.sync_wrapper.parser.wrap(
                    eager_parse=self.eager,
                    parse_params=self.PARSE_PARAMS,
                    parse_result=self.PARSE_RESULT,
                )
            if async_func:
                self.async_wrapper = self.wrapper_cls(
                    self.parser_cls.apply_for(async_func),
                    default_properties=self.default_wrapper_properties,
                )
                self.async_executor = self.async_wrapper.parser.wrap(
                    eager_parse=self.eager,
                    parse_params=self.PARSE_PARAMS,
                    parse_result=self.PARSE_RESULT,
                )

        self.response_types: List[Type[Response]] = parse_responses(self.return_type)
        self.wrapper.validate_method(method)

    @property
    def return_type(self):
        if self.parser.return_type:
            return self.parser.return_type
        if self.sync_wrapper:
            rt = self.sync_wrapper.parser.return_type
            if rt:
                return rt
        if self.async_wrapper:
            rt = self.async_wrapper.parser.return_type
            if rt:
                return rt
        return None

    def get_wrapper(self, asynchronous: bool = False):
        if asynchronous:
            if self.async_wrapper:
                return self.async_wrapper
        else:
            if self.sync_wrapper:
                return self.sync_wrapper
        return self.wrapper

    def get_parser(self, asynchronous: bool = False):
        return self.get_wrapper(asynchronous).parser

    def get_executor(self, asynchronous: bool = False):
        if asynchronous:
            if self.async_executor:
                return self.async_executor
        else:
            if self.sync_executor:
                return self.sync_executor
        return self.executor

    @property
    def default_wrapper_properties(self):
        return {key: PathParam for key in self.path_names}

    def iter_plugins(self):
        for cls, plugin in self._plugins.items():
            yield plugin

    def getattr(self, name: str, default=None):
        return getattr(self.f, name, default)

    @property
    def module_name(self):
        return getattr(self.f, "__module__", None)

    @property
    def is_method(self):
        return self.name.lower() == self.method.lower()

    @property
    def is_passed(self):
        return self.parser.is_passed

    @property
    def route(self):
        return self.getattr("route", "" if self.is_method else self.name)

    @property
    def parser(self):
        return self.wrapper.parser


class Endpoint(BaseEndpoint):
    @classmethod
    def apply_for(
        cls,
        func: Callable,
        api: Type["API"] = None,
        name: str = None,
        local_vars: dict = None,
    ):
        _cls = getattr(func, "cls", None)
        if not _cls or not issubclass(_cls, Endpoint):
            # override current class
            _cls = cls

        kwargs = {}
        for key, val in inspect.signature(_cls).parameters.items():
            v = getattr(func, key, None)
            if v is None:
                continue
            # func properties override the default kwargs
            kwargs[key] = v
        if api:
            kwargs.update(api=api)
        if name:
            kwargs.update(name=name)
        if local_vars:
            kwargs.update(local_vars=local_vars)
        return _cls(func, **kwargs)

    def __init__(
        self,
        f: Callable,
        *,
        api: Type["API"] = None,
        method: str,
        name: str = None,
        plugins: list = None,
        idempotent: bool = None,
        eager: bool = False,
        # openapi specs:
        operation_id: str = None,
        tags: list = None,
        summary: str = None,
        description: str = None,
        local_vars: dict = None,
        extension: dict = None,
    ):

        super().__init__(
            f,
            plugins=plugins,
            method=method,
            name=name,
            idempotent=idempotent,
            eager=eager,
            local_vars=local_vars,
        )
        self.api = api
        self.response_type = getattr(api, "response", None)
        if self.response_type and not Response.is_cls(self.response_type):
            self.response_type = None
        self.operation_id = operation_id
        self.tags = tags
        self.summary = summary
        self.description = description
        self.extension = extension

    def __call__(self, *args, **kwargs):
        executor = self.get_executor(False)
        r = executor(*args, **kwargs)
        if inspect.isawaitable(r):
            raise exc.ServerError("awaitable detected in sync function")
        return r

    @utils.awaitable(__call__)
    async def __call__(self, *args, **kwargs):
        executor = self.get_executor(True)
        r = executor(*args, **kwargs)
        while inspect.isawaitable(r):
            # executor is maybe a sync function, which will not need to await
            r = await r
        return r

    @property
    def openapi_extension(self):
        ext = {}
        if not self.extension or not isinstance(self.extension, dict):
            return ext
        for key, val in self.extension.items():
            key = str(key).lower().replace("_", "-")
            if not key.startswith("x-"):
                key = f"x-{key}"
            ext[key] = val
        return ext

    @property
    def ref(self) -> str:
        if self.api:
            return f"{self.api.__ref__}.{self.name}"
        if self.module_name:
            return f"{self.module_name}.{self.name}"
        return self.name

    def handler(self, api: "API"):
        args, kwargs = self.parse_request(api.request)
        return self(api, *args, **kwargs)

    async def async_handler(self, api: "API"):
        args, kwargs = await self.async_parse_request(api.request)
        return await self(api, *args, **kwargs)

    def parse_request(self, request: Request):
        try:
            kwargs = dict(var.path_params.getter(request))
            wrapper = self.get_wrapper(False)
            kwargs.update(wrapper.parse_context(request))
            return wrapper.parser.parse_params(
                (), kwargs, context=wrapper.parser.options.make_context()
            )
        except utype.exc.ParseError as e:
            raise exc.BadRequest(str(e), detail=e.get_detail()) from e

    async def async_parse_request(self, request: Request):
        try:
            kwargs = dict(await var.path_params.getter(request))
            wrapper = self.get_wrapper(True)
            kwargs.update(await wrapper.async_parse_context(request))
            return wrapper.parser.parse_params(
                (), kwargs, context=wrapper.parser.options.make_context()
            )
            # in base Endpoint, args is not supported
        except utype.exc.ParseError as e:
            raise exc.BadRequest(str(e), detail=e.get_detail()) from e
