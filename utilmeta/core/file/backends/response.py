from .base import FileAdaptor
from utilmeta.core.response import Response
from utilmeta.core.response.base import ResponseAdaptor


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
        file = self.file.file
        if file:
            return file.file
        from io import BytesIO
        return BytesIO(self.file.body)

    @property
    def size(self):
        return self.file.content_length

    @property
    def content_type(self):
        return self.file.content_type

    @property
    def filename(self):
        return self.file.filename

    def close(self):
        self.file.close()
