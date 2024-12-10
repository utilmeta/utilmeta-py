from sanic.response import HTTPResponse

try:
    from sanic.response import Header
except ImportError:
    from sanic.compat import Header

from .base import ResponseAdaptor
from typing import TYPE_CHECKING, Union, Optional

if TYPE_CHECKING:
    from utilmeta.core.response import Response


class SanicResponseAdaptor(ResponseAdaptor):
    response: HTTPResponse

    # def __init__(self, response: HTTPResponse):
    #     super().__init__(response)

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, HTTPResponse)

    @classmethod
    def reconstruct(cls, resp: Union["ResponseAdaptor", "Response"]):
        if isinstance(resp, HTTPResponse):
            return resp

        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        response = HTTPResponse(
            resp.prepare_body(),
            status=resp.status,
            headers=Header(resp.prepare_headers()),
            content_type=resp.content_type,
        )
        return response

    @property
    def status(self):
        return self.response.status

    @property
    def reason(self):
        return None

    @property
    def content_type(self) -> Optional[str]:
        return self.response.content_type

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self):
        return self.response.body
