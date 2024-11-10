from aiohttp.web_request import Request
from .base import RequestAdaptor
from utilmeta.utils import async_to_sync, RequestType
from utilmeta.core.file.backends.aiohttp import AiohttpFileAdaptor
import aiohttp
from utype import unprovided
from multidict import MultiDictProxy
from aiohttp.web_request import FileField
from typing import Union
from utilmeta.core.file import File


class AiohttpRequestAdaptor(RequestAdaptor):
    backend = aiohttp
    file_adaptor_cls = AiohttpFileAdaptor

    @property
    def request_method(self):
        return self.request.method

    @property
    def url(self):
        return self.request.url

    @property
    def query_params(self):
        return self.request.query

    @property
    def query_string(self):
        return self.request.query_string

    @property
    def encoded_path(self):
        return self.request.path_qs

    @property
    def headers(self):
        return self.request.headers

    @property
    def cookies(self):
        return self.request.cookies

    def get_form(self):
        return async_to_sync(self.request.post)()

    @property
    def body(self):
        if not unprovided(self._body):
            return self._body
        return async_to_sync(self.async_read)()

    def process_form(self, data: MultiDictProxy[Union[str, bytes, FileField]]):
        form = {}
        result = {}
        for key, value in data.items():
            # https://aiohttp-kxepal-test.readthedocs.io/en/latest/multidict.html
            if isinstance(value, FileField):
                value = File(self.file_adaptor_cls(value))
            form.setdefault(key, []).append(value)
        for key, val in form.items():
            if len(val) == 1:
                result[key] = val[0]
            else:
                result[key] = val
        return result

    async def async_get_content(self):
        if self.content_type == RequestType.FORM_DATA:
            return self.process_form(await self.request.post())
        return self.get_content()

    async def async_read(self):
        return await self.request.read()

    def __init__(self, request: Request):
        super().__init__(request)
        self.request = request
