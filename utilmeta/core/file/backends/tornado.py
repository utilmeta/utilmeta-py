from tornado.httputil import HTTPFile
from .base import FileAdaptor
from io import BytesIO


class TornadoFileAdaptor(FileAdaptor):
    file: HTTPFile

    @property
    def object(self):
        return BytesIO(self.file.body)

    @property
    def size(self):
        return len(self.file.body)

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename
