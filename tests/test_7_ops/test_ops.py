import pytest
from tests.conftest import make_cmd_process, db_using
from utilmeta.core import cli
from utilmeta.ops.client import OperationsClient
from utilmeta.core.api.plugins.retry import RetryPlugin
# test import client here, client should not depend on ops models
import utilmeta
from utilmeta.ops import __spec_version__
import os
from pathlib import Path
import django

BASE_DIR = Path(os.path.dirname(__file__))

django_wsgi_process = make_cmd_process(
    BASE_DIR / 'django_site/manage.py',
    cwd=BASE_DIR / 'django_site',
    port=9091
)
django_asgi_process = make_cmd_process(
    BASE_DIR / 'django_asgi_site/main.py',
    cwd=BASE_DIR / 'django_asgi_site',
    port=9100
)
fastapi_process = make_cmd_process(
    BASE_DIR / 'fastapi_site/server.py',
    cwd=BASE_DIR / 'fastapi_site',
    port=9092
)
flask_process = make_cmd_process(
    BASE_DIR / 'flask_site/server.py',
    cwd=BASE_DIR / 'flask_site',
    port=9093
)
sanic_process = make_cmd_process(
    BASE_DIR / 'sanic_site/server.py',
    cwd=BASE_DIR / 'sanic_site',
    port=9094
)
tornado_process = make_cmd_process(
    BASE_DIR / 'tornado_site/server.py',
    cwd=BASE_DIR / 'tornado_site',
    port=9095
)
utilmeta_process = make_cmd_process(
    BASE_DIR / 'utilmeta_site/server.py',
    cwd=BASE_DIR / 'utilmeta_site',
    port=9090
)

retry = RetryPlugin(
    max_retries=3, max_retries_timeout=15, retry_interval=1
)


class TestOperations:
    if django.VERSION >= (4, 0):
        def test_django_operations(self, django_wsgi_process):
            with OperationsClient(
                base_url='http://127.0.0.1:9091/ops',
                plugins=[retry]
            ) as client:
                info = client.get_info()
                assert info.result.utilmeta == __spec_version__

                openapi_resp = client.get_openapi()
                assert openapi_resp.status == 200
                assert openapi_resp.result.openapi
                assert openapi_resp.result.info.title
                assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9091'
                paths = openapi_resp.result.paths
                users = paths.get('/users/') or paths.get('/users')
                assert users
                assert users.get('get')
                add = paths.get('/api-ninja/add')
                assert add
                assert add.get('get')

                # -- tables
                table_resp = client.get_tables()
                assert len(table_resp.result) > 0
                for table in table_resp.result:
                    assert table.model_backend == 'django'

                # -- inst
                inst_resp = client.get_instances()
                inst = inst_resp.result[0]
                assert inst.backend == 'django'
                assert inst.language == 'python'
                # assert inst.backend_version == django.__version__
                # maybe the instance is cached in local, we just don't test it for now
                assert '2.6.0' <= inst.utilmeta_version

            with cli.Client(base_url='http://127.0.0.1:9091') as client:
                add = client.get('/api-ninja/add?a=1&b=2')
                assert add.status == 200
                data = add.data
                assert isinstance(data, dict) and data.get('result') == 3

        def test_django_asgi_operations(self, django_asgi_process):
            with OperationsClient(
                base_url='http://127.0.0.1:9100/ops',
                plugins=[retry]
            ) as client:
                info = client.get_info()
                assert info.result.utilmeta == __spec_version__

                openapi_resp = client.get_openapi()
                assert openapi_resp.status == 200
                assert openapi_resp.result.openapi
                assert openapi_resp.result.info.title
                assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9100'
                paths = openapi_resp.result.paths
                users = paths.get('/users/') or paths.get('/users')
                assert users
                assert users.get('get')

                # -- tables
                table_resp = client.get_tables()
                assert len(table_resp.result) > 0
                for table in table_resp.result:
                    assert table.model_backend == 'django'

                # -- inst
                inst_resp = client.get_instances()
                inst = inst_resp.result[0]
                assert inst.backend == 'django'
                assert inst.asynchronous is True
                assert inst.language == 'python'
                # assert inst.backend_version == django.__version__
                # maybe the instance is cached in local, we just don't test it for now
                assert '2.6.0' <= inst.utilmeta_version

    def test_fastapi_operations(self, fastapi_process):
        with OperationsClient(base_url='http://127.0.0.1:9092/api/v1/ops', base_headers={
            'cache-control': 'no-cache'
        }, plugins=[retry]) as client:
            info = client.get_info()
            assert info.result.utilmeta == __spec_version__

            openapi_resp = client.get_openapi()
            assert openapi_resp.status == 200
            assert openapi_resp.result.openapi
            assert openapi_resp.result.info.title
            assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9092/api'
            paths = openapi_resp.result.paths
            item = paths.get('/items/{item_id}')
            assert item
            assert item.get('get')
            item = paths.get('/hello')
            assert item
            assert item.get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            # import fastapi
            assert inst.backend == 'fastapi'
            assert inst.language == 'python'
            # assert inst.backend_version == fastapi.__version__
            assert '2.6.0' <= inst.utilmeta_version

        with cli.Client(base_url='http://127.0.0.1:9092') as client:
            hello = client.get('/hello')
            assert hello.status == 200
            assert 'world' in hello.data
            not_found = client.get('/v1/not_found')
            assert not_found.status == 404
            assert 'Not Found' in str(not_found.data)

    def test_flask_operations(self, flask_process):
        with OperationsClient(base_url='http://127.0.0.1:9093/ops', base_headers={
            'cache-control': 'no-cache'
        }, plugins=[retry]) as client:
            info = client.get_info()
            assert info.result.utilmeta == __spec_version__

            openapi_resp = client.get_openapi()
            assert openapi_resp.status == 200
            assert openapi_resp.result.openapi
            assert openapi_resp.result.info.title
            assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9093'
            paths = openapi_resp.result.paths
            item = paths.get('/pets/{pet_id}')
            assert item
            assert item.get('get')
            item = paths.get('/hello')
            assert item
            assert item.get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            # import flask
            assert 'flask' in inst.backend
            # apiflask
            assert inst.language == 'python'
            assert '2.6.0' <= inst.utilmeta_version

        with cli.Client(base_url='http://127.0.0.1:9093') as client:
            hello = client.get('/hello')
            assert hello.status == 200
            assert 'Hello' in str(hello.data)

    def test_sanic_operations(self, sanic_process):
        with OperationsClient(base_url='http://127.0.0.1:9094/ops', base_headers={
            'cache-control': 'no-cache'
        }, plugins=[retry]) as client:
            info = client.get_info()
            assert info.result.utilmeta == __spec_version__

            openapi_resp = client.get_openapi()
            assert openapi_resp.status == 200
            assert openapi_resp.result.openapi
            assert openapi_resp.result.info.title
            assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9094'
            paths = openapi_resp.result.paths
            item = paths.get('/sanic')
            assert item
            assert item.get('get')

            calc = paths.get('/calc/add')
            assert calc
            assert calc.get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            # import sanic
            assert inst.backend == 'sanic'
            # assert inst.backend_version == sanic.__version__
            assert inst.language == 'python'
            assert '2.6.0' <= inst.utilmeta_version

        with cli.Client(base_url='http://127.0.0.1:9094') as client:
            hello = client.get('/sanic')
            assert hello.status == 200
            assert 'Hello' in str(hello.data)

    def test_tornado_operations(self, tornado_process):
        with OperationsClient(base_url='http://127.0.0.1:9095/v1/ops', plugins=[retry]) as client:
            info = client.get_info()
            assert info.result.utilmeta == __spec_version__

            openapi_resp = client.get_openapi()
            assert openapi_resp.status == 200
            assert openapi_resp.result.openapi
            assert openapi_resp.result.info.title
            assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9095'
            paths = openapi_resp.result.paths

            calc = paths.get('/calc/add') or paths.get('/calc/add/')
            assert calc
            assert calc.get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            assert inst.backend == 'tornado'
            assert inst.language == 'python'
            assert '2.6.0' <= inst.utilmeta_version

    def test_utilmeta_operations(self, utilmeta_process):
        with OperationsClient(base_url='http://127.0.0.1:9090/api/ops', plugins=[retry]) as client:
            info = client.get_info()
            assert info.result.utilmeta == __spec_version__

            openapi_resp = client.get_openapi()
            assert openapi_resp.status == 200
            assert openapi_resp.result.openapi
            assert openapi_resp.result.info.title
            assert openapi_resp.result.servers[0].url == 'http://127.0.0.1:9090/api'
            paths = openapi_resp.result.paths

            calc = paths.get('/add') or paths.get('/add/')
            assert calc
            assert calc.get('get')
            assert paths.get('/hello', {}).get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            assert inst.language == 'python'
            assert '2.6.0' <= inst.utilmeta_version
