from httpx import Response
from .base import ResponseAdaptor


class HttpxClientResponseAdaptor(ResponseAdaptor):
    response: Response

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, Response)

    @property
    def status(self):
        return self.response.status_code

    @property
    def reason(self):
        return self.response.reason_phrase

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.read()

    async def async_read(self) -> bytes:
        return await self.response.aread()

    async def async_load(self):
        await self.response.aread()
        if self.text_type:
            return self.response.text
        elif self.json_type:
            return self.response.json()
        self.__dict__['body'] = self.response.content
        return self.get_content()

    # @property
    # def cookies(self):
    #     return self.response.cookies

    def close(self):
        self.response.close()
