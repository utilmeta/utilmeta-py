from tests.config import make_live, setup_service
from .params import get_requests
from utilmeta.core.response import Response
import flask

setup_service(__name__)

from server import service
service.set_backend(flask)
server_thread = make_live(service)


# def test_flask_api(server_thread):
#     for method, path, query, body, headers, result, status in get_requests():
#         h = dict(headers)
#         h.update({
#             'X-Common-State': 1
#         })
#
#         resp = service.get_client(live=True).request(
#             method=method,
#             path=f'test/{path}',
#             query=query,
#             data=body,
#             headers=h
#         )
#         assert isinstance(resp, Response), f'invalid response: {resp}'
#         content = resp.data
#         assert resp.status == status, f"{method} {path} failed with {content}, {status} expected, got {resp.status}"
#         if result is not ...:
#             if callable(result):
#                 result(content)
#             else:
#                 assert content == result, f"{method} {path} failed with {content}"
