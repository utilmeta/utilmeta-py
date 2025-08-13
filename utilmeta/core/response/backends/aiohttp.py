from aiohttp.client_reqrep import ClientResponse
from aiohttp.web_response import Response as ServerResponse
from typing import AsyncIterator
from .base import ResponseAdaptor


class AiohttpClientResponseAdaptor(ResponseAdaptor):
    response: ClientResponse

    async def aiter_bytes(self, chunk_size=None) -> AsyncIterator[bytes]:
        chunk_size = chunk_size or self.get_default_chunk_size()
        if chunk_size:
            reader = self.response.content.iter_chunked(chunk_size)
        else:
            reader = self.response.content
        async for chunk in reader:
            yield chunk

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, ClientResponse)

    @property
    def status(self):
        return self.response.status

    @property
    def reason(self):
        return self.response.reason

    @property
    def url(self):
        return str(self.response.url)

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return getattr(self.response, "_body", None)

    async def async_read(self) -> bytes:
        return await self.response.read()

    async def async_load(self):
        if self.text_type:
            return await self.response.text()
        elif self.json_type:
            return await self.response.json()
        self.__dict__["body"] = await self.async_read()
        return self.get_content()

    @property
    def cookies(self):
        return self.response.cookies

    def close(self):
        self.response.close()

    @property
    def request(self):
        return self.response.request_info


class AiohttpServerResponseAdaptor(ResponseAdaptor):
    response: ServerResponse

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, ServerResponse)

    @property
    def status(self):
        return self.response.status

    @property
    def reason(self):
        return self.response.reason

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.body

    @property
    def cookies(self):
        return self.response.cookies
