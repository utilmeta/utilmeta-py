from utilmeta.core.cli import Client
from utilmeta.core.file import File
from utilmeta.core import request
from utilmeta.core.api import Retry
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
import httpx
import aiohttp
import requests
import urllib


@pytest.fixture(params=[urllib, requests, httpx])
def sync_request_backend(request):
    return request.param


@pytest.fixture(params=[httpx, aiohttp])
def async_request_backend(request):
    return request.param


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

        client2 = Client(
            base_url='https://test.com/path?q1=v1',
            base_query={'q0': 'v0'},
            append_slash=True
        )
        assert client2._build_url(
            path='sub?q2=v2',
            query={'q3': 'v3'}
        ) == 'https://test.com/path/sub/?q0=v0&q1=v1&q2=v2&q3=v3'

    def test_live_server(self, server_thread, sync_request_backend):
        with TestClient(
            base_url='http://127.0.0.1:8666/api/test',
            backend=sync_request_backend,
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
            # assert tr.status == 500
            # assert 'MaxRetriesTimeoutExceed' in tr.text
            assert f'retry: 2' in tr.text

    def test_live_server_with_mount(self, server_thread, sync_request_backend):
        with APIClient(
            base_url='http://127.0.0.1:8666/api',
            backend=sync_request_backend,
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
    async def test_live_server_async(self, server_thread, async_request_backend):
        with TestClient(
            base_url='http://127.0.0.1:8666/api/test',
            backend=async_request_backend,
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

    def test_request_failure(self, sync_request_backend):
        with TestClient(
            base_url='http://127.0.0.1:1',
            backend=sync_request_backend,
            default_timeout=0.5
        ) as client:
            with pytest.raises(Exception):
                client.get_doc(category='test')

        with TestClient(
            base_url='http://127.0.0.1:1',
            backend=sync_request_backend,
            default_timeout=0.5,
            fail_silently=True
        ) as client:
            resp = client.get_doc(category='test')
            assert resp.status == 500
            assert resp.is_aborted

    def test_request_retry(self):
        # test retry
        retry1 = Retry(
            max_retries=3, max_retries_timeout=5, retry_interval=0.1
        )
        retry2 = Retry(
            max_retries=100, max_retries_timeout=0.5, retry_interval=0.1
        )
        with TestClient(
            base_url='http://127.0.0.1:1',
            default_timeout=0.2,
            plugins=[retry1],
            fail_silently=True
        ) as client:
            resp = client.get_doc(category='test')
            retry_index = resp.request.adaptor.get_context('retry_index')
            assert retry_index == 2
            # retry stop at max_retries

        with TestClient(
            base_url='http://127.0.0.1:1',
            default_timeout=0.2,
            plugins=[retry2],
        ) as client:
            with pytest.raises(Exception) as e:
                assert "timeout" in str(e).lower() or "timed out" in str(e).lower()
                client.get_doc(category='test')
                # retry stop at max_retries

    @pytest.mark.asyncio
    async def test_request_async_retry(self):
        # test retry
        retry1 = Retry(
            max_retries=3, max_retries_timeout=5, retry_interval=0.1
        )
        retry2 = Retry(
            max_retries=100, max_retries_timeout=0.5, retry_interval=0.1
        )
        with TestClient(
            base_url='http://127.0.0.1:1',
            default_timeout=0.2,
            plugins=[retry1],
            fail_silently=True
        ) as client:
            resp = await client.aget_doc(category='test')
            retry_index = resp.request.adaptor.get_context('retry_index')
            assert retry_index == 2
            # retry stop at max_retries

        with TestClient(
            base_url='http://127.0.0.1:1',
            default_timeout=0.2,
            plugins=[retry2],
        ) as client:
            with pytest.raises(Exception) as e:
                assert "timeout" in str(e).lower() or "timed out" in str(e).lower()
                await client.aget_doc(category='test')
                # retry stop at max_retries

    @pytest.mark.asyncio
    async def test_async_request_failure(self, async_request_backend):
        with TestClient(
            base_url='http://127.0.0.1:1',
            backend=async_request_backend,
            default_timeout=0.5
        ) as client:
            with pytest.raises(Exception):
                await client.aget_doc(category='test')

        with TestClient(
            base_url='http://127.0.0.1:1',
            backend=async_request_backend,
            default_timeout=0.5,
            fail_silently=True
        ) as client:
            resp = await client.aget_doc(category='test')
            assert resp.status == 500
            assert resp.is_aborted
