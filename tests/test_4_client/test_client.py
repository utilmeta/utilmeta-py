from utilmeta.core.cli import Client
from utilmeta.core.file import File
from tests.conftest import make_live_process, make_server_thread, setup_service
import pytest

setup_service(__name__, backend='django', async_param=[False])
# server_process = make_live_process(
#     backend='django',
#     port=8666
# )
from tests.server.client import TestClient, APIClient, DataSchema
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

            # assert client.get_asynchronous().data == ('async' if service.asynchronous else 'sync')

            # test file
            fr = client.get_file(content='test-content-1')
            assert fr.status == 200
            file = File(fr)
            assert file.size == len('test-content-1')
            assert file.read() == b'test-content-1'

            #
            tr = client.get_retry()
            assert tr.status == 500
            assert 'MaxRetriesTimeoutExceed' in tr.text

    def test_live_server_with_mount(self, server_thread):
        with APIClient(
            base_url='http://127.0.0.1:8666/api',
        ) as client:
            v = client.test.get_doc(
                category='finance',
                page=3
            )
            assert v.status == 200
            assert v.data == {'finance': 3}
            assert v.headers['test-response-header'] == 'test'

            pg = client.test.query_schema(
                query={'page': 3, 'item': 'test'}
            )
            assert pg.status == 200
            assert pg.result.page == 3
            assert pg.result.item == 'test'

            assert pg.headers['test-response-header'] == 'test'

    @pytest.mark.asyncio
    async def test_live_server_async(self, server_thread):
        with TestClient(
            base_url='http://127.0.0.1:8666/api/test',
        ) as client:
            v = await client.aget_doc(
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

            dt = await client.aget_data(key='test1')
            assert isinstance(dt.result, DataSchema)
            assert dt.result.key == 'test1'

            # assert client.get_asynchronous().data == ('async' if service.asynchronous else 'sync')
