from typing import Union
from utilmeta.utils import guess_mime_type
from io import TextIOWrapper, BufferedReader, BufferedRandom
from utilmeta.core.file.backends.base import FileAdaptor


class FileIOAdaptor(FileAdaptor):
    file: Union[BufferedReader, BufferedRandom, TextIOWrapper]

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, (BufferedReader, BufferedRandom, TextIOWrapper))

    @property
    def object(self):
        return self.file

    @property
    def size(self):
        if self.file.name:
            try:
                import os
                return os.path.getsize(self.file.name)
            except FileNotFoundError:
                pass
        self.file.seek(0)
        byts = self.file.read()
        size = len(byts)
        self.file.seek(0)
        return size

    @property
    def content_type(self):
        t, encoding = guess_mime_type(self.file.name)
        return t

    @property
    def filename(self):
        return self.file.name

    def close(self):
        self.file.close()
