from utilmeta.core.file import File
from utilmeta.utils import file_like
from io import BytesIO


class TestFile:
    def test_file(self):
        f = File(BytesIO(b'test'))
        assert file_like(f)
        assert f.size == 4
        assert f.read() == b'test'

