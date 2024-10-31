from starlette.datastructures import UploadFile
from .base import FileAdaptor


class StarletteFileAdaptor(FileAdaptor):
    file: UploadFile

    def get_object(self):
        return self.file.file

    @property
    def size(self):
        return self.file.size

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename

    def close(self):
        return self.object.close()
