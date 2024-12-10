import inspect

from utilmeta.utils import (
    PluginEvent,
    PluginTarget,
    Error,
    url_join,
    classonlymethod,
    json_dumps,
    COMMON_METHODS,
    EndpointAttr,
    valid_url,
    parse_query_string,
    parse_query_dict,
)

from utype.types import *
from http.cookies import SimpleCookie
from .backends.base import ClientRequestAdaptor
from utilmeta.core.response import Response
from utilmeta.core.response.base import Headers
from utilmeta.conf import Preference
from .endpoint import ClientEndpoint, ClientRoute
from .chain import ClientChainBuilder
from utilmeta.core.request import Request
from utilmeta.core.api import decorator
from utype.utils.compat import is_annotated
from utype import Schema
from .hook import Hook
import urllib
from urllib.parse import urlsplit, urlunsplit, urlencode
from utilmeta import UtilMeta
from functools import partial
from typing import TypeVar


T = TypeVar("T")

setup_class = PluginEvent("setup_class", synchronous_only=True)
process_request = PluginEvent("process_request", streamline_result=True)
handle_error = PluginEvent("handle_error")
process_response = PluginEvent("process_response", streamline_result=True)


def parse_proxies(
    proxies: Union[str, List[str], Dict[str, str]], scheme=None
) -> Dict[str, List[str]]:
    if isinstance(proxies, str):
        from urllib.parse import urlparse

        parsed = urlparse(proxies)
        if parsed.scheme:
            return {parsed.scheme: [proxies]}
        if scheme:
            return {scheme: scheme + "://" + proxies}
        return {
            "http": ["http://" + proxies],
            "https": ["https://" + proxies],
        }
    elif isinstance(proxies, list):
        values = {}
        for v in proxies:
            urls = parse_proxies(v, scheme=scheme)
            for _s, _urls in urls.items():
                if _s in values:
                    values[_s].extend(urls)
                else:
                    values[_s] = _urls
        return values
    elif isinstance(proxies, dict):
        values = {}
        for _s, _urls in proxies.items():
            values.update(parse_proxies(_urls, scheme=_s))
    return {}


class ClientParameters(Schema):
    base_url: Union[str, List[str], None]
    backend: Any
    append_slash: Optional[bool]
    base_headers: Optional[Dict[str, str]]
    base_cookies: SimpleCookie
    base_query: Optional[Dict[str, Any]]
    allow_redirects: Optional[bool]
    charset: Optional[str]

    # --
    # request_cls: Any
    service: Any
    mock: Optional[bool]
    internal: Optional[bool]
    plugins: list = ()
    fail_silently: Optional[bool]
    default_timeout: Union[float, int, timedelta, None]
    proxies: Optional[dict]


class Client(PluginTarget):
    _endpoint_cls: Type[ClientEndpoint] = ClientEndpoint
    _request_cls: Type[Request] = Request
    _chain_cls: Type[ClientChainBuilder] = ClientChainBuilder
    _clients: Dict[str, ClientRoute] = {}
    _hook_cls = Hook
    _route_cls = ClientRoute

    def __init_subclass__(cls, **kwargs):
        if not issubclass(cls._request_cls, Request):
            raise TypeError(
                f"Invalid request class: {cls._request_cls}, must be subclass of Request"
            )
        if not issubclass(cls._endpoint_cls, ClientEndpoint):
            raise TypeError(
                f"Invalid request class: {cls._endpoint_cls}, must be subclass of ClientEndpoint"
            )

        cls._generate_endpoints()
        setup_class(cls, **kwargs)
        super().__init_subclass__(**kwargs)

    @classonlymethod
    def _generate_endpoints(cls):
        endpoints = []
        hooks = []
        clients = {}

        for key, api in cls.__annotations__.items():
            if key.startswith("_"):
                continue
            val = cls.__dict__.get(key)

            if is_annotated(api):
                # param: Annotated[str, request.QueryParam()]
                api = getattr(api, "__origin__", None)

            if inspect.isclass(api) and issubclass(api, Client):
                kwargs = dict(route=key, name=key, parent=cls)
                if not val:
                    val = getattr(api, "_generator", None)
                if isinstance(val, decorator.APIGenerator):
                    kwargs.update(val.kwargs)
                elif inspect.isfunction(val):
                    raise TypeError(
                        f"{cls.__name__}: generate route [{repr(key)}] failed: conflict api and endpoint"
                    )
                route = cls._route_cls(api, **kwargs)
                clients[key] = route

        for key, val in cls.__dict__.items():
            if not inspect.isfunction(val):
                continue

            if inspect.isfunction(val):
                method = getattr(val, EndpointAttr.method, None)
                hook_type = getattr(val, EndpointAttr.hook, None)

                if method:
                    if hasattr(Client, key):
                        if key.lower() in COMMON_METHODS:
                            raise TypeError(
                                f"{cls.__name__}: generate route for {repr(key)} failed: HTTP method "
                                f'name is reserved for Client class, please use @api.{key.lower()}("/")'
                            )
                        else:
                            raise TypeError(
                                f"{cls.__name__}: generate route for {repr(key)} failed: "
                                f"name conflicted with Client method"
                            )

                    # a sign to wrap it in Unit
                    # 1. @api.get                (method='get')
                    # 2. @api.parser             (method=None)
                    # 3. def get(self):          (method='get')
                    # 4. @api(method='CUSTOM')   (method='custom')
                    val = cls._endpoint_cls.apply_for(val, cls)
                elif hook_type:
                    val = cls._hook_cls.dispatch_for(
                        val, hook_type, target_type="client"
                    )
                else:
                    continue
                setattr(cls, key, val)  # reset value

            if isinstance(val, ClientEndpoint):
                endpoints.append(val)
            if isinstance(val, Hook):
                hooks.append(val)

        for hook in hooks:
            for route in clients.values():
                route.hook(hook)
            for endpoint in endpoints:
                endpoint.client_route.hook(hook)

        cls._clients = clients

    def __init__(
        self,
        base_url: Union[str, List[str]] = None,
        backend=None,  # urllib / requests / aiohttp / httpx
        service: Optional[UtilMeta] = None,
        mock: bool = False,
        internal: bool = False,
        plugins: list = (),
        # session=None,      # used to pass along the sdk classes
        # prepend_route: str = None,
        append_slash: bool = None,
        default_timeout: Union[float, int, timedelta] = None,
        base_headers: Dict[str, str] = None,
        base_cookies: Union[str, Dict[str, str], SimpleCookie] = None,
        base_query: Dict[str, Any] = None,
        proxies: dict = None,
        allow_redirects: bool = None,
        charset: str = "utf-8",
        fail_silently: bool = False,
    ):

        super().__init__(plugins=plugins)

        if not backend:
            pref = Preference.get()
            backend = pref.client_default_request_backend or urllib

        self._internal = internal
        self._mock = mock

        # backend_name = None
        if isinstance(backend, str):
            backend_name = backend
        elif inspect.ismodule(backend):
            backend_name = backend.__name__
        else:
            raise TypeError(
                f"Invalid backend: {repr(backend)}, must be a module or str"
            )

        self._backend_name = backend_name
        self._backend = backend

        self._service = service
        self._base_query = base_query or {}
        self._default_timeout = default_timeout
        self._base_headers = base_headers or {}

        if base_url:
            # check base url
            res = urlsplit(base_url)
            if not res.scheme:
                # allow ws / wss in the future
                raise ValueError(
                    f"utilmeta.core.cli.Client: Invalid base_url: {repr(base_url)}, "
                    f"must be a valid url"
                )
            if res.query:
                self._base_query.update(parse_query_string(res.query))
            base_url = urlunsplit(
                (res.scheme, res.netloc, res.path, "", "")  # query  # fragment
            )

        self._base_url = base_url
        self._proxies = proxies
        self._allow_redirects = allow_redirects
        self._charset = charset

        # self._prepend_route = prepend_route
        self._append_slash = append_slash
        self._fail_silently = fail_silently

        cookies = base_cookies
        if isinstance(cookies, str):
            cookies = SimpleCookie(cookies)
        elif isinstance(cookies, dict):
            # includes BaseCookie cookies
            cookies = SimpleCookie(cookies)
        elif cookies:
            raise TypeError(f"Invalid cookies: {cookies}, must be str or dict")
        else:
            cookies = SimpleCookie()

        for _key, _val in self._base_headers.items():
            if _key.lower() == "cookie":
                cookies.update(SimpleCookie(_val))
                break

        # this hold the persistent cookies
        self._cookies = cookies
        self._context = {}

        self._original_cookies = SimpleCookie(cookies)
        self._original_headers = dict(self._base_headers)
        self._original_query = dict(self._base_query)

        self._client_route: Optional["ClientRoute"] = None

        for key, val in self.__class__.__dict__.items():
            if isinstance(val, ClientEndpoint):
                setattr(self, key, partial(val, self))

        if self._clients:
            params = self.get_client_params()
            for name, client_route in self._clients.items():
                client_base_url = url_join(self._base_url, client_route.route)
                client_cls = client_route.handler
                params = dict(params)
                params.update(
                    base_url=client_base_url, plugins=self._plugins  # inject plugins
                )
                client = client_cls(**params)
                client._client_route = client_route.merge_hooks(self._client_route)
                client._cookies = self._cookies
                client._context = self._context
                setattr(self, name, client)

    def __enter__(self: T) -> T:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cookies = SimpleCookie(self._original_cookies)
        self._base_headers = dict(self._original_headers)
        self._base_query = dict(self._original_query)

    @property
    def fail_silently(self):
        return self._fail_silently

    @property
    def cookies(self):
        return self._cookies

    @property
    def request_cls(self):
        return self._request_cls

    @property
    def client_route(self) -> "ClientRoute":
        return self._client_route

    @classonlymethod
    def __reproduce_with__(cls, generator: decorator.APIGenerator):
        plugins = generator.kwargs.get("plugins")
        if plugins:
            cls._add_plugins(*plugins)
        cls._generator = generator
        return cls

    def get_client_params(self):
        return ClientParameters(
            base_url=self._base_url,
            backend=self._backend,
            service=self._service,
            base_headers=self._base_headers,
            base_query=self._base_query,
            base_cookies=self._cookies,  # use cookies as base_cookies to pass session to sub client
            append_slash=self._append_slash,
            allow_redirects=self._allow_redirects,
            proxies=self._proxies,
            charset=self._charset,
            default_timeout=self._default_timeout,
            fail_silently=self._fail_silently,
            mock=self._mock,
            internal=self._internal,
            plugins=self._plugins,
        )

    def update_cookies(self, cookies: dict):
        if isinstance(cookies, dict):
            self._cookies.update(cookies)

    def update_base_headers(self, headers: dict):
        if isinstance(headers, dict):
            self._base_headers.update(headers)

    def update_base_query(self, query: dict):
        if isinstance(query, dict):
            self._base_query.update(query)

    def _build_url(self, path: str, query: dict = None):
        # if self._internal:
        #     return path
        query_params = dict(self._base_query or {})
        # 1. base_query
        parsed = urlsplit(path)
        qs: str = parsed.query
        if qs:
            query_params.update(parse_query_string(qs))
        # 2. path query
        if isinstance(query, dict) and query:
            query_params.update(parse_query_dict(query))
        # 3. assigned query

        # base_url: null
        # path: https://origin.com/path?key=value

        base_url = self._base_url or (self._service.base_url if self._service else "")

        if parsed.scheme:
            # ignore base url
            url = urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")  # query  # fragment
            )
        else:
            url = url_join(base_url, parsed.path)

        if self._append_slash:
            url = url.rstrip("/") + "/"

        return url + (("?" + urlencode(query_params)) if query_params else "")

    def _build_headers(self, headers, cookies=None):
        if cookies:
            _cookies = SimpleCookie(self._cookies)
            _cookies.update(SimpleCookie(cookies))
        else:
            _cookies = self._cookies

        _headers = Headers({})

        if headers:
            for key, value in headers.items():
                if not isinstance(value, (str, bytes)):
                    if isinstance(value, (dict, list)):
                        value = json_dumps(value)
                    else:
                        value = str(value)
                _headers[key] = value

        if isinstance(_cookies, SimpleCookie) and _cookies:
            _headers["cookie"] = ";".join(
                [f"{key}={val.value}" for key, val in _cookies.items() if val.value]
            )

        return _headers

    def _build_request(
        self,
        method: str,
        path: str = None,
        query: dict = None,
        data=None,
        # form: dict = None,
        headers: dict = None,
        cookies=None,
    ):
        url = self._build_url(path=path, query=query)
        headers = self._build_headers(headers=headers, cookies=cookies)
        # if content_type:
        #     headers.setdefault('content-type', content_type)
        return self._request_cls(
            method=method, url=url, data=data, headers=headers, backend=self._backend
        )

    def __request__(self, endpoint: ClientEndpoint, request: Request):
        if self._mock:
            if endpoint.response_types:
                resp = endpoint.response_types[0]
                return resp.mock()
            return None

        def make_request(req: Request = request):
            return endpoint.parse_response(
                self._make_request(req), fail_silently=self._fail_silently
            )

        handler = self._chain_cls(self, endpoint).build_client_handler(
            make_request, asynchronous=False
        )
        return handler(request)

    async def __async_request__(self, endpoint: ClientEndpoint, request: Request):
        if self._mock:
            if endpoint.response_types:
                resp = endpoint.response_types[0]
                return resp.mock()
            return None

        async def make_request(req: Request = request):
            return endpoint.parse_response(
                await self._make_async_request(req), fail_silently=self._fail_silently
            )

        handler = self._chain_cls(self, endpoint).build_client_handler(
            make_request, asynchronous=True
        )
        return await handler(request)

    def _make_request(self, request: Request, timeout: int = None) -> Response:
        if self._internal:
            service = self._service
            if not service:
                from utilmeta import service

            root_api = service.resolve()
            request.adaptor.route = request.path.strip("/")

            try:
                response = root_api(request)()
            except Exception as e:
                response = getattr(root_api, "response", Response)(
                    error=e, request=request
                )

        else:
            adaptor: ClientRequestAdaptor = ClientRequestAdaptor.dispatch(request)
            if timeout is None:
                timeout = request.adaptor.get_context("timeout")  # slot
                if timeout is None:
                    timeout = self._default_timeout
            if timeout is not None:
                timeout = float(timeout)
            try:
                resp = adaptor(timeout=timeout, allow_redirects=self._allow_redirects)
            except Exception as e:
                if not self._fail_silently:
                    raise e from e
                timeout = "timeout" in str(e).lower()
                response = Response(
                    timeout=timeout, error=e, request=request, aborted=True
                )
            else:
                response = Response(response=resp, request=request)

        if response.cookies:
            # update response cookies
            self._cookies.update(response.cookies)

        return response

    async def _make_async_request(
        self, request: Request, timeout: int = None
    ) -> Response:
        if self._internal:
            service = self._service
            if not service:
                from utilmeta import service

            root_api = service.resolve()
            request.adaptor.route = request.path.strip("/")

            try:
                response = root_api(request)()
                if inspect.isawaitable(response):
                    response = await response
            except Exception as e:
                response = getattr(root_api, "response", Response)(
                    error=e, request=request
                )

        else:
            adaptor: ClientRequestAdaptor = ClientRequestAdaptor.dispatch(request)
            if timeout is None:
                timeout = request.adaptor.get_context("timeout")  # slot
            try:
                resp = adaptor(
                    timeout=timeout or self._default_timeout,
                    allow_redirects=self._allow_redirects,
                )
                if inspect.isawaitable(resp):
                    resp = await resp
            except Exception as e:
                if not self._fail_silently:
                    raise e from e
                timeout = "timeout" in str(e).lower()
                response = Response(
                    error=e, request=request, timeout=timeout, aborted=True
                )
            else:
                response = Response(response=resp, request=request)
        return response

    def request(
        self,
        method: str,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ) -> Response:

        request = self._build_request(
            method=method,
            path=path,
            query=query,
            data=data,
            # form=form,
            headers=headers,
            cookies=cookies,
        )
        return self._make_request(request, timeout=timeout)

    async def async_request(
        self,
        method: str,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ) -> Response:
        request = self._build_request(
            method=method,
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
        )
        return await self._make_async_request(request, timeout=timeout)

    def get(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="GET",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_get(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="GET",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def post(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="POST",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_post(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="POST",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def put(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="PUT",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_put(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="PUT",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def patch(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="PATCH",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_patch(
        self,
        path: str = None,
        query: dict = None,
        data=None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="PATCH",
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def delete(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="DELETE",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_delete(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="DELETE",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def options(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="OPTIONS",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_options(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return await self.async_request(
            method="OPTIONS",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def head(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="HEAD",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    async def async_head(
        self,
        path: str = None,
        query: dict = None,
        headers: dict = None,
        cookies=None,
        timeout: int = None,
    ):
        return self.request(
            method="HEAD",
            path=path,
            query=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
        )

    def process_request(self, request: Request):
        pass

    def process_response(self, response: Response):  # noqa : meant to be inherited
        """
        Process response can also be treated as a hook (callback)
        to handle non-blocking requests
        when the response is finally retrieved, call the function
        to execute the following processes, so as to the @api.after()
        :param response:
        :return:
        """
        pass

    def handle_error(self, error: Error):
        pass
