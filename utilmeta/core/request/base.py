from utype.types import *
from typing import Optional, Union, Any, Dict, Tuple
from datetime import datetime
from .backends.base import RequestAdaptor
from utilmeta.utils import MetaMethod
from http.cookies import SimpleCookie
from collections.abc import Mapping
from . import var


__all__ = [
    'Request',
]


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
        if not request:
            from .client import ClientRequest
            request = ClientRequest(
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
    def traffic(self):
        traffic = self.adaptor.get_context('traffic')
        if traffic:
            return traffic
        value = 12  # HTTP/1.1 200 OK \r\n
        value += len(str(self.encoded_path))
        value += len(str(self.adaptor.request_method))
        value += self.content_length or 0
        for key, val in self.headers.items():
            value += len(str(key)) + len(str(val)) + 4
        self.adaptor.update_context(traffic=traffic)
        return value

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

    @body.setter
    def body(self, data):
        self.adaptor.body = data

    async def aread(self) -> bytes:
        return await self.adaptor.async_read()

    @property
    def data(self):
        data = var.data.setup(self)
        if data.contains():
            return data.get()
        return self.adaptor.get_content()

    @data.setter
    def data(self, data):
        data_var = var.data.setup(self)
        data_var.set(data)
        self.adaptor.set_content(data)

    @property
    def time(self) -> datetime:
        return self.adaptor.time

    @property
    def ip_address(self):
        return self.adaptor.address
