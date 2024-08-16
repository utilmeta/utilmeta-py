from .base import FileAdaptor
from sanic.request.form import File
from io import BytesIO


class SanicFileAdaptor(FileAdaptor):
    file: File

    @property
    def object(self):
        return BytesIO(self.file.body)

    @property
    def size(self):
        return len(self.file.body)

    @property
    def content_type(self):
        return self.file.type

    @property
    def filename(self):
        return self.file.name

    def close(self):
        pass
