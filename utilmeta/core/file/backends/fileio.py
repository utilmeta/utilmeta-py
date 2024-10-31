from typing import Union
from utilmeta.utils import guess_mime_type
from io import TextIOWrapper, BufferedReader, BufferedRandom
from utilmeta.core.file.backends.base import FileAdaptor
import os
from pathlib import Path


class FileIOAdaptor(FileAdaptor):
    file: Union[BufferedReader, BufferedRandom, TextIOWrapper]

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, (BufferedReader, BufferedRandom, TextIOWrapper))

    @property
    def size(self):
        if self.file.name:
            try:
                return os.path.getsize(self.file.name)
            except FileNotFoundError:
                pass
        return super().size

    @property
    def content_type(self):
        t, encoding = guess_mime_type(self.file.name)
        return t

    @property
    def filename(self):
        path, name = os.path.split(self.file.name)
        return name

    @property
    def filepath(self):
        path = self.file.name
        if not os.path.isabs(path):
            return Path(os.getcwd()) / path
        return Path(path)

    def close(self):
        self.file.close()
