from .base import RequestAdaptor
from werkzeug.wrappers import Request
from utilmeta.core.file.backends.werkzeug import WerkzeugFileAdaptor
from utilmeta.core.file.base import File
import werkzeug


class WerkzeugRequestAdaptor(RequestAdaptor):
    request: Request
    file_adaptor_cls = WerkzeugFileAdaptor
    backend = werkzeug

    @property
    def request_method(self):
        return self.request.method

    @property
    def url(self):
        return self.request.url

    @property
    def encoded_path(self):
        return self.request.full_path

    @property
    def query_string(self):
        return self.request.query_string

    @property
    def query_params(self):
        return self.request.args

    @property
    def body(self):
        return self.request.data

    @property
    def headers(self):
        return self.request.headers

    def get_form(self):
        form = dict(self.request.form)
        parsed_files = {}
        for key, files in self.request.files.lists():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        form.update(parsed_files)
        return form
