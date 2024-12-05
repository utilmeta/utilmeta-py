from requests import Response
from typing import Union
from .base import ResponseAdaptor


class RequestsResponseAdaptor(ResponseAdaptor):
    response: Response

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, Response)

    @property
    def status(self):
        return self.response.status_code

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
