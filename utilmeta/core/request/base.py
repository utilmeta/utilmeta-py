from utype.types import *
from typing import Optional, Union, Callable, List, Any, Dict, Tuple
from datetime import datetime, date, timedelta
from .backends.base import RequestAdaptor
from utilmeta.utils import MetaMethod, time_now, get_interval
from http.cookies import SimpleCookie
from collections.abc import Mapping
from . import var
from urllib.parse import urlsplit, parse_qs
from utilmeta.utils import Headers


__all__ = [
    'Request',
]


class DummyRequest:
    def __init__(self,
                 method: str,
                 url: str,
                 query: dict = None,
                 data=None,
                 headers: Dict[str, str] = None):
        self.method = method
        self.url = url or ''
        self.query = query or {}
        self.data = data
        self.headers = Headers(headers or {})
        cookie = SimpleCookie(self.headers.get('cookie', {}))
        self.cookies = {k: v.value for k, v in cookie.items()}

    @property
    def route(self):
        return urlsplit(self.url).path.strip('/')


class DummyRequestAdaptor(RequestAdaptor):
    request: DummyRequest

    def __init__(self, request: DummyRequest, route: str = None, *args, **kwargs):
        super().__init__(request, route=route or request.route, *args, **kwargs)

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, DummyRequest)

    @property
    def address(self):
        from ipaddress import ip_address
        return ip_address('127.0.0.1')

    @property
    def content_type(self) -> Optional[str]:
        ct = super().content_type
        if ct:
            return ct
        if isinstance(self.request.data, (dict, list)):
            return 'application/json'
        return None

    @property
    def request_method(self) -> str:
        return self.request.method

    @property
    def url(self) -> str:
        return str(self.request.url)        # request.url is a URL structure, str will get the inner _url

    @property
    def cookies(self):
        return self.request.cookies

    @property
    def query_params(self):
        params = super().query_params
        if self.request.query:
            params.update(self.request.query)
        return params

    @property
    def query_string(self):
        return urlsplit(self.request.url).query

    @property
    def path(self):
        return urlsplit(self.request.url).path

    @property
    def scheme(self):
        return urlsplit(self.request.url).scheme or 'http'

    @property
    def headers(self):
        return self.request.headers

    def get_form(self):
        if isinstance(self.request.data, dict):
            return self.request.data
        return None

    @property
    def body(self) -> bytes:
        return self.request.data

    async def async_read(self):
        return self.request.data

    async def async_load(self):
        return self.get_content()


class Request:
    adaptor_cls: Type[RequestAdaptor]

    method: str
    url: str
    query: dict
    data: Any
    headers: Union[Mapping, dict]
    cookies: Union[SimpleCookie, dict]

    @classmethod
    def apply_for(cls, req):
        if isinstance(req, Request):
            return req
        return cls(req)

    def __init__(self,
                 request=None, *,
                 method: str = None,
                 url: str = None,
                 query: dict = None,
                 data=None,
                 headers: Union[Mapping, Dict[str, str]] = None,
                 backend=None,
                 ):
        request = request or DummyRequest(
            method=method,
            url=url,
            query=query,
            data=data,
            headers=headers
        )
        self.adaptor = RequestAdaptor.dispatch(request)
        self.backend = self.adaptor.backend or backend
        # self.timeout = None

    # def set_timeout(self, timeout: Union[int, float, timedelta, datetime, None]):
    #     if isinstance(timeout, datetime):
    #         timeout = time_now() - timeout
    #     self.timeout = get_interval(timeout, null=True)

    @property
    def url(self):
        return self.adaptor.url

    @property
    def method(self):
        return self.adaptor.method

    @property
    def is_options(self):
        return self.adaptor.request_method.lower() == MetaMethod.OPTIONS

    @property
    def path(self) -> str:
        return self.adaptor.path

    @property
    def encoded_path(self) -> str:
        return self.adaptor.encoded_path

    @property
    def scheme(self):
        return self.adaptor.scheme

    @property
    def query_string(self) -> str:
        return self.adaptor.query_string

    @property
    def query(self) -> dict:
        return self.adaptor.query_params

    @property
    def cookies(self):
        return self.adaptor.cookies

    @property
    def origin(self):
        return self.adaptor.origin

    @property
    def headers(self) -> dict:
        return self.adaptor.headers

    @property
    def authorization(self) -> Tuple[Optional[str], Optional[str]]:
        auth: str = self.headers.get('authorization')
        if not auth:
            return None, None
        if ' ' in auth:
            lst = auth.split()
            return lst[0], ' '.join(lst[1:])
        return None, auth

    @property
    def content_type(self) -> Optional[str]:
        return self.adaptor.content_type

    @property
    def content_length(self) -> int:
        return self.adaptor.content_length

    @property
    def host(self):
        return self.adaptor.hostname

    @property
    def body(self) -> bytes:
        return self.adaptor.body

    async def aread(self) -> bytes:
        return await self.adaptor.async_read()

    @property
    def data(self):
        data = var.data.init(self)
        if data.contains():
            return data.get()
        return None

    @property
    def time(self) -> datetime:
        return self.adaptor.time

    @property
    def ip_address(self):
        return self.adaptor.address
