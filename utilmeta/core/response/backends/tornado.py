from tornado.httpclient import HTTPResponse as ClientResponse
from .base import ResponseAdaptor


class TornadoClientResponseAdaptor(ResponseAdaptor):
    response: ClientResponse

    def iter_bytes(self, chunk_size=None):
        chunk_size = chunk_size or self.get_default_chunk_size()
        if self.response.buffer:
            for chunk in self.response.buffer.read(chunk_size):
                yield chunk

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, ClientResponse)

    @property
    def url(self):
        return str(self.response.effective_url)

    @property
    def status(self):
        return self.response.code

    @property
    def reason(self):
        return self.response.reason

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.body

    def close(self):
        if self.response.buffer:
            self.response.buffer.close()

# class TornadoServerResponseAdaptor(ResponseAdaptor):
#     response: ServerResponse
#
#     @property
#     def status(self):
#         return self.response.status
#
#     @property
#     def reason(self):
#         return self.response.reason
#
#     @property
#     def headers(self):
#         return self.response.headers
#
#     @property
#     def body(self) -> bytes:
#         return self.response.body
#
#     @property
#     def cookies(self):
#         return self.response.cookies
