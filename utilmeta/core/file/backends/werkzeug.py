from werkzeug.datastructures import FileStorage
from .base import FileAdaptor


class WerkzeugFileAdaptor(FileAdaptor):
    file: FileStorage

    @property
    def object(self):
        return self.file.stream

    @property
    def size(self):
        length = self.file.content_length
        if length:
            return length
        size = len(self.file.stream.read())
        self.file.stream.seek(0)
        return size

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename

    def close(self):
        self.file.close()
