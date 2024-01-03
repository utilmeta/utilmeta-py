import os
from utilmeta.utils.adaptor import BaseAdaptor


class FileAdaptor(BaseAdaptor):
    def __init__(self, file):
        self.file = file

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
            file_path = os.path.join(file_path, name)

        with open(file_path, 'wb') as fp:
            fp.write(self.file)

        return file_path
