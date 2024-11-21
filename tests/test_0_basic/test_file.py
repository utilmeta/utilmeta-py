from utilmeta.core.file import File
from utilmeta.core.response import Response
from utilmeta.utils import file_like
from io import BytesIO
from pathlib import Path
import os


class TestFile:
    def test_bytes_file(self):
        f = File(BytesIO(b'test'))
        assert file_like(f)
        assert f.size == 4
        assert f.read() == b'test'

    def test_system_file(self):
        base_dir = Path(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server'))
        f = File(open(base_dir / 'test.txt', 'r'))
        assert f.read() == 'test-content'
        assert f.size == len('test-content')
        assert str(f.filepath) == str(base_dir / 'test.txt')
        assert f.content_type == 'text/plain'
        assert f.filename == 'test.txt'

    def test_response_file(self):
        f = File(Response({'a': 1}), filename='test.json')
        assert f.read() == b'{"a": 1}'
        assert f.size == 8
        assert f.content_type == 'application/json'
        assert f.filename == 'test.json'
