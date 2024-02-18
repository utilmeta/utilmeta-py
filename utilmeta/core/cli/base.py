import inspect

from utilmeta.utils import PluginEvent, PluginTarget, \
    Error, awaitable, url_join, file_like, \
    encode_multipart_form, RequestType, json_dumps
from utype.types import *
from http.cookies import SimpleCookie
from utilmeta.core.request import Request
from .backends.base import ClientRequestAdaptor
from utilmeta.core.response import Response
from utilmeta.core.response.base import Headers

import urllib
from urllib.parse import urlparse, parse_qs, urlencode
# from urllib.request import Request
from utilmeta import UtilMeta

process_request = PluginEvent('process_request', streamline_result=True)
handle_error = PluginEvent('handle_error')
process_response = PluginEvent('process_response', streamline_result=True)


class Client(PluginTarget):
    def __init__(self,
                 base_url: Union[str, List[str]] = None,
                 backend=None,      # urllib / requests / aiohttp / httpx
                 service: Optional[UtilMeta] = None,
                 mock: bool = False,
                 internal: bool = False,

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
                 ):

        super().__init__()

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cookies = {}

    def _build_url(self, path: str, query: dict = None):
        if self._internal:
            return path
        parsed = urlparse(path)
        qs = parse_qs(parsed.query)
        if isinstance(query, dict):
            qs.update(query)
        base_url = self._base_url or (self._service.base_url if self._service else '')
        base_path = url_join(base_url, parsed.path)
        if self._append_slash:
            base_path = base_path.rstrip('/') + '/'
        return base_path + (('?' + urlencode(qs)) if qs else '')

    def _build_headers(self, headers, cookies=None):
        if cookies:
            _cookies = SimpleCookie(self._cookies)
            _cookies.update(SimpleCookie(cookies))
        else:
            _cookies = self._cookies
        headers = headers or {}
        if isinstance(_cookies, SimpleCookie) and _cookies:
            headers.update({
                'cookie': ';'.join([f'{key}={val.value}' for key, val in _cookies.items() if val.value])
            })
        return Headers(headers)

    def _build_request(self,
                       method: str,
                       path: str = None,
                       query: dict = None,
                       data=None,
                       form: dict = None,
                       headers: dict = None,
                       cookies=None):

        body = None
        content_type = None
        if isinstance(form, dict) and form:
            if any(file_like(val) for val in form.values()):
                body = encode_multipart_form(form)
                content_type = RequestType.FORM_DATA
            else:
                body = urlencode(form).encode(self._charset)
                content_type = RequestType.FORM_URLENCODED
        elif data:
            if isinstance(data, (dict, list, tuple)):
                content_type = RequestType.JSON
                body = json_dumps(data).encode(self._charset)
            elif isinstance(data, bytes):
                body = data
                content_type = RequestType.OCTET_STREAM
            else:
                content_type = RequestType.PLAIN
                body = str(data).encode(self._charset)
        url = self._build_url(
            path=path,
            query=query
        )
        headers = self._build_headers(
            headers=headers,
            cookies=cookies
        )
        if content_type:
            headers.setdefault('content-type', content_type)
        return Request(
            method=method,
            url=url,
            data=body,
            headers=headers,
            backend=self._backend
        )

    def _process_request(self, request: Request):
        request = self.process_request(request)
        if not isinstance(request, Request):
            return request

        request = process_request(self, request)
        for handler in process_request.iter(self):
            try:
                request = handler(request, self)
            except NotImplementedError:
                continue
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

    def request(self, method: str, path: str = None, query: dict = None,
                data=None, form: dict = None,
                headers: dict = None, cookies=None,
                timeout: int = None) -> Response:

        req = self._build_request(
            method=method,
            path=path,
            query=query,
            data=data,
            form=form,
            headers=headers,
            cookies=cookies
        )

        if self._internal:
            service = self._service
            if not service:
                from utilmeta import service

            root_api = service.resolve()
            req.adaptor.route = req.path.strip('/')

            try:
                response = root_api(req)()
            except Exception as e:
                response = getattr(root_api, 'response', Response)(error=e, request=req)

        else:
            adaptor: ClientRequestAdaptor = ClientRequestAdaptor.dispatch(req)
            resp = adaptor(
                timeout=timeout or self._default_timeout,
                allow_redirects=self._allow_redirects
            )
            response = Response(response=resp, request=req)

        return self._process_response(response)

    @awaitable(request)
    async def request(self, method: str, path: str = None, query: dict = None,
                      data=None, form: dict = None,
                      headers: dict = None, cookies=None,
                      timeout: int = None) -> Response:
        pass

    def get(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='GET', path=path, query=query, data=data, headers=headers)

    def post(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='POST', path=path, query=query, data=data, headers=headers)

    def put(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='PUT', path=path, query=query, data=data, headers=headers)

    def patch(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='PATCH', path=path, query=query, data=data, headers=headers)

    def delete(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='DELETE', path=path, query=query, data=data, headers=headers)

    def options(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='OPTIONS', path=path, query=query, data=data, headers=headers)

    def head(self, path: str = None, query: dict = None, data=None, headers: dict = None):
        return self.request(method='HEAD', path=path, query=query, data=data, headers=headers)

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

    def handle_error(self, request: Request, error: Error):
        raise error.throw()
