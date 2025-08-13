from django.http.response import (
    StreamingHttpResponse,
    HttpResponse,
    HttpResponseBase,
    # FileResponse,
)
from typing import Union, TYPE_CHECKING
from .base import ResponseAdaptor
import django

if TYPE_CHECKING:
    from utilmeta.core.response import Response

pass_headers = django.VERSION >= (3, 2)


class DjangoResponseAdaptor(ResponseAdaptor):
    response: Union[HttpResponse, StreamingHttpResponse]

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, HttpResponseBase)

    @classmethod
    def reconstruct(cls, resp: Union["ResponseAdaptor", "Response"]):
        if isinstance(resp, (HttpResponse, StreamingHttpResponse)):
            return resp

        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        kwargs: dict = dict(
            status=resp.status,
            reason=resp.reason,
            content_type=resp.content_type,
            charset=resp.charset,
        )
        headers = resp.prepare_headers(with_content_type=False)
        if pass_headers:
            kwargs.update(headers=headers)
        # if resp.file:
        #     response = FileResponse(resp.file, **kwargs)
        # else:
        if resp.event_stream:
            response = StreamingHttpResponse(resp.event_stream, **kwargs)
        else:
            response = HttpResponse(resp.body, **kwargs)
        if not pass_headers:
            for k, v in headers:
                response[k] = v
        return response

    @property
    def status(self):
        return self.response.status_code

    @property
    def reason(self):
        return self.response.reason_phrase

    @property
    def headers(self):
        if django.VERSION >= (3, 2):
            return self.response.headers    # noqa
        return {k: v for k, v in self.response.items()}

    @property
    def body(self) -> bytes:
        if self._body is not None:
            return self._body
        if isinstance(self.response, StreamingHttpResponse):
            self._body = self.response.getvalue()
        else:
            self._body = self.response.content
        return self._body

    @property
    def cookies(self):
        return self.response.cookies

    def close(self):
        self.response.close()
