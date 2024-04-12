from starlette.requests import Request
from utilmeta.utils import async_to_sync
from utilmeta.utils import exceptions as exc
from utilmeta.core.file.backends.starlette import StarletteFileAdaptor
from utilmeta.core.file.base import File
from starlette.datastructures import UploadFile, FormData
from .base import RequestAdaptor, get_request_ip
from ipaddress import ip_address
import starlette


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
        addr = get_request_ip(self.headers)
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
        if 'body' in self.__dict__:
            return self.__dict__['body']
        return async_to_sync(self.async_read)()

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

    async def async_load(self):
        try:
            if self.form_type:
                data = await self.request.form()
                return self.process_form(data)
            if self.json_type:
                return await self.request.json()
            self.__dict__['body'] = await self.request.body()
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exc.UnprocessableEntity(f'process request body failed with error: {e}') from e
