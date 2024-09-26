from utilmeta.core.file.backends.django import DjangoFileAdaptor  # noqa
from io import BytesIO
from utilmeta.core.response import Response


# image = UploadedFile(BytesIO(b"image"), content_type="image/png", size=6)
def get_requests(backend: str = None, asynchronous: bool = False):
    image = BytesIO(b"image")
    # files = [
    #     UploadedFile(BytesIO(b"f1"), content_type="image/png", size=2),
    #     UploadedFile(BytesIO(b"f2"), content_type="image/png", size=2),
    #     UploadedFile(BytesIO(b"f3"), content_type="image/png", size=2),
    # ]
    files = [
        BytesIO(b"f1"),
        BytesIO(b"f2"),
        BytesIO(b"f3"),
    ]

    backend_requests = [('get', 'backend', {}, None, {}, backend, 200)] if backend else []
    if asynchronous:
        # test async plugins
        backend_requests += [
            ("get", "async_plugin", {}, None, {},
             {"test": "plugin-async-3", "message": ""}, 403),
        ]

    return [
        # (method, path, query, data, headers, result, status)
        ("get", "@special", {}, None, {}, "@special", 200),
        ("get", "sync_plugin", {}, None, {},
         {"test": "plugin-async-1" if asynchronous else "plugin-sync-1", "message": ""},
         401),
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
        ("get", "asynchronous", {}, None, {}, 'async' if asynchronous else 'sync', 200),
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
            {},  # test default for before
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
        (
            "get",
            "@parent/error",
            {"msg": "test_message"},
            None,
            {},
            {'test': 'test_message', 'message': ''},
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
        ), (
            "post",
            "headers_kwargs",
            {"q": '6'},
            {"title": "test"},
            {},  # test default value in request Param
            ['null', 6, {"title": "test", "views": 0}],
            200,
        ),
    ] + backend_requests


def do_live_api_tests(service):
    for method, path, query, body, headers, result, status in get_requests(
        service.backend_name,
        asynchronous=service.asynchronous
    ):
        h = dict(headers)
        h.update({
            'X-Common-State': 1
        })
        resp = service.get_client(live=True).request(
            method=method,
            path=f'test/{path}',
            query=query,
            data=body,
            headers=h
        )
        assert isinstance(resp, Response), f'invalid response: {resp}'
        content = resp.data
        assert resp.status == status, \
            f"{method} {path} failed with {content}, {status} expected, got {resp.status}, {resp.headers}"
        if result is not ...:
            if callable(result):
                result(content)
            else:
                assert content == result, f"{method} {path} failed with {repr(content)}, {repr(result)} expected"
