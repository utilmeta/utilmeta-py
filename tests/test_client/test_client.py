from utilmeta.core.cli import Client
from tests.conftest import make_live_process, make_server_thread, setup_service
from .client import TestClient, DataSchema
import pytest

setup_service(__name__, backend='django', async_param=[False])
# server_process = make_live_process(
#     backend='django',
#     port=8666
# )

server_thread = make_server_thread(
    backend='django',
    port=8666
)


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

    def test_live_server(self, server_thread):
        with TestClient(
            base_url='http://127.0.0.1:8666/api/test',
        ) as client:
            v = client.get_doc(
                category='finance',
                page=3
            )
            assert v.status == 200
            assert v.data == {'finance': 3}

            dt = client.get_data(key='test1')
            assert isinstance(dt.result, DataSchema)
            assert dt.result.key == 'test1'

    @pytest.mark.asyncio
    async def test_live_server_async(self, server_thread):
        with TestClient(
            base_url='http://127.0.0.1:8666/api/test',
        ) as client:
            v = client.get_doc(
                category='finance',
                page=3
            )
            # test sync api in async function
            assert v.status == 200
            assert v.data == {'finance': 3}

            v = await client.async_query(
                page=3,
                item='what'
            )
            assert v.data == [3, 'what']

            dt = client.get_data(key='test1')
            assert isinstance(dt.result, DataSchema)
            assert dt.result.key == 'test1'
