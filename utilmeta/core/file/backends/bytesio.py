from .base import FileAdaptor
from io import BytesIO


class BytesIOFileAdaptor(FileAdaptor):
    file: BytesIO

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, BytesIO)

    @property
    def content_type(self):
        return None

    @property
    def filename(self):
        return None

    def close(self):
        self.file.close()
