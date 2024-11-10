from starlette.requests import Request
from utilmeta.utils import async_to_sync, RequestType, parse_query_string
from utilmeta.core.file.backends.starlette import StarletteFileAdaptor
from utilmeta.core.file.base import File
from starlette.datastructures import UploadFile, FormData
from .base import RequestAdaptor, get_request_ip
from ipaddress import ip_address
import starlette
from utype import unprovided


class StarletteRequestAdaptor(RequestAdaptor):
    """
    This adaptor can adapt starlette project and all frameworks based on it
    such as [FastAPI]
    """
    request: Request
    file_adaptor_cls = StarletteFileAdaptor
    backend = starlette

    @classmethod
    def reconstruct(cls, adaptor: 'RequestAdaptor'):
        pass

    def gen_csrf_token(self):
        pass

    def check_csrf_token(self) -> bool:
        pass

    @property
    def address(self):
        addr = get_request_ip(dict(self.headers))
        if addr:
            return addr
        return ip_address(self.request.client.host)

    @property
    def request_method(self) -> str:
        return self.request.method

    @property
    def url(self) -> str:
        return str(self.request.url)        # request.url is a URL structure, str will get the inner _url

    @property
    def cookies(self):
        return self.request.cookies

    @property
    def query_params(self):
        query = {}
        for key, value in self.request.query_params.multi_items():
            query.setdefault(key.rstrip('[]'), []).append(value)
        return {k: val[0] if len(val) == 1 else val for k, val in query.items()}

    @property
    def query_string(self):
        return self.request.url.query

    @property
    def path(self):
        return self.request.url.path

    @property
    def scheme(self):
        return self.request.url.scheme

    @property
    def encoded_path(self):
        path, query = self.path, self.query_string
        if query:
            return path + '?' + query
        return path

    @property
    def headers(self):
        return self.request.headers

    @property
    def body(self) -> bytes:
        if not unprovided(self._body):
            return self._body
        return async_to_sync(self.async_read)()

    @body.setter
    def body(self, data):
        self._body = data
        self.request._body = data

    async def async_read(self):
        return await self.request.body()

    def get_form(self):
        return self.process_form(async_to_sync(self.request.form)())

    def process_form(self, data: FormData):
        form = {}
        result = {}
        for key, value in data.multi_items():
            if isinstance(value, UploadFile):
                value = File(self.file_adaptor_cls(value))
            form.setdefault(key, []).append(value)
        for key, val in form.items():
            if len(val) == 1:
                result[key] = val[0]
            else:
                result[key] = val
        return result

    async def async_get_content(self):
        if self.form_type:
            if self.content_type == RequestType.FORM_URLENCODED:
                if not unprovided(self._body):
                    self._body = await self.request.body()
                return parse_query_string(self.body.decode())

            elif self.content_type == RequestType.FORM_DATA:
                if not unprovided(self._body):
                    from starlette.formparsers import MultiPartParser

                    async def steam():
                        yield self._body
                        yield b""
                        return

                    form = await MultiPartParser(
                        self.headers, steam()
                    ).parse()
                else:
                    form = await self.request.form()
                return self.process_form(form)
            return {}
        return self.get_content()
