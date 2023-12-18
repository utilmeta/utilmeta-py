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

    def save(self, path: str):
        raise NotImplementedError
