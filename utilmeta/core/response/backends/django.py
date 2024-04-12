from django.http.response import StreamingHttpResponse, HttpResponse, HttpResponseBase, FileResponse
from typing import Union, TYPE_CHECKING
from .base import ResponseAdaptor

if TYPE_CHECKING:
    from utilmeta.core.response import Response


class DjangoResponseAdaptor(ResponseAdaptor):
    response: Union[HttpResponse, StreamingHttpResponse]

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, HttpResponseBase)

    @classmethod
    def reconstruct(cls, resp: Union['ResponseAdaptor', 'Response']):
        from utilmeta.core.response import Response
        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        kwargs = dict(
            status=resp.status,
            reason=resp.reason,
            content_type=resp.content_type,
            charset=resp.charset,
            headers=resp.prepare_headers()
        )
        if resp.file:
            response = FileResponse(resp.file, **kwargs)
        else:
            response = HttpResponse(resp.body, **kwargs)
        return response

    @property
    def status(self):
        return self.response.status_code

    @property
    def reason(self):
        return self.response.reason_phrase

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self) -> bytes:
        if isinstance(self.response, StreamingHttpResponse):
            return self.response.getvalue()
        return self.response.content

    @property
    def cookies(self):
        return self.response.cookies

    def close(self):
        self.response.close()
