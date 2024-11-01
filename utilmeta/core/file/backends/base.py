import os
from utilmeta.utils.adaptor import BaseAdaptor
import inspect


class FileAdaptor(BaseAdaptor):
    def __init__(self, file):
        self.file = file
        self.object = self.get_object()

    @classmethod
    def get_module_name(cls, obj):
        from io import BytesIO, TextIOWrapper, BufferedRandom, BufferedReader
        from utilmeta.core.response.base import Response, ResponseAdaptor
        if isinstance(obj, BytesIO):
            return 'bytesio'
        elif isinstance(obj, (BufferedReader, BufferedRandom, TextIOWrapper)):
            return 'fileio'
        elif isinstance(obj, (Response, ResponseAdaptor)) or Response.response_like(obj):
            return 'response'
        return super().get_module_name(obj)

    def get_object(self):
        return self.file

    @property
    def size(self):
        if self.seekable:
            current_position = self.object.tell()
            self.object.seek(0, os.SEEK_END)
            size = self.object.tell()
            self.object.seek(current_position)
            return size
        return 0

    @property
    def seekable(self):
        return hasattr(self.object, "seek") and (
            not hasattr(self.object, "seekable") or self.object.seekable()
        )

    @property
    def content_type(self):
        raise NotImplementedError

    @property
    def filename(self):
        raise NotImplementedError

    @property
    def filepath(self):
        return None

    def save(self, path: str, name: str = None):
        file_path = path
        name = name or self.filename
        if name:
            if not os.path.exists(file_path):
                os.makedirs(file_path, exist_ok=True)
            if os.path.isdir(file_path):
                file_path = os.path.join(file_path, name)
        else:
            if os.path.isdir(file_path):
                raise PermissionError(f'Attempt to write file to directory: {file_path}')
        with open(file_path, 'wb') as fp:
            if self.seekable:
                self.object.seek(0)
            content = self.object.read()
            if isinstance(content, str):
                content = content.encode()
            fp.write(content)

        return file_path

    async def asave(self, path: str, name: str = None):
        file_path = path
        name = name or self.filename
        if name:
            if not os.path.exists(file_path):
                os.makedirs(file_path, exist_ok=True)
            if os.path.isdir(file_path):
                file_path = os.path.join(file_path, name)

        with open(file_path, 'wb') as fp:
            if self.seekable:
                r = self.object.seek(0)
                if inspect.isawaitable(r):
                    await r
            content = self.object.read()
            if inspect.isawaitable(content):
                content = await content
            if isinstance(content, str):
                content = content.encode()
            fp.write(content)

        return file_path

    def close(self):
        if hasattr(self.object, 'close'):
            try:
                self.object.close()
            except Exception:    # noqa
                pass
