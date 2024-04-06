from .base import RequestAdaptor
from werkzeug.wrappers import Request
from utilmeta.core.file.backends.werkzeug import WerkzeugFileAdaptor
from utilmeta.core.file.base import File
from utilmeta.utils import Headers, exceptions
import werkzeug


class WerkzeugRequestAdaptor(RequestAdaptor):
    request: Request
    file_adaptor_cls = WerkzeugFileAdaptor
    backend = werkzeug

    def __init__(self, request, route: str = None, *args, **kwargs):
        super().__init__(request, route, *args, **kwargs)
        self._url = self.request.url

    @property
    def request_method(self):
        return self.request.method

    @property
    def url(self):
        return self._url

    @property
    def encoded_path(self):
        return f"{self.path}?{self.query_string}" if self.query_string else self.path

    @property
    def query_string(self):
        return self.request.query_string.decode()

    @property
    def query_params(self):
        return self.request.args

    @property
    def body(self):
        return self.request.data

    @property
    def headers(self):
        return Headers({key: val for key, val in self.request.headers.items()})

    @property
    def cookies(self):
        return self.request.cookies

    def get_form(self):
        form = dict(self.request.form)
        parsed_files = {}
        for key, files in self.request.files.lists():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        form.update(parsed_files)
        return form

    async def async_load(self):
        try:
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exceptions.UnprocessableEntity(f'process request body failed with error: {e}') from e
