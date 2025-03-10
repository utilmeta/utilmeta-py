from .base import FileAdaptor
from utilmeta.core.response import Response
from utilmeta.core.response.base import ResponseAdaptor
from urllib.parse import urlsplit


class ResponseFileAdaptor(FileAdaptor):
    file: Response

    def __init__(self, file):
        if isinstance(file, Response):
            self.response = file
        else:
            self.response = Response(response=file)
        super().__init__(file)

    @classmethod
    def qualify(cls, obj):
        if isinstance(obj, Response):
            return True
        try:
            ResponseAdaptor.dispatch(obj)
        except NotImplementedError:
            return False
        return True

    def get_object(self):
        file = self.response.file
        if file:
            return file.file
        from io import BytesIO
        return BytesIO(self.response.body)

    @property
    def size(self):
        length = self.response.content_length
        if length:
            return length
        return super().size

    @property
    def content_type(self):
        return self.response.content_type

    @property
    def filename(self):
        filename = self.response.filename
        if filename:
            return filename
        url = self.response.url
        if isinstance(url, str):
            parsed = urlsplit(url)
            if parsed.path:
                return parsed.path.split('/')[-1]
        return ''

    def close(self):
        self.response.close()
