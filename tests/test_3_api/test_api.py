from utilmeta.core import api, request, file
from utilmeta.core.api import API
from utilmeta.core import response
import pytest

from utilmeta.core.request import Request
from utilmeta.core.response import Response
from utilmeta.utils import Error
from .params import get_requests
from tests.conftest import setup_service


setup_service(__name__, backend='django')


class TestAPIClass:
    def test_request_response(self):
        resp = Response(response=Response(status=400, result='123'), cached=True)
        assert resp.status == 400
        assert resp.result == '123'
        assert resp.body == b'123'

        resp2 = Response(response=Response(status=400, result='123'), status=422)
        assert resp2.status == 422

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
            try:
                assert isinstance(resp, response.Response), f'invalid response: {resp}'
                content = resp.data
                assert resp.status == status, \
                    f"{method} {path} failed with {content}, {status} expected, got {resp.status}"
                if result is not ...:
                    if callable(result):
                        result(content)
                    else:
                        if isinstance(result, bytes):
                            result = result.decode()
                        if isinstance(content, bytes):
                            content = content.decode()
                        assert content == result, f"{method} {path} failed with {content}"
            finally:
                resp.close()

    def test_api_plugins_exc_handle(self):
        from utilmeta.core.request import Request
        from utilmeta.core.response import Response
        from utilmeta.utils import Error

        class MyPlugin(api.Plugin):
            def process_request(self, request: Request):
                raise ValueError('123')

            def process_response(self, response: Response):
                pass

            def handle_error(self, error: Error):
                pass

        @MyPlugin
        class SubAPI(api.API):
            @api.get
            def hello(self):
                return 'world'

        class RootAPI(api.API):
            sub: SubAPI

            @api.handle(SubAPI, ValueError)
            def handle_error(self, error: Error):
                return self.response(status=422, error=error)

        resp = RootAPI(Request(
            method='GET',
            url='sub/hello'
        ))()

        assert resp.status == 422
        assert resp.message == '123'

        class SubAPI2(api.API):
            @api.get
            @MyPlugin()
            def hello(self):
                return 'world'

        class ParentAPI(api.API):
            sub: SubAPI2

            @api.handle(SubAPI2, ValueError)
            def handle_error(self, error: Error):
                return self.response(status=422, error=error)

        resp2 = ParentAPI(Request(
            method='GET',
            url='sub/hello'
        ))()

        assert resp2.status == 422
        assert resp2.message == '123'

    def test_api_plugins_orders(self, service):
        if service.asynchronous:
            return

        from utilmeta.core.request import Request
        from utilmeta.core.response import Response

        class OrderPlugin(api.Plugin):
            def __init__(self, val: str):
                self.val = val
                super().__init__(locals())

            def process_request(self, request: Request, target=None):
                data = request.data
                if not data:
                    request.data = [self.val]
                elif isinstance(data, list):
                    data.append(self.val)
                assert target is not None

            def process_response(self, response: Response, target=None):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = self.val
                else:
                    response.headers['x-order'] = f'{order},{self.val}'
                assert target is not None

        def make_plugin(val) -> OrderPlugin:
            class _order(OrderPlugin):
                pass
            return _order(val)

        @make_plugin('4')
        @make_plugin('3')
        class SubAPI(api.API):
            @make_plugin('2')
            @make_plugin('1')
            @api.get
            def operation(self):
                return self.request.data

            @api.after(operation)
            def after_operation(self, response: Response):
                response.headers['x-order-tmp'] = str(response.headers.get('x-order'))

        plugin_4 = make_plugin('4')
        plugin_3 = make_plugin('3')

        @plugin_4.inject
        @plugin_3.inject
        class SubAPI2(api.API):

            @make_plugin('2')
            @make_plugin('1')
            @api.get
            def operation(self):
                return self.request.data

            @api.after(operation)
            def after_operation(self, response: Response):
                response.headers['x-order-tmp'] = str(response.headers.get('x-order'))

        class RootAPI(api.API):
            sub: SubAPI
            sub2: SubAPI2

        resp1 = RootAPI(Request(
            method='GET',
            url='sub/operation'
        ))()

        assert resp1.result == ['4', '3', '2', '1']
        assert resp1.headers.get('x-order-tmp') == '1,2'
        assert resp1.headers.get('x-order') == '1,2,3,4'

        resp2 = RootAPI(Request(
            method='GET',
            url='sub2/operation'
        ))()

        assert resp2.result == ['4', '3', '2', '1']
        assert resp2.headers.get('x-order-tmp') == '1,2,3,4'
        assert resp2.headers.get('x-order') == '1,2,3,4'

    @pytest.mark.asyncio
    async def test_api_async_plugins_orders(self, service):
        if not service.asynchronous:
            return

        from utilmeta.core.request import Request
        from utilmeta.core.response import Response

        class OrderPlugin(api.Plugin):
            def __init__(self, val: str):
                self.val = val
                super().__init__(locals())

            async def process_request(self, request: Request, target=None):
                data = request.data
                if not data:
                    request.data = [self.val]
                elif isinstance(data, list):
                    data.append(self.val)
                assert target is not None

            async def process_response(self, response: Response, target=None):
                order = response.headers.get('x-order')
                if not order:
                    response.headers['x-order'] = self.val
                else:
                    response.headers['x-order'] = f'{order},{self.val}'
                assert target is not None

        def make_plugin(val) -> OrderPlugin:
            class _order(OrderPlugin):
                pass

            return _order(val)

        @make_plugin('4')
        @make_plugin('3')
        class SubAPI(api.API):
            @make_plugin('2')
            @make_plugin('1')
            @api.get
            async def operation(self):
                return self.request.data

            @api.after(operation)
            async def after_operation(self, response: Response):
                response.headers['x-order-tmp'] = str(response.headers.get('x-order'))

        plugin_4 = make_plugin('4')
        plugin_3 = make_plugin('3')

        @plugin_4.inject
        @plugin_3.inject
        class SubAPI2(api.API):

            @make_plugin('2')
            @make_plugin('1')
            @api.get
            async def operation(self):
                return self.request.data

            @api.after(operation)
            async def after_operation(self, response: Response):
                response.headers['x-order-tmp'] = str(response.headers.get('x-order'))

        class RootAPI(api.API):
            sub: SubAPI
            sub2: SubAPI2

        resp1 = await RootAPI(Request(
            method='GET',
            url='sub/operation'
        ))()

        assert resp1.result == ['4', '3', '2', '1']
        assert resp1.headers.get('x-order-tmp') == '1,2'
        assert resp1.headers.get('x-order') == '1,2,3,4'

        resp2 = await RootAPI(Request(
            method='GET',
            url='sub2/operation'
        ))()

        assert resp2.result == ['4', '3', '2', '1']
        assert resp2.headers.get('x-order-tmp') == '1,2,3,4'
        assert resp2.headers.get('x-order') == '1,2,3,4'
