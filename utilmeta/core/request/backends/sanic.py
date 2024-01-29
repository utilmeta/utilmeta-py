from sanic.request import Request
from .base import RequestAdaptor
import sanic


class SanicRequestAdaptor(RequestAdaptor):
    backend = sanic

    def gen_csrf_token(self):
        pass

    def check_csrf_token(self) -> bool:
        pass

    @property
    def address(self):
        return self.request.remote_addr

    @property
    def cookies(self):
        return self.request.cookies

    def get_form(self):
        form = dict(self.request.form)
        form.update(self.request.files)
        return form

    async def async_read(self):
        await self.request.receive_body()
        return self.body

    request: Request

    @property
    def request_method(self):
        return self.request.method

    @property
    def url(self):
        return self.request.url

    @property
    def body(self):
        return self.request.body

    @property
    def headers(self):
        return self.request.headers

    @property
    def query_string(self):
        return self.request.query_string
