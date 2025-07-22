import datetime

import pytest
from tests.conftest import make_cmd_process, db_using
from utilmeta.core import cli
from utilmeta.ops.client import OperationsClient
from utilmeta.core.api.plugins.retry import RetryPlugin
# test import client here, client should not depend on ops models
from utilmeta.ops import __spec_version__
import os
from pathlib import Path
import django
import time
import sys

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

from tests.conftest import setup_service, make_live_process

setup_service(__name__, backend='django')
django_server_process = make_live_process(
    backend='django',
    port=9900,
    cmdline=True
)

retry = RetryPlugin(
    max_retries=5, max_retries_timeout=15, retry_interval=1.5
)

OPS_WAIT = 2.0
# add wait to make sure that the operations data are all setup


class TestOperations:
    if django.VERSION >= (4, 0):
        def test_django_operations(self, django_wsgi_process):
            time.sleep(OPS_WAIT)
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

                now = client.get('/api/v1/time/now')
                assert now.status == 200
                assert isinstance(now.data, dict)
                assert isinstance(datetime.datetime.strptime(
                    now.data.get('data'), '%Y-%m-%d %H:%M:%S'), datetime.datetime)

        def test_django_asgi_operations(self, django_asgi_process):
            time.sleep(OPS_WAIT)
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
        time.sleep(OPS_WAIT)
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
        time.sleep(OPS_WAIT)
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

    if sys.version_info >= (3, 9):
        sanic_process = make_cmd_process(
            BASE_DIR / 'sanic_site/server.py',
            cwd=BASE_DIR / 'sanic_site',
            port=9094
        )

        def test_sanic_operations(self, sanic_process):
            time.sleep(OPS_WAIT)
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
        time.sleep(OPS_WAIT)
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
        time.sleep(OPS_WAIT)
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
            plus_operation = calc.get('get')
            assert plus_operation
            assert plus_operation.get('description') == 'add api: input a, b, return a + b'

            assert paths.get('/hello', {}).get('get')
            # -- inst
            inst_resp = client.get_instances()
            inst = inst_resp.result[0]
            assert inst.language == 'python'
            assert '2.6.0' <= inst.utilmeta_version

    def test_ops_api_data(self, service, django_server_process, db_using):
        time.sleep(OPS_WAIT)
        from utilmeta.ops.schema import QuerySchema, CreateDataSchema, UpdateDataSchema
        from utilmeta.ops.config import Operations

        with OperationsClient(base_url=service.get_config(Operations).ops_api,
                              plugins=[retry], fail_silently=True) as client:
            # for using in ['default', 'postgresql', 'mysql']:
            resp = client.query_data(
                model='app.models.Article',
                using=db_using,
                data=QuerySchema(
                    query=dict(id=1)
                )
            )
            assert resp.status == 200
            assert len(resp.result) == 1
            article = resp.result[0]
            assert article.get('pk') == 1
            assert db_using in article.get('tags', [])

            # create data
            resp = client.create_data(
                model='app.models.Article',
                using=db_using,
                data=CreateDataSchema(
                    data=[dict(
                        author_id=2,
                        title="Test Happy",
                        slug="test-happy",
                        content="hello content",
                        tags=[db_using, "hello"],
                    )],
                    return_fields=['pk', 'tags']
                )
            )
            assert resp.status == 200
            assert len(resp.result) == 1
            article = resp.result[0]
            article_id = article.get('pk')
            assert article_id
            assert db_using in article.get('tags', [])

            # update data
            resp = client.update_data(
                model='app.models.Article',
                using=db_using,
                data=UpdateDataSchema(
                    data=[dict(
                        pk=article_id,
                        slug="test-new-happy",
                        tags=[db_using, "world"],
                    )],
                )
            )
            assert resp.status == 200

            # query again
            resp = client.query_data(
                model='app.models.Article',
                using=db_using,
                data=QuerySchema(
                    query=dict(id=article_id)
                )
            )
            assert resp.status == 200
            assert len(resp.result) == 1
            article = resp.result[0]
            assert article.get('pk') == article_id
            assert article.get('slug') == "test-new-happy"
            assert db_using in article.get('tags', [])
            assert "world" in article.get('tags', [])

            # delete
            resp = client.delete_data(
                model='app.models.Article',
                using=db_using,
                id=article_id,
            )
            assert resp.status == 200
            if not service.asynchronous:
                # do not check async query result
                assert resp.result == 2  # article and content instances

            # query after delete
            resp = client.query_data(
                model='app.models.Article',
                using=db_using,
                data=QuerySchema(
                    query=dict(id=article_id)
                )
            )
            assert resp.status == 200
            assert len(resp.result) == 0

            # query non-exists model
            resp = client.query_data(
                model='app.models.What',
                using=db_using,
                data=QuerySchema(
                    query=dict(id=1)
                )
            )
            assert resp.status == 400

            # query non-exists model
            resp = client.query_data(
                model='app.models.Article',
                using='none',
                data=QuerySchema(
                    query=dict(id=1)
                )
            )
            assert resp.status == 400

    def test_ops_api_servers(self, service, django_server_process):
        import platform
        time.sleep(OPS_WAIT)
        from utilmeta.ops.config import Operations

        with OperationsClient(base_url=service.get_config(Operations).ops_api,
                              plugins=[retry], fail_silently=True) as client:
            resp = client.get_servers()
            assert len(resp.result) >= 1
            server = resp.result[0]
            assert server.hostname == platform.node()

    def test_ops_api_logs(self):
        pass

    def test_ops_connect_supervisor(self):
        pass
