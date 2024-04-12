from .base import ResponseAdaptor
from werkzeug.wrappers import Response as WerkzeugResponse
from typing import Union


class WerkzeugResponseAdaptor(ResponseAdaptor):
    response: WerkzeugResponse

    @classmethod
    def reconstruct(cls, resp: Union['ResponseAdaptor', 'WerkzeugResponse']):
        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        response = WerkzeugResponse(
            resp.body,
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
        return ''

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        return self.response.data

    def close(self):
        self.response.close()
