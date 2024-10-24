from utilmeta.core.cli import Client
from tests.conftest import make_server_thread, setup_service
from client import UserClient
import pytest

setup_service(__name__, backend='django', async_param=[False])

server_thread = make_server_thread(
    backend='django',
    port=8555
)


class TestLiveAuth:
    def test_live_auth(self, server_thread):
        with UserClient(
            base_url='http://127.0.0.1:8555/api/user',
        ) as client:
            # test
            v = client.jwt_login(
                username='alice',
                password="alice123",
            )
            assert v.status == 200
            assert v.result.jwt_token is not None
            assert v.result.username == 'alice'
            assert v.result.id == 1

            token = v.result.jwt_token
            r2 = client.jwt_get(token=f'bearer {token}')
            assert r2.status == 200
            assert r2.result.id == 1
            assert r2.result.username == 'alice'

            # test 401
            r401 = client.session_get()
            assert r401.status == 401
            # -----

            # test Session
            v = client.session_login(
                username='alice',
                password="alice123",
            )
            assert v.status == 200
            assert v.result.username == 'alice'
            assert v.result.id == 1

            r1 = client.session_get()
            assert r1.status == 200
            assert r1.result.id == 1
            assert r1.result.username == 'alice'

            pr = client.update_user(
                avatar='path/to/new/avatar'
            )
            assert pr.status == 200
            assert pr.result.id == 1
            assert pr.result.avatar == 'path/to/new/avatar'

            ro = client.session_logout()
            assert ro.status == 200

            # test 401
            r401 = client.session_get()
            assert r401.status == 401
            # -----
