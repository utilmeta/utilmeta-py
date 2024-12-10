from utilmeta import utils
from utilmeta.utils import exceptions as exc
import inspect
from utilmeta.core.api.endpoint import BaseEndpoint

# from utilmeta.core.response import Response
# from utype.parser.rule import LogicalType

from utilmeta.utils import Error, function_pass
from utype.types import *
from http.cookies import SimpleCookie
from utilmeta.core.request import Request, properties
from utilmeta.core.response import Response
from utilmeta.core.api.route import BaseRoute
from .hook import ClientErrorHook, ClientAfterHook, ClientBeforeHook

if TYPE_CHECKING:
    from .base import Client


def prop_is(prop: properties.Property, ident):
    return prop.__ident__ == ident


def prop_in(prop: properties.Property, ident):
    if not prop.__in__:
        return False
    in_ident = getattr(prop.__in__, "__ident__", None)
    if in_ident:
        return in_ident == ident
    return prop.__in__ == ident


class ClientRoute(BaseRoute):
    def __init__(
        self,
        handler: Union[Type["Client"], "ClientEndpoint"],
        route: str,
        name: str,
        parent=None,
        before_hooks: List[ClientBeforeHook] = (),
        after_hooks: List[ClientAfterHook] = (),
        error_hooks: Dict[Type[Exception], ClientErrorHook] = None,
    ):
        super().__init__(
            handler,
            route=route,
            name=name,
            parent=parent,
            before_hooks=before_hooks,
            after_hooks=after_hooks,
            error_hooks=error_hooks,
        )


class ClientEndpoint(BaseEndpoint):
    PATH_REGEX = utils.PATH_REGEX
    ASYNCHRONOUS = None
    route_cls = ClientRoute
    error_cls = Error

    @classmethod
    def apply_for(cls, func: Callable, client: Type["Client"] = None):
        _cls = getattr(func, "cls", None)
        _async = inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)
        if not _cls or not issubclass(_cls, ClientEndpoint):
            # override current class
            if cls.ASYNCHRONOUS == _async:
                _cls = cls
            else:
                for sub_class in cls.__subclasses__():
                    if sub_class.ASYNCHRONOUS == _async:
                        _cls = sub_class

        kwargs = {}
        for key, val in inspect.signature(_cls).parameters.items():
            v = getattr(func, key, None)
            if v is None:
                continue
            # func properties override the default kwargs
            kwargs[key] = v
        if client:
            kwargs.update(client=client)
        return _cls(func, **kwargs)

    def __init__(
        self,
        f: Callable,
        *,
        client: Type["Client"] = None,
        method: str,
        plugins: list = None,
        idempotent: bool = None,
        eager: bool = False,
    ):

        super().__init__(
            f, plugins=plugins, method=method, idempotent=idempotent, eager=eager
        )
        # self.is_async = self.parser.is_asynchronous
        self.client = client
        self.client_route = self.route_cls(
            self,
            route=self.route,
            name=self.name,
        )
        self.client_wrap = False
        if self.client:
            self.client_wrap = not all(
                [
                    function_pass(self.client.process_request),
                    function_pass(self.client.process_response),
                    function_pass(self.client.handle_error),
                ]
            )
        self.path_args = self.PATH_REGEX.findall(self.route)

        # if self.parser.is_asynchronous:
        #     self.__call__ = self.async_call
        # else:
        #     self.__call__ = self.call

    @property
    def ref(self) -> str:
        if self.client:
            return f"{self.client.__ref__}.{self.f.__name__}"
        if self.module_name:
            return f"{self.module_name}.{self.f.__name__}"
        return self.f.__name__

    def __call__(self, client: "Client", /, *args, **kwargs):
        if not self.is_passed:
            return self.executor(client, *args, **kwargs)
        if self.parser.is_asynchronous:
            return client.__async_request__(self, *args, **kwargs)
        else:
            return client.__request__(self, *args, **kwargs)

    def build_request(self, client: "Client", /, *args, **kwargs) -> Request:
        # get Call object from kwargs
        args, kwargs = self.parser.parse_params(
            args, kwargs, context=self.parser.options.make_context()
        )
        for i, arg in enumerate(args):
            kwargs[self.parser.pos_key_map[i]] = arg

        client_params = client.get_client_params()
        try:
            url = utils.url_join(
                client_params.base_url or "",
                self.route,
                append_slash=client_params.append_slash,
            )
        except Exception as e:
            raise e.__class__(
                f"utilmeta.core.cli.Client: build request url with base_url:"
                f" {repr(client_params.base_url)} and route: {repr(self.route)} failed: {e}"
            ) from e

        query = dict(client_params.base_query or {})
        headers = dict(client_params.base_headers or {})
        cookies = SimpleCookie(client_params.base_cookies or {})
        # client_params.base_cookies = client.cookies
        # use the latest cookies instead of params
        body = None
        path_params = {}

        for name, value in kwargs.items():
            if name in self.path_args:
                path_params[name] = value
                continue

            inst = self.wrapper.attrs.get(name)
            if not inst:
                continue

            prop = inst.prop
            key = inst.name  # this is FINAL alias key name instead of attname

            if not prop:
                continue

            if prop_in(prop, "path"):
                # PathParam
                path_params[key] = value
            elif prop_in(prop, "query"):
                # QueryParam
                query[key] = value
            elif prop_is(prop, "query"):
                # Query
                if isinstance(value, Mapping):
                    query.update(value)
            elif prop_in(prop, "body"):
                # BodyParam
                if isinstance(body, dict):
                    body[key] = value
                else:
                    body = {key: value}
            elif prop_is(prop, "body"):
                # Body
                if isinstance(body, dict) and isinstance(value, Mapping):
                    body.update(value)
                else:
                    body = value
                if isinstance(prop, properties.Body):
                    if prop.content_type:
                        headers.update({"content-type": prop.content_type})
            elif prop_in(prop, "header"):
                # HeaderParam
                headers[key] = value
            elif prop_is(prop, "header"):
                # Headers
                if isinstance(value, Mapping):
                    headers.update(value)
            elif prop_in(prop, "cookie"):
                # CookieParam
                cookies[key] = value
            elif prop_is(prop, "cookie"):
                # Cookies
                if isinstance(value, Mapping):
                    cookies.update(value)

        for key, val in path_params.items():
            unit = "{%s}" % key
            url = url.replace(unit, str(val))

        if isinstance(cookies, SimpleCookie) and cookies:
            headers.update(
                {
                    "cookie": ";".join(
                        [
                            f"{key}={val.value}"
                            for key, val in cookies.items()
                            if val.value
                        ]
                    )
                }
            )

        return client.request_cls(
            method=self.method,
            url=url,
            query=query,
            data=body,
            headers=headers,
            backend=client_params.backend,
        )

    def parse_response(
        self, response: Response, fail_silently: bool = False
    ) -> Response:
        if not isinstance(response, Response):
            response = Response(response)

        if not self.response_types:
            return response

        if response.is_aborted:
            # return if response is generated from aborted error
            return response

        for i, response_cls in enumerate(self.response_types):
            if isinstance(response, response_cls):
                if response_cls != Response or len(self.response_types) == 1:
                    # if response types is only -> Response
                    # return any
                    return response

        # pref = Preference.get()
        for i, response_cls in enumerate(self.response_types):
            if response_cls.status and response.status != response_cls.status:
                continue
            try:
                return response_cls(response=response, strict=True)
            except Exception as e:  # noqa
                if i == len(self.response_types) - 1 and not fail_silently:
                    raise e
                continue

        return response


class SyncClientEndpoint(ClientEndpoint):
    ASYNCHRONOUS = False

    def __call__(self, client: "Client", *args, **kwargs):
        with self.client_route.merge_hooks(client.client_route) as route:
            r = None
            request = None
            try:
                request = self.build_request(client, *args, **kwargs)

                for hook in route.before_hooks:
                    hook.serve(client, request)

                if not self.is_passed:
                    r = self.executor(client, *args, **kwargs)
                    if inspect.isawaitable(r):
                        raise exc.ServerError("awaitable detected in sync function")

                if r is None:
                    r = client.__request__(self, request)

                for hook in route.after_hooks:
                    r = hook(client, r) or r

            except Exception as e:
                error = self.error_cls(e, request=request)
                hook = error.get_hook(
                    route.error_hooks, exact=isinstance(error.exception, exc.Redirect)
                )
                # hook applied before handel_error plugin event
                if hook:
                    r = hook(self, error)
                else:
                    raise error.throw()

            return r


class AsyncClientEndpoint(ClientEndpoint):
    ASYNCHRONOUS = True

    async def __call__(self, client: "Client", *args, **kwargs):
        # async with self:
        with self.client_route.merge_hooks(client.client_route) as route:
            r = None
            request = None
            try:
                request = self.build_request(client, *args, **kwargs)
                for hook in route.before_hooks:
                    _ = hook.serve(client, request)
                    if inspect.isawaitable(_):
                        await _

                if not self.is_passed:
                    r = self.executor(client, *args, **kwargs)
                    while inspect.isawaitable(r):
                        # executor is maybe a sync function, which will not need to await
                        r = await r

                if r is None:
                    r = await client.__async_request__(self, request)

                for hook in route.after_hooks:
                    r = hook(client, r) or r
                    if inspect.isawaitable(r):
                        await r

            except Exception as e:
                error = self.error_cls(e, request=request)
                hook = error.get_hook(
                    route.error_hooks, exact=isinstance(error.exception, exc.Redirect)
                )
                # hook applied before handel_error plugin event
                if hook:
                    r = hook(self, error)
                    if inspect.isawaitable(r):
                        await r
                else:
                    raise error.throw()

            return r


# enter_endpoint.register(ClientEndpoint)
# exit_endpoint.register(ClientEndpoint)
