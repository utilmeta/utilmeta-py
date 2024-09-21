import os
from utilmeta.utils.adaptor import BaseAdaptor


class FileAdaptor(BaseAdaptor):
    def __init__(self, file):
        self.file = file

    @classmethod
    def get_module_name(cls, obj):
        from io import BytesIO
        from utilmeta.core.response.base import Response, ResponseAdaptor
        if isinstance(obj, BytesIO):
            return 'bytesio'
        elif isinstance(obj, (Response, ResponseAdaptor)) or Response.response_like(obj):
            return 'response'
        return super().get_module_name(obj)

    @property
    def object(self):
        raise NotImplementedError

    @property
    def size(self):
        raise NotImplementedError

    @property
    def content_type(self):
        raise NotImplementedError

    @property
    def filename(self):
        raise NotImplementedError

    def save(self, path: str, name: str = None):
        file_path = path
        name = name or self.filename
        if name:
            if os.path.isdir(file_path):
                file_path = os.path.join(file_path, name)

        with open(file_path, 'wb') as fp:
            fp.write(self.object.read())

        return file_path

    def close(self):
        pass
