from starlette.responses import Response as HttpResponse
from starlette.responses import StreamingResponse
from .base import ResponseAdaptor
from typing import TYPE_CHECKING, Union


if TYPE_CHECKING:
    from utilmeta.core.response import Response


class StarletteResponseAdaptor(ResponseAdaptor):
    response: HttpResponse

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, HttpResponse)

    @classmethod
    def reconstruct(cls, resp: Union["ResponseAdaptor", "Response"]):
        if isinstance(resp, HttpResponse):
            return resp

        from utilmeta.core.response import Response

        if isinstance(resp, ResponseAdaptor):
            resp = Response(response=resp)
        elif not isinstance(resp, Response):
            resp = Response(resp)

        kwargs = dict(status_code=resp.status, media_type=resp.content_type)
        # file will not be closed if using this
        # file = resp.file
        # if file:
        #     def iterator():
        #         return iter(file.file)
        #
        #     response = StreamingResponse(resp.file, **kwargs)
        # else:
        stream = resp.event_stream
        if stream:
            response = StreamingResponse(stream, **kwargs)
        else:
            response = HttpResponse(resp.body, **kwargs)
        for key, val in resp.prepare_headers():
            # set values in this way cause headers is a List[Tuple]
            response.headers[key] = val
        return response

    @property
    def status(self):
        return self.response.status_code

    @property
    def reason(self):
        return None

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self):
        # StreamResponse does not have body attribute
        return getattr(self.response, "body", b"")

    @property
    def cookies(self):
        from http.cookies import SimpleCookie

        cookies = SimpleCookie()
        for cookie in self.response.headers.getlist("set-cookie"):
            cookies.load(cookie)
        return cookies

    def close(self):
        pass
