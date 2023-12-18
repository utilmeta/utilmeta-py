from requests import Request
from .base import RequestAdaptor


class RequestsRequestAdaptor(RequestAdaptor):
    @property
    def request_method(self) -> str:
        return self.request.method

    @property
    def url(self):
        return self.request.url

    @property
    def cookies(self):
        return self.request.cookies

    @property
    def headers(self):
        return self.request.headers

    def get_form(self):
        return self.request.files

    @property
    def body(self) -> bytes:
        prepared = self.request.prepare()
        return prepared.body

    request: Request
