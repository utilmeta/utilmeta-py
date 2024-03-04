from utilmeta.core.cli import Client


class TestClientClass:
    def test_build_url(self):
        client1 = Client(
            base_url='https://test.com/path',
            append_slash=True
        )
        assert client1._build_url(
            path='sub?k1=v1',
            query={'k2': 'v2'}
        ) == 'https://test.com/path/sub/?k1=v1&k2=v2'

        assert client1._build_url(
            path='https://test2.com/sub?k1=v1',
            query={'k2': 'v2'}
        ) == 'https://test2.com/sub/?k1=v1&k2=v2'
