from utilmeta.core.cli import Client
from utilmeta.core.file import File
from utilmeta.core import request
from typing import List
from tests.conftest import make_live_process, make_server_thread, setup_service
import pytest
import utype

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

    def test_client_plugin_orders(self, server_thread):
        from utilmeta.core import api
        from utilmeta.core.request import Request
        from utilmeta.core.response import Response

        class OrderPlugin(api.Plugin):
            def __init__(self, val: str):
                self.val = val
                super().__init__(locals())

            def process_request(self, request: Request):
                data = request.data
                if not data:
                    request.data = self.val
                elif isinstance(data, str):
                    request.data = f'{request.data},{self.val}'

            def process_response(self, response: Response):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = self.val
                else:
                    response.headers['x-order'] = f'{order},{self.val}'

        def make_plugin(val) -> OrderPlugin:
            class _order(OrderPlugin):
                pass

            return _order(val)

        from utilmeta.core import cli

        @make_plugin('4')
        @make_plugin('3')
        class MyClient(cli.Client):
            @api.patch
            @make_plugin('2')
            @make_plugin('1')
            def content(self, data: str = request.Body(content_type='text/html', default='')) -> Response[str]:
                pass

            def process_request(self, request: Request):
                data = request.data
                if not data:
                    request.data = '0'
                elif isinstance(data, str):
                    request.data = f'{request.data},0'

            def process_response(self, response: Response):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = '0'
                else:
                    response.headers['x-order'] = f'{order},0'

        with MyClient(
            base_url='http://127.0.0.1:8666/api/test',
        ) as client:
            resp = client.content()
            assert resp.result == '0,4,3,2,1'
            assert resp.headers.get('x-order') == '1,2,3,4,0'

    @pytest.mark.asyncio
    async def test_async_client_plugin_orders(self, server_thread):
        from utilmeta.core import api
        from utilmeta.core.request import Request
        from utilmeta.core.response import Response

        class OrderPlugin(api.Plugin):
            def __init__(self, val: str):
                self.val = val
                super().__init__(locals())

            async def process_request(self, request: Request):
                data = request.data
                if not data:
                    request.data = self.val
                elif isinstance(data, str):
                    request.data = f'{request.data},{self.val}'

            async def process_response(self, response: Response):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = self.val
                else:
                    response.headers['x-order'] = f'{order},{self.val}'

        def make_plugin(val) -> OrderPlugin:
            class _order(OrderPlugin):
                pass

            return _order(val)

        from utilmeta.core import cli

        @make_plugin('4')
        @make_plugin('3')
        class MyClient(cli.Client):
            @api.patch
            @make_plugin('2')
            @make_plugin('1')
            async def content(self, data: str = request.Body(content_type='text/html', default='')) -> Response[str]:
                pass

            async def process_request(self, request: Request):
                data = request.data
                if not data:
                    request.data = '0'
                elif isinstance(data, str):
                    request.data = f'{request.data},0'

            async def process_response(self, response: Response):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = '0'
                else:
                    response.headers['x-order'] = f'{order},0'

        with MyClient(
            base_url='http://127.0.0.1:8666/api/test',
        ) as client:
            resp = await client.content()
            assert resp.result == '0,4,3,2,1'
            assert resp.headers.get('x-order') == '1,2,3,4,0'
