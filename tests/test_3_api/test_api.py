from utilmeta.core import api, request, file
from utilmeta.core.api import API
from utilmeta.core import response
import pytest
from .params import get_requests
from tests.conftest import setup_service


setup_service(__name__, backend='django')


class TestAPIClass:
    def test_invalid_declaration(self):
        with pytest.raises(TypeError):
            class _API(API):    # noqa
                @api.get
                def request(self):
                    pass

        with pytest.raises(TypeError):
            class _API(API):    # noqa
                @api.get
                def response(self):
                    pass

        with pytest.raises(Exception):
            class _API(API):    # noqa
                @api.get
                def post(self):
                    pass

        with pytest.raises(Exception):
            class _API(API):  # noqa
                @api.get
                def _route(self):
                    pass

        with pytest.raises(Exception):
            class _API(API):  # noqa
                @api.before('*')
                @api.get
                def route(self):
                    pass

        # only warns
        # with pytest.raises(Exception):
        #     class _API(API):  # noqa
        #         @api.before('no_exists')
        #         def bef(self):
        #             pass

        with pytest.raises(Exception):
            class _API(API):  # noqa
                def post(self):
                    pass

                @api.before(post)
                def get(self):
                    pass

        with pytest.raises(Exception):
            class _API(API):  # noqa
                def post(self):
                    pass

                @api.before(post)
                def _before(self):      # "_"
                    pass

        with pytest.raises(Exception):
            class _API1(API):  # noqa
                def post(self):
                    pass

            class _API2(API):  # noqa
                api1: _API1

                @api.get
                def api1(self):
                    pass

        # with pytest.raises(Exception):
        #     class _API1(API):  # noqa
        #         def post(self):
        #             pass
        #
        #     class _API2(API):  # noqa
        #         api1: _API1
        #
        #         @api.get('api1')
        #         def api_func(self):
        #             pass

        with pytest.raises(Exception):
            class WrongAPI(API):  # noqa
                @api.get
                def post(self):  # HTTP-METHOD function with conflict @api
                    pass

        # ------------ wrong params
        with pytest.raises(Exception):
            class WrongAPI(API):  # noqa
                @api.get
                def file(self, f: file.File):  # HTTP-METHOD function with conflict @api
                    pass

    def test_api_features(self):
        from api import TestAPI
        # from service.api import RootAPI

        for method, path, query, body, headers, result, status in get_requests():
            h = dict(headers)
            h.update({
                'X-Common-State': 1
            })
            resp = TestAPI(
                request.Request(
                    method=method,
                    url=path,
                    query=query,
                    data=body,
                    headers=h,
                )
            )()
            assert isinstance(resp, response.Response), f'invalid response: {resp}'
            content = resp.data
            assert resp.status == status, \
                f"{method} {path} failed with {content}, {status} expected, got {resp.status}"
            if result is not ...:
                if callable(result):
                    result(content)
                else:
                    assert content == result, f"{method} {path} failed with {content}"
