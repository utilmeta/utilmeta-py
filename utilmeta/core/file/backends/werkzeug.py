from werkzeug.datastructures import FileStorage
from .base import FileAdaptor


class WerkzeugFileAdaptor(FileAdaptor):
    file: FileStorage

    @property
    def object(self):
        return self.file.stream

    @property
    def size(self):
        return self.file.content_length

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename
