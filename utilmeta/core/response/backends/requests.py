from requests import Response
from typing import Union
from .base import ResponseAdaptor


class RequestsResponseAdaptor(ResponseAdaptor):
    response: Response

    def iter_bytes(self, chunk_size=None):
        yield from self.response.iter_content(chunk_size=chunk_size or self.get_default_chunk_size() or 1)

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
        return self.response.reason

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.content

    def get_text(self) -> str:
        return self.response.text

    def get_json(self, **kwargs) -> Union[dict, list]:
        return self.response.json(**kwargs)

    def close(self):
        self.response.close()

    @property
    def request(self):
        return self.response.request
