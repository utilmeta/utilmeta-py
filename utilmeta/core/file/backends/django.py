from django.core.files.uploadedfile import UploadedFile
from .base import FileAdaptor


class DjangoFileAdaptor(FileAdaptor):
    file: UploadedFile

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, UploadedFile)

    @property
    def object(self):
        return self.file.file

    @property
    def size(self):
        return self.file.size

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.name

    def close(self):
        self.file.close()
