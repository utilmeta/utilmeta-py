import inspect

from .base import ResponseAdaptor
from werkzeug.wrappers import Response as WerkzeugResponse
from typing import Union


class WerkzeugResponseAdaptor(ResponseAdaptor):
    response: WerkzeugResponse

    @classmethod
    def reconstruct(cls, resp: Union["ResponseAdaptor", "WerkzeugResponse"]):
        if isinstance(resp, WerkzeugResponse):
            return resp

        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        if resp.event_stream:
            if inspect.isasyncgen(resp.event_stream):
                raise RuntimeError(f'Flask cannot handle async generator as response, use another backend')
            else:
                content = resp.event_stream
        else:
            content = resp.body

        response = WerkzeugResponse(
            content,
            status=resp.status,
            headers=resp.prepare_headers(),
            content_type=resp.content_type,
        )
        return response

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, WerkzeugResponse)

    @property
    def status(self):
        return self.response.status_code

    @property
    def reason(self):
        return ""

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.data

    def close(self):
        self.response.close()
