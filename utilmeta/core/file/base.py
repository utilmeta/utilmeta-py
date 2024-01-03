from io import BytesIO
from .backends.base import FileAdaptor
import utype
from typing import Type
from utilmeta.utils.exceptions import UnprocessableEntity

__all__ = ['File', 'Image', 'Audio', 'Video', 'FileType']


class InvalidFileType(UnprocessableEntity):
    pass


class File:
    file: BytesIO

    encoding = property(lambda self: self.file.encoding)
    fileno = property(lambda self: self.file.fileno)
    flush = property(lambda self: self.file.flush)
    isatty = property(lambda self: self.file.isatty)
    newlines = property(lambda self: self.file.newlines)
    read = property(lambda self: self.file.read)
    readinto = property(lambda self: self.file.readinto)
    readline = property(lambda self: self.file.readline)
    readlines = property(lambda self: self.file.readlines)
    seek = property(lambda self: self.file.seek)
    tell = property(lambda self: self.file.tell)
    truncate = property(lambda self: self.file.truncate)
    write = property(lambda self: self.file.write)
    writelines = property(lambda self: self.file.writelines)

    # -------
    max_length = None
    type = None

    def __init__(self, file):
        if isinstance(file, File):
            self.adaptor = file.adaptor
            self.file = file.file
        elif isinstance(file, BytesIO):
            from .backends.bytesio import BytesIOFileAdaptor
            self.adaptor = BytesIOFileAdaptor(file)
            self.file = file
        else:
            self.adaptor = FileAdaptor.dispatch(file)
            self.file = self.adaptor.object
        self.validate()

    def validate(self):
        pass

    @property
    def closed(self):
        return not self.file or self.file.closed

    def readable(self):
        if self.closed:
            return False
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True

    def writable(self):
        if self.closed:
            return False
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")

    def seekable(self):
        if self.closed:
            return False
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return True

    def save(self, path: str, name: str = None):
        return self.adaptor.save(path, name)

    async def asave(self, path: str, name: str = None):
        pass

    def __iter__(self):
        return iter(self.file)

    def __len__(self):
        return self.size

    @property
    def content_type(self) -> str:
        return self.adaptor.content_type

    @property
    def filename(self) -> str:
        return self.adaptor.filename

    @property
    def size(self) -> int:
        return self.adaptor.size

    @property
    def suffix(self) -> str:
        if '.' in self.filename:
            return str(self.filename.split('.')[-1]).lower()
        type = self.content_type
        if not type:
            return ''
        if '/' in type:
            return str(type.split('/')[1]).lower()
        return type.lower()

    @property
    def is_image(self):
        return self.content_type.startswith('image')

    @property
    def is_audio(self):
        return self.content_type.startswith('audio')

    @property
    def is_video(self):
        return self.content_type.startswith('video')


class Image(File):
    def validate(self):
        if not self.content_type or not self.is_image:
            raise InvalidFileType(f'Invalid file type: {repr(self.content_type)}, image expected')


class Audio(File):
    def validate(self):
        if not self.content_type or not self.is_audio:
            raise InvalidFileType(f'Invalid file type: {repr(self.content_type)}, audio expected')


class Video(File):
    def validate(self):
        if not self.content_type or not self.is_video:
            raise InvalidFileType(f'Invalid file type: {repr(self.content_type)}, video expected')


def FileType(content_type: str):
    if '/' in content_type:
        content_class, suffix = content_type.split('/')
    else:
        content_class, suffix = content_type, None

    class FileCls(File):
        def validate_type(self):
            if self.content_type:
                if '/' in self.content_type:
                    cc, suf = self.content_type.split('/')
                    if content_class != '*':
                        if content_class != cc:
                            return False
                    if suffix not in (None, '*'):
                        if suf != suffix:
                            return False
                    return True
            return False

        def validate(self):
            if not self.validate_type():
                raise InvalidFileType(f'Invalid file type: {repr(self.content_type)}, video expected')

    return FileCls


@utype.register_transformer(File)
def transform_file(transformer, file, cls: Type[File]):
    if isinstance(file, (list, tuple)) and file:
        file = file[0]
    if file is None:
        raise TypeError('Invalid file: None')
    if isinstance(file, cls):
        return cls(file.adaptor)
    return cls(file)
