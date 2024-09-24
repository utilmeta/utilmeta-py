import inspect

from utilmeta.utils import PluginEvent, PluginTarget, \
    Error, url_join, classonlymethod, json_dumps, \
    COMMON_METHODS, EndpointAttr, \
    parse_query_string, parse_query_dict

from utype.types import *
from http.cookies import SimpleCookie
from .backends.base import ClientRequestAdaptor
from utilmeta.core.response import Response
from utilmeta.core.response.base import Headers
from .endpoint import ClientEndpoint
from utilmeta.core.request import Request, properties
from utilmeta.utils.context import Property

import urllib
from urllib.parse import urlsplit, urlunsplit, urlencode
from utilmeta import UtilMeta
from functools import partial
from typing import TypeVar

T = TypeVar('T')

setup_class = PluginEvent('setup_class', synchronous_only=True)
process_request = PluginEvent('process_request', streamline_result=True)
handle_error = PluginEvent('handle_error')
process_response = PluginEvent('process_response', streamline_result=True)


def prop_is(prop: Property, ident):
    return prop.__ident__ == ident


def prop_in(prop: Property, ident):
    if not prop.__in__:
        return False
    in_ident = getattr(prop.__in__, '__ident__', None)
    if in_ident:
        return in_ident == ident
    return prop.__in__ == ident


def parse_proxies(proxies: Union[str, List[str], Dict[str, str]], scheme=None) -> Dict[str, List[str]]:
    if isinstance(proxies, str):
        from urllib.parse import urlparse
        parsed = urlparse(proxies)
        if parsed.scheme:
            return {parsed.scheme: [proxies]}
        if scheme:
            return {scheme: scheme + '://' + proxies}
        return {
            'http': ['http://' + proxies],
            'https': ['https://' + proxies],
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


class Client(PluginTarget):
    _endpoint_cls: Type[ClientEndpoint] = ClientEndpoint
    _request_cls: Type[Request] = Request

    def __init_subclass__(cls, **kwargs):
        if not issubclass(cls._request_cls, Request):
            raise TypeError(f'Invalid request class: {cls._request_cls}, must be subclass of Request')
        if not issubclass(cls._endpoint_cls, ClientEndpoint):
            raise TypeError(f'Invalid request class: {cls._endpoint_cls}, must be subclass of ClientEndpoint')

        cls._generate_endpoints()
        setup_class(cls, **kwargs)
        super().__init_subclass__(**kwargs)

    @classonlymethod
    def _generate_endpoints(cls):
        for key, val in cls.__dict__.items():
            if not inspect.isfunction(val):
                continue

            if inspect.isfunction(val):
                if key.lower() in COMMON_METHODS:
                    continue

                method = getattr(val, EndpointAttr.method, None)
                # hook_type = getattr(val, EndpointAttr.hook, None)

                if method:
                    # a sign to wrap it in Unit
                    # 1. @api.get                (method='get')
                    # 2. @api.parser             (method=None)
                    # 3. def get(self):          (method='get')
                    # 4. @api(method='CUSTOM')   (method='custom')
                    val = cls._endpoint_cls.apply_for(val, cls)
                # elif hook_type:
                #     val = cls._hook_cls.dispatch_for(val, hook_type)
                else:
                    continue

                setattr(cls, key, val)  # reset value

    def __init__(self,
                 base_url: Union[str, List[str]] = None,
                 backend=None,      # urllib / requests / aiohttp / httpx
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
                 charset: str = 'utf-8',
                 fail_silently: bool = False,
                 ):

        super().__init__(plugins=plugins)

        self._internal = internal
        self._mock = mock

        if not backend:
            backend = urllib
        self._backend = backend

        # backend_name = None
        if isinstance(backend, str):
            backend_name = backend
        elif inspect.ismodule(backend):
            backend_name = backend.__name__
        else:
            raise TypeError(f'Invalid backend: {repr(backend)}, must be a module or str')

        self._backend_name = backend_name
        self._service = service
        self._base_url = base_url
        self._default_timeout = default_timeout
        self._base_headers = base_headers or {}
        self._base_query = base_query or {}
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
            raise TypeError(f'Invalid cookies: {cookies}, must be str or dict')
        else:
            cookies = SimpleCookie()

        for _key, _val in self._base_headers.items():
            if _key.lower() == 'cookie':
                cookies.update(SimpleCookie(_val))
                break

        # this hold the persistent cookies
        self._cookies = cookies
        self._context = {}

        self._original_cookies = SimpleCookie(cookies)
        self._original_headers = dict(self._base_headers)
        self._original_query = dict(self._base_query)

        for key, val in self.__class__.__dict__.items():
            if isinstance(val, ClientEndpoint):
                setattr(self, key, partial(val, self))

    def __enter__(self: T) -> T:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cookies = SimpleCookie(self._original_cookies)
        self._base_headers = dict(self._original_headers)
        self._base_query = dict(self._original_query)

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
        if self._internal:
            return path

        parsed = urlsplit(path)
        qs = parse_query_string(parsed.query)
        if isinstance(query, dict):
            qs.update(parse_query_dict(query))

        # base_url: null
        # path: https://origin.com/path?key=value

        base_url = self._base_url or (self._service.base_url if self._service else '')

        if parsed.scheme:
            # ignore base url
            url = urlunsplit((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                '',     # query
                ''      # query
            ))
        else:
            url = url_join(base_url, parsed.path)

        if self._append_slash:
            url = url.rstrip('/') + '/'

        return url + (('?' + urlencode(qs)) if qs else '')

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
            _headers['cookie'] = ';'.join([f'{key}={val.value}' for key, val in _cookies.items() if val.value])

        return _headers

    def _build_request(self,
                       method: str,
                       path: str = None,
                       query: dict = None,
                       data=None,
                       # form: dict = None,
                       headers: dict = None,
                       cookies=None):
        # body = None
        # headers = Headers(headers or {})
        # content_type = headers.get('content-type')
        # if isinstance(form, dict) and form:
        #     if any(file_like(val) for val in form.values()):
        #         body = encode_multipart_form(form)
        #         content_type = RequestType.FORM_DATA
        #     else:
        #         body = urlencode(form).encode(self._charset)
        #         content_type = RequestType.FORM_URLENCODED
        #
        # elif data:
        #     if isinstance(data, (dict, list, tuple)):
        #         if isinstance(data, dict) and any(file_like(val) for val in data.values()):
        #             body = encode_multipart_form(data)
        #             content_type = RequestType.FORM_DATA
        #         else:
        #             content_type = RequestType.JSON
        #             body = json_dumps(data).encode(self._charset)
        #     elif isinstance(data, (bytes, io.BytesIO)):
        #         body = data
        #         content_type = RequestType.OCTET_STREAM
        #     else:
        #         content_type = RequestType.PLAIN
        #         body = str(data).encode(self._charset)
        #
        url = self._build_url(
            path=path,
            query=query
        )
        headers = self._build_headers(
            headers=headers,
            cookies=cookies
        )
        # if content_type:
        #     headers.setdefault('content-type', content_type)
        return self._request_cls(
            method=method,
            url=url,
            data=data,
            headers=headers,
            backend=self._backend
        )

    def __request__(self, endpoint: ClientEndpoint, *args, **kwargs):
        if self._mock:
            if endpoint.response_types:
                resp = endpoint.response_types[0]
                return resp.mock()
            return None

        request = self._build_function_request(endpoint, args, kwargs)
        retry_index = 0
        start_time = request.time
        while True:
            try:
                request.adaptor.update_context(
                    start_time=start_time,
                    retry_index=retry_index,
                    idempotent=endpoint.idempotent
                )
                result = self._process_request(request) or request
                # this result can be a Request or Response

                if isinstance(result, Request):
                    request = result
                    # do not bother generate another same request in another retry
                    response = self._make_request(request)
                else:
                    response = result

                result = self._process_response(self._parse_response(
                    response,
                    types=endpoint.response_types
                ))

                if isinstance(result, Request):
                    # need another loop
                    request = result
                elif isinstance(result, Response):
                    response = result
                    break
                else:
                    raise TypeError(f'invalid response: {result}')

            except Exception as e:
                err = Error(e, request=request)
                result = self.handle_error(err)
                if isinstance(result, Request):
                    request = result
                elif isinstance(result, Response):
                    response = result
                    break
                else:
                    raise err.throw()
            retry_index += 1  # add

        if not isinstance(response, Response):
            raise TimeoutError(f'No response')
        return response

    async def __async_request__(self, endpoint: ClientEndpoint, *args, **kwargs):
        if self._mock:
            if endpoint.response_types:
                resp = endpoint.response_types[0]
                return resp.mock()
            return None

        request = self._build_function_request(endpoint, args, kwargs)
        retry_index = 0
        start_time = request.time
        while True:
            try:
                request.adaptor.update_context(
                    start_time=start_time,
                    retry_index=retry_index,
                    idempotent=endpoint.idempotent
                )
                result = (await self._async_process_request(request)) or request
                # this result can be a Request or Response

                if isinstance(result, Request):
                    request = result
                    # do not bother generate another same request in another retry
                    response = await self._make_async_request(request)
                else:
                    response = result

                result = await self._async_process_response(self._parse_response(
                    response,
                    types=endpoint.response_types
                ))

                if isinstance(result, Request):
                    # need another loop
                    request = result
                elif isinstance(result, Response):
                    response = result
                    break
                else:
                    raise TypeError(f'invalid response: {result}')

            except Exception as e:
                err = Error(e, request=request)
                result = self.handle_error(err)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, Request):
                    request = result
                elif isinstance(result, Response):
                    response = result
                    break
                else:
                    raise err.throw()
            retry_index += 1  # add

        if not isinstance(response, Response):
            raise TimeoutError(f'No response')
        return response

    def _parse_response(self, response: Response, types: List[Type[Response]]) -> Response:
        from utype import type_transform

        if not types:
            return type_transform(response, Response)

        if not isinstance(response, Response):
            response = Response(response)

        for i, response_cls in enumerate(types):
            if isinstance(response, response_cls):
                return response

            if response_cls.status and response.status != response_cls.status:
                continue

            try:
                return response_cls(response=response, strict=True)
            except Exception as e:   # noqa
                if i == len(types) - 1 and not self._fail_silently:
                    raise e
                continue

        return type_transform(response, Response)

    def _build_function_request(self, endpoint: ClientEndpoint, args: tuple, kwargs: dict) -> Request:
        # get Call object from kwargs
        args, kwargs = endpoint.parser.parse_params(args, kwargs, context=endpoint.parser.options.make_context())
        for i, arg in enumerate(args):
            kwargs[endpoint.parser.pos_key_map[i]] = arg

        url = url_join(self._base_url or '', endpoint.route, append_slash=self._append_slash)
        query = dict(self._base_query or {})
        headers = dict(self._base_headers or {})
        cookies = SimpleCookie(self._cookies or {})
        body = None
        path_params = {}

        for name, value in kwargs.items():
            if name in endpoint.path_args:
                path_params[name] = value
                continue

            inst = endpoint.wrapper.attrs.get(name)
            if not inst:
                continue

            prop = inst.prop
            key = inst.name  # this is FINAL alias key name instead of attname

            if not prop:
                continue

            if prop_in(prop, 'path'):
                # PathParam
                path_params[key] = value
            elif prop_in(prop, 'query'):
                # QueryParam
                query[key] = value
            elif prop_is(prop, 'query'):
                # Query
                if isinstance(value, Mapping):
                    query.update(value)
            elif prop_in(prop, 'body'):
                # BodyParam
                if isinstance(body, dict):
                    body[key] = value
                else:
                    body = {key: value}
                if isinstance(prop, properties.Body):
                    if prop.content_type:
                        headers.update({'content-type': prop.content_type})
            elif prop_is(prop, 'body'):
                # Body
                if isinstance(body, dict) and isinstance(value, Mapping):
                    body.update(value)
                else:
                    body = value
            elif prop_in(prop, 'header'):
                # HeaderParam
                headers[key] = value
            elif prop_is(prop, 'header'):
                # Headers
                if isinstance(value, Mapping):
                    headers.update(value)
            elif prop_in(prop, 'cookie'):
                # CookieParam
                cookies[key] = value
            elif prop_is(prop, 'cookie'):
                # Cookies
                if isinstance(value, Mapping):
                    cookies.update(value)

        for key, val in path_params.items():
            unit = '{%s}' % key
            url = url.replace(unit, str(val))

        if isinstance(cookies, SimpleCookie) and cookies:
            headers.update({
                'cookie': ';'.join([f'{key}={val.value}' for key, val in cookies.items() if val.value])
            })

        return self._request_cls(
            method=endpoint.method,
            url=url,
            query=query,
            data=body,
            headers=headers,
            backend=self._backend
        )

    def _process_request(self, request: Request):
        request = self.process_request(request)
        if not isinstance(request, Request):
            return request

        # request = process_request(self, request)
        for handler in process_request.iter(self):
            try:
                request = handler(request, self)
            except NotImplementedError:
                continue
            if not isinstance(request, Request):
                return request
        return request

    async def _async_process_request(self, request: Request):
        request = self.process_request(request)
        if inspect.isawaitable(request):
            request = await request     # noqa

        if not isinstance(request, Request):
            return request

        # request = process_request(self, request)
        for handler in process_request.iter(self):
            try:
                request = handler(request, self)
            except NotImplementedError:
                continue
            if inspect.isawaitable(request):
                request = await request
            if not isinstance(request, Request):
                return request
        return request

    def _process_response(self, response: Response):
        # --- common process
        if response.cookies:
            self._cookies.update(response.cookies)
        # ----
        response = self.process_response(response)
        if not isinstance(response, Response):
            # need to invoke another request
            return response
        for handler in process_response.iter(self):
            try:
                resp = handler(response, self)
            except NotImplementedError:
                continue
            if isinstance(resp, Request):
                # need to invoke another request
                return resp
            if isinstance(resp, Response):
                # only take value if return value is Response objects
                response = resp
        return response

    async def _async_process_response(self, response: Response):
        # --- common process
        if response.cookies:
            self._cookies.update(response.cookies)
        # ----
        response = self.process_response(response)
        if inspect.isawaitable(response):
            response = await response   # noqa

        if not isinstance(response, Response):
            # need to invoke another request
            return response
        for handler in process_response.iter(self):
            try:
                resp = handler(response, self)
            except NotImplementedError:
                continue
            if inspect.isawaitable(response):
                response = await response
            if isinstance(resp, Request):
                # need to invoke another request
                return resp
            if isinstance(resp, Response):
                # only take value if return value is Response objects
                response = resp
        return response

    def _make_request(self, request: Request, timeout: int = None) -> Response:
        if self._internal:
            service = self._service
            if not service:
                from utilmeta import service

            root_api = service.resolve()
            request.adaptor.route = request.path.strip('/')

            try:
                response = root_api(request)()
            except Exception as e:
                response = getattr(root_api, 'response', Response)(error=e, request=request)

        else:
            adaptor: ClientRequestAdaptor = ClientRequestAdaptor.dispatch(request)
            if timeout is None:
                timeout = request.adaptor.get_context('timeout')        # slot
            resp = adaptor(
                timeout=timeout or self._default_timeout,
                allow_redirects=self._allow_redirects
            )
            response = Response(response=resp, request=request)

        return response

    async def _make_async_request(self, request: Request, timeout: int = None) -> Response:
        if self._internal:
            service = self._service
            if not service:
                from utilmeta import service

            root_api = service.resolve()
            request.adaptor.route = request.path.strip('/')

            try:
                response = root_api(request)()
                if inspect.isawaitable(response):
                    response = await response
            except Exception as e:
                response = getattr(root_api, 'response', Response)(error=e, request=request)

        else:
            adaptor: ClientRequestAdaptor = ClientRequestAdaptor.dispatch(request)
            if timeout is None:
                timeout = request.adaptor.get_context('timeout')        # slot
            resp = adaptor(
                timeout=timeout or self._default_timeout,
                allow_redirects=self._allow_redirects
            )
            if inspect.isawaitable(resp):
                resp = await resp
            response = Response(response=resp, request=request)
        return response

    def request(self, method: str, path: str = None, query: dict = None,
                data=None,
                headers: dict = None, cookies=None, timeout: int = None) -> Response:

        request = self._build_request(
            method=method,
            path=path,
            query=query,
            data=data,
            # form=form,
            headers=headers,
            cookies=cookies
        )
        response = self._make_request(request, timeout=timeout)
        return self._process_response(response)

    async def async_request(self, method: str, path: str = None, query: dict = None,
                            data=None,
                            headers: dict = None, cookies=None,
                            timeout: int = None) -> Response:
        request = self._build_request(
            method=method,
            path=path,
            query=query,
            data=data,
            headers=headers,
            cookies=cookies
        )
        response = await self._make_async_request(request, timeout=timeout)
        return await self._async_process_response(response)

    def get(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='GET', path=path, query=query, data=data, headers=headers)

    async def async_get(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='GET', path=path, query=query, data=data, headers=headers)

    def post(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='POST', path=path, query=query, data=data, headers=headers)

    async def async_post(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='POST', path=path, query=query, data=data, headers=headers)

    def put(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='PUT', path=path, query=query, data=data, headers=headers)

    async def async_put(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='PUT', path=path, query=query, data=data, headers=headers)

    def patch(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='PATCH', path=path, query=query, data=data, headers=headers)

    async def async_patch(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='PATCH', path=path, query=query, data=data, headers=headers)

    def delete(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='DELETE', path=path, query=query, data=data, headers=headers)

    async def async_delete(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='DELETE', path=path, query=query, data=data, headers=headers)

    def options(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='OPTIONS', path=path, query=query, data=data, headers=headers)

    async def async_options(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='OPTIONS', path=path, query=query, data=data, headers=headers)

    def head(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='HEAD', path=path, query=query, data=data, headers=headers)

    async def async_head(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return await self.async_request(method='HEAD', path=path, query=query, data=data, headers=headers)

    def process_request(self, request: Request):
        return request

    def process_response(self, response: Response):     # noqa : meant to be inherited
        """
        Process response can also be treated as a hook (callback)
        to handle non-blocking requests
        when the response is finally retrieved, call the function
        to execute the following processes, so as to the @api.after()
        :param response:
        :return:
        """
        return response

    def handle_error(self, error: Error):
        raise error.throw()
