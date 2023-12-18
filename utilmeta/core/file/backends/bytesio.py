from .base import FileAdaptor
from io import BytesIO


class BytesIOFileAdaptor(FileAdaptor):
    file: BytesIO

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, BytesIO)

    @property
    def object(self):
        return self.file

    @property
    def size(self):
        byts = self.file.read()
        size = len(byts)
        self.file.seek(0)
        return size

    @property
    def content_type(self):
        return None

    @property
    def filename(self):
        return None
