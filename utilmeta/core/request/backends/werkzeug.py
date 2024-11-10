from .base import RequestAdaptor
from werkzeug.wrappers import Request
from utilmeta.core.file.backends.werkzeug import WerkzeugFileAdaptor
from utilmeta.core.file.base import File
from utilmeta.utils import Headers, exceptions, HAS_BODY_METHODS
import werkzeug


class WerkzeugRequestAdaptor(RequestAdaptor):
    request: Request
    file_adaptor_cls = WerkzeugFileAdaptor
    backend = werkzeug

    def __init__(self, request, route: str = None, *args, **kwargs):
        super().__init__(request, route, *args, **kwargs)
        # Flask request cannot access after close
        # we store the variables here
        self._url = self.request.url
        self._query_string = self.request.query_string.decode()
        self._headers = Headers({key: val for key, val in self.request.headers.items()})
        self._method = str(self.request.method).lower()
        self._query_params = self.request.args
        self._cookies = self.request.cookies
        self._body = None
        self._form = None
        if self._method in HAS_BODY_METHODS:
            self._body = self.request.data
            if self.form_type:
                self._form = self.get_form()

    @property
    def request_method(self):
        return self._method

    @property
    def url(self):
        return self._url

    @property
    def encoded_path(self):
        return f"{self.path}?{self.query_string}" if self.query_string else self.path

    @property
    def query_string(self):
        return self._query_string

    @property
    def query_params(self):
        return self._query_params

    @property
    def body(self):
        return self._body or b''

    @property
    def headers(self):
        return self._headers

    @property
    def cookies(self):
        return self._cookies

    def get_form(self):
        if self._form is not None:
            return self._form
        form = dict(self.request.form)
        parsed_files = {}
        for key, files in self.request.files.lists():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        form.update(parsed_files)
        return form
