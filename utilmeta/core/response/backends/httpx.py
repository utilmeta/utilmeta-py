from httpx import Response
from .base import ResponseAdaptor
from http.cookies import SimpleCookie


class HttpxClientResponseAdaptor(ResponseAdaptor):
    response: Response

    def iter_bytes(self, chunk_size=None):
        chunk_size = chunk_size or self.get_default_chunk_size()
        yield from self.response.iter_bytes(chunk_size)

    async def aiter_bytes(self, chunk_size=None):
        chunk_size = chunk_size or self.get_default_chunk_size()
        try:
            async for chunk in self.response.aiter_bytes(chunk_size):
                yield chunk
        except RuntimeError:
            for chunk in self.response.iter_bytes(chunk_size):
                yield chunk

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, Response)

    @property
    def status(self):
        return self.response.status_code

    @property
    def url(self):
        return str(self.response.url)

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
        self.__dict__["body"] = self.response.content
        return self.get_content()

    @property
    def cookies(self):
        set_cookie = self.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        if set_cookie:
            for cookie in set_cookie:
                cookies.update(SimpleCookie(cookie))
        return cookies

    # @property
    # def cookies(self):
    #     return self.response.cookies

    def close(self):
        self.response.close()

    async def aclose(self):
        try:
            await self.response.aclose()
        except RuntimeError:
            self.response.close()

    @property
    def request(self):
        return self.response.request
