import inspect

from sanic.response import HTTPResponse, ResponseStream, file_stream

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
        return isinstance(obj, (HTTPResponse, ResponseStream))

    @classmethod
    def get_streaming_fn(cls, event_stream):
        async def _streaming_fn(response: ResponseStream):
            if inspect.isasyncgen(event_stream):
                async for event in event_stream:
                    event: str
                    await response.write(event)
            else:
                for event in event_stream:
                    await response.write(event)
            await response.eof()
        return _streaming_fn

    @classmethod
    def reconstruct(cls, resp: Union["ResponseAdaptor", "Response"]):
        if isinstance(resp, HTTPResponse):
            return resp

        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        if resp.event_stream:
            response = ResponseStream(
                cls.get_streaming_fn(resp.event_stream),
                status=resp.status,
                headers=Header(resp.prepare_headers()),
                content_type=resp.content_type,
            )
            # if resp.request:
            #     response.request = resp.request.adaptor.request
        else:
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
