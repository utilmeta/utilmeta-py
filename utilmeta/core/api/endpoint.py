from utilmeta import utils
from utilmeta.utils import exceptions as exc
from typing import Callable, Union, Type, TYPE_CHECKING
from utilmeta.utils.plugin import PluginTarget, PluginEvent
from utilmeta.utils.error import Error
from utilmeta.utils.context import ContextWrapper, Property
from utype.parser.base import BaseParser
from utype.parser.func import FunctionParser
from utype.parser.field import ParserField
import inspect
from ..request import Request, var
from ..request.properties import QueryParam
from ..response import Response
import utype

if TYPE_CHECKING:
    from .base import API

process_request = PluginEvent('process_request', streamline_result=True)
handle_error = PluginEvent('handle_error')
process_response = PluginEvent('process_response', streamline_result=True)
enter_endpoint = PluginEvent('enter_endpoint')
exit_endpoint = PluginEvent('exit_endpoint')


class RequestContextWrapper(ContextWrapper):
    context_cls = Request
    default_property = QueryParam
    parser: FunctionParser

    def __init__(self, *args, **kwargs):
        self.header_names = []
        super().__init__(*args, **kwargs)
        # used in generate allow headers

    def init_prop(self, prop: Property, val: ParserField):    # noqa, to be inherit
        if prop.__ident__ == 'header':
            for origin in val.input_origins:
                parser = getattr(origin, '__parser__', None)
                if isinstance(parser, BaseParser):
                    utils.distinct_add(self.header_names, [str(v).lower() for v in parser.fields])
        elif prop.__in__ and getattr(prop.__in__, '__ident__', None) == 'header':
            name = val.name.lower()
            if name not in self.header_names:
                self.header_names += name
        else:
            headers = getattr(prop, 'headers', None)
            if headers and utils.multi(headers):
                utils.distinct_add(self.header_names, [str(v).lower() for v in headers])
        return prop.init(val)


class Endpoint(PluginTarget):
    @classmethod
    def apply_for(cls, func: Callable, api: Type['API'] = None):
        _cls = getattr(func, 'cls', None)
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
        return _cls(func, **kwargs)

    parser_cls = FunctionParser
    wrapper_cls = RequestContextWrapper

    def __init__(self, f: Callable, *,
                 api: Type['API'] = None,
                 method: str,
                 plugins: list = None,
                 idempotent: bool = None,
                 eager: bool = False
                 ):

        super().__init__(plugins=plugins)

        if not inspect.isfunction(f):
            raise TypeError(f'Invalid endpoint function: {f}')

        self.f = f
        self.api = api
        self.method = method
        self.idempotent = idempotent
        self.eager = eager
        self.name = self.__name__ = f.__name__
        self.wrapper = self.wrapper_cls(self.parser_cls.apply_for(f))
        self.executor = self.parser.wrap(
            eager_parse=self.eager,
            parse_params=False,
            parse_result=True
        )

    def iter_plugins(self):
        for cls, plugin in self._plugins.items():
            yield plugin

    def getattr(self, name: str, default=None):
        return getattr(self.f, name, default)

    @property
    def ref(self) -> str:
        if self.api:
            return f'{self.api.__ref__}.{self.f.__name__}'
        if self.module_name:
            return f'{self.module_name}.{self.f.__name__}'
        return self.f.__name__

    @property
    def module_name(self):
        return getattr(self.f, '__module__', None)

    @property
    def is_method(self):
        return self.name.lower() == self.method.lower()

    @property
    def is_passed(self):
        return self.parser.is_passed

    @property
    def route(self):
        return '' if self.is_method else self.getattr('route', self.name)

    @property
    def parser(self):
        return self.wrapper.parser

    def serve(self, api: 'API'):
        retry_index = 0
        while True:
            try:
                api.request.adaptor.update_context(
                    retry_index=retry_index,
                    idempotent=self.idempotent
                )
                req = self.process_request(api.request)
                if isinstance(req, Request):
                    api.request = req
                    args, kwargs = self.parse_request(api.request)
                    enter_endpoint(self, api, *args, **kwargs)
                    response = self(api, *args, **kwargs)
                else:
                    response = req
                result = self.process_response(response)
                if isinstance(result, Request):
                    # need another loop
                    api.request = result
                else:
                    response = result
                    break
            except Exception as e:
                err = Error(e)
                result = self.handle_error(api.request, err)
                if isinstance(result, Request):
                    api.request = result
                else:
                    response = result
                    break
            retry_index += 1
        exit_endpoint(self, api)
        return response

    @utils.awaitable(serve)
    async def serve(self, api: 'API'):
        retry_index = 0
        while True:
            try:
                api.request.adaptor.update_context(
                    retry_index=retry_index,
                    idempotent=self.idempotent
                )
                req = await self.process_request(api.request)
                if isinstance(req, Request):
                    api.request = req
                    args, kwargs = await self.parse_request(api.request)
                    await enter_endpoint(self, api, *args, **kwargs)
                    response = await self(api, *args, **kwargs)
                else:
                    response = req
                result = await self.process_response(response)
                if isinstance(result, Request):
                    # need another loop
                    api.request = result
                else:
                    response = result
                    break
            except Exception as e:
                err = Error(e)
                result = await self.handle_error(api.request, err)
                if isinstance(result, Request):
                    api.request = result
                else:
                    response = result
                    break
            retry_index += 1
        await exit_endpoint(self, api)
        return response

    def process_request(self, request: Request) -> Union[Request, Response]:
        for handler in process_request.iter(self):
            try:
                req = handler(request, self)
            except NotImplementedError:
                continue
            if isinstance(req, Response):
                return req
            if isinstance(req, Request):
                request = req
        return request

    @utils.awaitable(process_request)
    async def process_request(self, request: Request) -> Union[Request, Response]:
        for handler in process_request.iter(self):
            try:
                req = handler(request, self)
            except NotImplementedError:
                continue
            if inspect.isawaitable(req):
                req = await req
            if isinstance(req, Response):
                return req
            if isinstance(req, Request):
                request = req
        return request

    def process_response(self, response):
        for handler in process_response.iter(self):
            try:
                resp = handler(response, self)
            except NotImplementedError:
                continue
            if isinstance(resp, Request):
                # need to invoke another request
                return resp
            if isinstance(resp, Response):
                # only take value if return value is BaseResponse objects
                response = resp
                break
            else:
                response = resp
        return response

    @utils.awaitable(process_response)
    async def process_response(self, response):
        for handler in process_response.iter(self):
            try:
                resp = handler(response, self)
            except NotImplementedError:
                continue
            if inspect.isawaitable(resp):
                resp = await resp
            if isinstance(resp, Request):
                # need to invoke another request
                return resp
            if isinstance(resp, Response):
                # only take value if return value is BaseResponse objects
                response = resp
                break
            else:
                response = resp
        return response

    def handle_error(self, request: Request, e: Error):
        for error_handler in handle_error.iter(self):
            try:
                res = error_handler(request, e, self)
            except NotImplementedError:
                continue
            if isinstance(res, Request):
                # need to invoke another request
                return res
            if isinstance(res, Response):
                # only take value if return value is BaseResponse objects
                return res
        raise e.throw()

    @utils.awaitable(handle_error)
    async def handle_error(self, request: Request, e: Error):
        for error_handler in handle_error.iter(self):
            try:
                res = error_handler(request, e, self)
            except NotImplementedError:
                continue
            if inspect.isawaitable(res):
                res = await res
            if isinstance(res, Request):
                # need to invoke another request
                return res
            if isinstance(res, Response):
                # only take value if return value is BaseResponse objects
                return res
        raise e.throw()

    def __call__(self, *args, **kwargs):
        # with self:
        r = self.executor(*args, **kwargs)
        if inspect.isawaitable(r):
            raise exc.ServerError('awaitable detected in sync function')
        return r

    @utils.awaitable(__call__)
    async def __call__(self, *args, **kwargs):
        # async with self:
        r = self.executor(*args, **kwargs)
        while inspect.isawaitable(r):
            # executor is maybe a sync function, which will not need to await
            r = await r
        return r

    def parse_request(self, request: Request):
        try:
            kwargs = dict(var.path_params.getter(request))
            kwargs.update(self.wrapper.parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
        except utype.exc.ParseError as e:
            raise exc.BadRequest(str(e), detail=e.get_detail()) from e

    @utils.awaitable(parse_request)
    async def parse_request(self, request: Request):
        try:
            kwargs = dict(await var.path_params.getter(request))
            kwargs.update(await self.wrapper.parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
            # in base Endpoint, args is not supported
        except utype.exc.ParseError as e:
            raise exc.BadRequest(str(e), detail=e.get_detail()) from e

    def generate_call(self):
        pass


enter_endpoint.register(Endpoint)
exit_endpoint.register(Endpoint)
