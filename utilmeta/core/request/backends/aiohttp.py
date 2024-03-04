from aiohttp.web_request import Request
from .base import RequestAdaptor
from utilmeta.utils import async_to_sync
from utilmeta.utils import exceptions as exc
import aiohttp


class AiohttpRequestAdaptor(RequestAdaptor):
    backend = aiohttp

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

    def get_form(self):
        return async_to_sync(self.request.post)()

    @property
    def body(self):
        if 'body' in self.__dict__:
            return self.__dict__.get('body')
        return async_to_sync(self.async_read)()

    async def async_load(self):
        try:
            if self.form_type:
                return await self.request.post()
            elif self.json_type:
                return await self.request.json()
            elif self.text_type:
                return await self.request.text()
            self.__dict__['body'] = await self.request.read()
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exc.UnprocessableEntity(f'process request body failed with error: {e}')

    async def async_read(self):
        return await self.request.read()

    def __init__(self, request: Request):
        super().__init__(request)
        self.request = request
