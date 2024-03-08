from io import BytesIO
from utilmeta.core import api, request
from utilmeta.core.api import API
from utilmeta.core import response
import pytest


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

    # def test_hooks(self):
    #     class HookAPI(API):
    #         def __init__(self, *args, **kwargs):
    #             super().__init__(*args, **kwargs)
    #             self.meta_token = None
    #
    #         def post(self, data: Dict[int, bool] = request.Body):
    #             if not data:
    #                 raise exc.UnprocessableEntity
    #             return data
    #
    #         @api.get
    #         def token(self):
    #             return self.meta_token
    #
    #         @api.before(post)
    #         def handle_post(self):
    #             self.request.data = self.request.query
    #
    #         @api.after(token, post)
    #         def process_result(self, r: Response.http):
    #             r["token"] = self.meta_token or "none"
    #             # test not return
    #
    #         @api.before("*", excludes=post)
    #         def process_token(self, x_meta_token: str = Rule(length=12)):
    #             self.meta_token = x_meta_token
    #
    #         @api.handle("*", exc.BadRequest)
    #         def handle_bad_request(self, e: Error):
    #             return self.response(str(e.type), message=e, status=e.status)
    #
    #         @api.handle("*", exc.UnprocessableEntity, exc.Unauthorized, excludes=token)
    #         def handle_data(self, e: Error):
    #             self.request.log.warn(e.message)
    #             return e  # test error result
    #
    #         @api.handle(post)  # handle all exception
    #         def handle_post_all(self, e: Error):
    #             raise e.throw(prepend="post error:")
    #
    #     req = request.Request(method='get', url='token', headers={"X-Meta-Token": "x" * 12})
    #     hook = HookAPI(req)
    #     assert hook.token() is None  # no before hook is set
    #     hook1 = HookAPI(
    #         Request.custom("get", path="token", headers={"X-Meta-Token": "x" * 12})
    #     )
    #
    #     resp = hook1()
    #     assert Response.get_content(resp) == "x" * 12
    #     assert resp["token"] == "x" * 12  # test after hook
    #     assert hook1.meta_token == "x" * 12
    #
    #     hook2 = HookAPI(Request.custom("post", query={"4": 0}, user_id=1))
    #     resp = hook2()
    #     assert Response.get_content(resp) == {"4": False}
    #     assert resp["token"] == "none"
    #     err_resp = HookAPI(
    #         Request.custom("get", path="token", headers={"X-Meta-Token": "x" * 10})
    #     )()
    #     assert "BadRequest" in Response.get_content(err_resp)
    #     assert err_resp.status_code == 400
    #     err_resp = HookAPI(Request.custom("post"))()
    #     assert "Unauthorized" in Response.get_content(err_resp)
    #     err_resp = HookAPI(Request.custom("post", user_id=1))()
    #     assert "UnprocessableEntity" in Response.get_content(err_resp)

    def test_api_features(self):
        from .api import TestAPI
        # from service.api import RootAPI
        from django.core.files.uploadedfile import UploadedFile
        from utilmeta.core.file.backends.django import DjangoFileAdaptor       # noqa

        image = UploadedFile(BytesIO(b"image"), content_type="image/png", size=6)
        files = [
            UploadedFile(BytesIO(b"f1"), content_type="image/png", size=2),
            UploadedFile(BytesIO(b"f2"), content_type="image/png", size=2),
            UploadedFile(BytesIO(b"f3"), content_type="image/png", size=2),
        ]

        requests = [
            # (method, path, query, data, headers, result, status)
            ("get", "@special", {}, None, {}, "@special", 200),
            (
                "post",
                "response",
                dict(status=201),
                None,
                {},
                {
                    "data": "response",
                    "code": 1,
                    "error": "default",
                },
                201,
            ),
            ("get", "patch", {}, None, {}, "patch", 200),
            ("delete", "patch", {}, None, {}, "patch", 200),
            ("get", "doc/tech", {}, None, {}, {"tech": 1}, 200),
            ("get", "doc/tech/3", {}, None, {}, {"tech": 3}, 200),
            ("get", "query", {"page": "3"}, None, {}, [3, "default"], 200),
            ("get", "query", {"page": 3, "item": 4}, None, {}, [3, "4"], 200),
            (
                "get",
                "query_schema",
                {"page": "5", "item": "tech"},
                None,
                {},
                {"page": 5, "item": "tech"},
                200,
            ),
            ("get", "query_schema", {"page": 5, "item": "t"}, None, {}, ..., 422),
            (
                "get",
                "query_schema",
                {"page": 0, "item": "tech"},
                None,
                {},
                ...,
                422,
            ),
            (
                "get",
                "alias",
                {"class": "infra", "@page": 3},
                None,
                {},
                {"infra": 3},
                200,
            ),
            ("get", "alias", {"class": "infra"}, None, {}, {"infra": 1}, 200),
            (
                "get",
                "random/path/to",
                {},
                None,
                {},
                'random/path/to',
                200,
            ),
            # test not found
            (
                "get",
                "the/api/not_found",
                {},
                None,
                {},
                ...,
                404,
            ),
            (
                "get",
                "the/api/hello",
                {},
                None,
                {},
                {'test': 'world', 'message': 'hello'},
                200,
            ),
            (
                "get",
                "@parent/hello",
                {},
                None,
                {},
                {'test': 'world', 'message': ''},
                200,
            ),
            (
                "get",
                "@parent/sub/hello",
                {},
                None,
                {'X-Test-ID': 1},
                {'test': 'world', 'message': ''},
                200,
            ),
            (
                "get",
                "@parent/sub/test0",
                {},
                None,
                {'X-Test-ID': 1},
                'test0',
                200,
            ),
            (
                "get",
                "@parent/sub/test0",
                {},
                None,
                {},     # test default for before
                'test0',
                200,
            ),
            (
                "get",
                "@parent/sub/test1",
                {},
                None,
                {'X-Test-ID': '3'},
                {'test1': 3},
                200,
            ),
            (
                "get",
                "@parent/sub/resp",
                {},
                None,
                {'X-Test-ID': 5},
                {'resp': 5},
                200,
            ),
            # ----------------------
            (
                "post",
                "upload",
                {},
                BytesIO(b"text"),
                {},
                b'text',
                200,
            ),
            (
                "post",
                "multipart",
                {},
                {"name": "test", "images": files},
                {},
                ['test', 3, 6],
                200,
            ),
            (
                "put",
                "batch",
                {},
                [{"title": "xxx"}, {"title": "yyyy", "views": "3"}],
                {},
                [{"title": "xxx", "views": 0}, {"title": "yyyy", "views": 3}],
                200,
            ),
            (
                "post",
                "log/2022/1/INFO",
                {"status": "500"},
                # [{"title": "yyyy", "views": 3}],
                'title=yyyy&views=3',
                {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                [2022, 1, "INFO", 500, {"title": "yyyy", "views": 3}],
                200,
            ),
            (
                "post",
                "log/2022/1/INFO",
                {"status": "500"},
                {"title": "yyyy", "views": 3},
                {},
                ...,
                422,
            ),
            ("patch", "content", {}, "<xyz>", {
                'Content-Type': 'text/html'
            }, "<xyz>", 200),
            ("patch", "content", {}, "x" * 200, {
                'Content-Type': 'text/html'
            }, ..., 413),
            (
                "put",
                "update",
                {"page": 3, 'item': 'test'},
                {"name": "image.png", "desc": "DESC", "image": image},
                {
                    'cookie': 'test-cookie=123',
                    # 'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundary'
                    'Content-Type': 'multipart/form-data'
                },
                {
                    'image': 'image',
                    'cookie': '123',
                    'name': 'image.png',
                    'desc': 'DESC',
                    'page': 3,
                    'item': 'test'
                },
                200,
            ),  # test body rules
            (
                "post",
                "operation",
                {},
                {"4": [3, {}, [3.4]], "5": ["x", {3: 0}, []]},
                {
                    "X-Auth-Token": "x" * 12,
                    "x-meta-data": {"test": "val"},
                    "Cookie": "sessionid=x",
                },
                [
                    "x" * 12,
                    {"test": "val"},
                    {"sessionid": "x", "csrftoken": None, "access_key": None},
                    {"4": ["3", {}, [3]], "5": ["x", {"3": False}, []]},
                ],
                200,
            ),
            (
                "post",
                "headers_kwargs",
                {"q": 3},
                {"title": "test"},
                {"X-test-ID": "11"},
                [11, 3, {"title": "test", "views": 0}],
                200,
            ),(
                "post",
                "headers_kwargs",
                {"q": '6'},
                {"title": "test"},
                {},     # test default value in request Param
                ['null', 6, {"title": "test", "views": 0}],
                200,
            ),
        ]
        for method, path, query, body, headers, result, status in requests:
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
            assert resp.status == status, f"{method} {path} failed with {content}, {status} expected, got {resp.status}"
            if result is not ...:
                if callable(result):
                    result(content)
                else:
                    assert content == result, f"{method} {path} failed with {content}"

    # def test_private_params(self):
    #     class ParamAPI(API):
    #         @api.post
    #         def private(self, public: str, _private: int = 0):
    #             pass
    #
    #         @api.get
    #         def kwargs(self, public: str, seg_public: str = Rule(alias='__seg__'),
    #                    _private: int = 0, **kwargs):
    #             # even if request pass ?public=x&__seg__=1&&_private=2
    #             # the _private must be 0
    #             # cannot pass from **kwargs  (or will be a bug)
    #             return _private
    #
    #     assert Response.get_content(ParamAPI(Request.custom(
    #         'get', query={'_private': 1, 'public': '1', '__seg__': 'X'}, path='kwargs'))()) == '0'
    #
    #     with pytest.raises(ValueError):
    #         class ParamAPI2(API):
    #             @api.post
    #             def private(self, public: str, _private: int):
    #                 # private param must specify default
    #                 pass

    # def test_api_decorator(self):
    #     class DecoAPI(API):
    #         @api.get(log=False)
    #         def no_log(self):
    #             pass
    #
    #         @api.get('some-route')
    #         def some_route(self):
    #             pass
    #
    #         @api.post('route/{id}')
    #         def post(self):
    #             pass
    #
    #         @api.get('/')
    #         def get_root(self):
    #             pass
    #
    #         @api.get(transaction='default')
    #         def transaction(self):
    #             pass
    #
    #         @api.get(public=False)
    #         def private(self):
    #             pass
    #
    #         @api.get(depreciated=True)
    #         def dep(self):
    #             pass
    #
    #         @api.Retry(
    #             retry_timeout=1,
    #             max_retries=3,
    #             max_retries_timeout=10,
    #             retry_on_errors=[TimeoutError],
    #             retry_interval=lambda: random.random()
    #         )
    #         def sleep(self, seconds: int) -> int:
    #             """
    #             timeout=1s
    #             :param seconds: sleep for seconds
    #             :return: sleep seconds
    #             """
    #             import time
    #             time.sleep(seconds)
    #             return seconds
    #
    # def test_api_errors(self):
    #     from service.api import TestAPI
    #     with pytest.raises(exc.NotFound):
    #         TestAPI(Request.custom("get")).model(
    #             target={("none", False): [], ("other", True): [{"x": "somebody"}]} # noqa
    #         )
    #
    #     with pytest.raises(exc.NotFound):
    #         TestAPI(Request.custom("get", path='doc/1/2/3'))()
    #
    #     with pytest.raises(exc.MethodNotAllowed):
    #         TestAPI(Request.custom("post", path='route-1'))()
