from tornado.httpserver import HTTPRequest as ServerRequest
# from tornado.httpclient import HTTPRequest as ClientRequest
from ..base import RequestAdaptor
from utilmeta.core.file.backends.tornado import TornadoFileAdaptor
from utilmeta.core.file.base import File
from utilmeta.utils import exceptions as exc
import tornado


class TornadoServerRequestAdaptor(RequestAdaptor):
    request: ServerRequest
    file_adaptor_cls = TornadoFileAdaptor
    backend = tornado

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

    # note: tornado use bytes to process query, which is not a standard way, fallback instead
    # @property
    # def query_params(self):
    #     return self.request.query_arguments

    @property
    def cookies(self):
        cookies = {}
        for key, val in self.request.cookies.items():
            cookies[val.key] = val.value
        return cookies

    async def async_read(self):
        return self.request.body

    async def async_load(self):
        try:
            return self.get_content()
        except NotImplementedError:
            raise
        except Exception as e:
            raise exc.UnprocessableEntity(f'process request body failed with error: {e}') from e

    def get_form(self):
        form = dict(self.request.body_arguments)
        parsed_files = {}
        for key, files in self.request.files.items():
            parsed_files[key] = [File(self.file_adaptor_cls(file)) for file in files]
        form.update(parsed_files)
        return form
