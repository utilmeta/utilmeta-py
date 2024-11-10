from aiohttp.web_request import FileField
from .base import FileAdaptor


class AiohttpFileAdaptor(FileAdaptor):
    file: FileField

    def get_object(self):
        return self.file.file

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename

    def close(self):
        pass
