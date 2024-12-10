from sanic.request import Request
from .base import RequestAdaptor
import sanic
import ipaddress
from utilmeta.core.file.backends.sanic import SanicFileAdaptor
from sanic.request.form import File as SanicFile
from utilmeta.core.file.base import File
from utilmeta.utils import multi, get_request_ip
from utype import unprovided


class SanicRequestAdaptor(RequestAdaptor):
    file_adaptor_cls = SanicFileAdaptor
    backend = sanic

    def gen_csrf_token(self):
        pass

    def check_csrf_token(self) -> bool:
        pass

    @property
    def address(self):
        try:
            ip = self.request.remote_addr
            if ip:
                return ipaddress.ip_address(ip)
        except (AttributeError, ValueError):
            pass
        return get_request_ip(dict(self.headers)) or ipaddress.ip_address("127.0.0.1")

    @property
    def cookies(self):
        return self.request.cookies

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
        if not unprovided(self._body):
            return self._body
        return self.request.body

    @property
    def headers(self):
        return self.request.headers

    @property
    def query_string(self):
        return self.request.query_string

    def get_form(self):
        form = dict(self.request.form)
        form.update(self.request.files)
        return self.process_form(form)

    def process_form(self, data: dict):
        form = {}
        for key, value in data.items():
            if multi(value):
                res = []
                for val in value:
                    if isinstance(val, SanicFile):
                        val = File(self.file_adaptor_cls(val))
                    res.append(val)
                value = res
            elif isinstance(value, SanicFile):
                value = File(self.file_adaptor_cls(value))
            form[key] = value
        return form

    # async def async_load(self):
    #     try:
    #         if not self.request.body:
    #             await self.request.receive_body()
    #         if self.form_type:
    #             return self.get_form()
    #         if self.json_type:
    #             return self.request.json
    #         self.__dict__['body'] = self.request.body
    #         return self.get_content()
    #     except NotImplementedError:
    #         raise
    #     except Exception as e:
    #         raise exceptions.UnprocessableEntity(f'process request body failed with error: {e}') from e
