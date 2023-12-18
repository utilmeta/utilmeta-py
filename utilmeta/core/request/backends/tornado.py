from tornado.httpserver import HTTPRequest as ServerRequest
# from tornado.httpclient import HTTPRequest as ClientRequest
from ..base import RequestAdaptor
from utilmeta.core.file.backends.tornado import TornadoFileAdaptor
from utilmeta.core.file.base import File


class TornadoServerRequestAdaptor(RequestAdaptor):
    request: ServerRequest
    file_adaptor_cls = TornadoFileAdaptor

    @classmethod
    def reconstruct(cls, adaptor: 'RequestAdaptor') -> ServerRequest:
        if isinstance(adaptor, cls):
            return adaptor.request
        raise ServerRequest(
            method=adaptor.method,
            uri=adaptor.url,
            headers=adaptor.headers,
            body=adaptor.body,
        )

    @property
    def request_method(self):
        return self.request.method

    @property
    def url(self):
        return self.request.full_url()

    @property
    def body(self):
        return self.request.body

    @property
    def headers(self):
        return self.request.headers

    @property
    def query_params(self):
        return self.request.query_arguments

    def get_form(self):
        form = dict(self.request.body_arguments)
        parsed_files = {}
        for key, files in self.request.files.items():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        form.update(parsed_files)
        return form
