from aiohttp.client_reqrep import ClientResponse
from aiohttp.web_response import Response as ServerResponse

# from utilmeta.utils import async_to_sync
from .base import ResponseAdaptor


class AiohttpClientResponseAdaptor(ResponseAdaptor):
    response: ClientResponse

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
        if isinstance(self.response, ClientResponse):
            pass
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
