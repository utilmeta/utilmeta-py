import httpx
from .base import ClientRequestAdaptor
from utilmeta.utils import awaitable


class HttpxClientRequestAdaptor(ClientRequestAdaptor):
    backend = httpx

    @property
    def request_kwargs(self):
        kwargs = dict(
            method=self.request.method,
            url=self.request.url,
            headers=self.request.headers,
        )
        if self.request.body:
            if isinstance(self.request.body, bytes):
                kwargs.update(content=self.request.body)
            elif isinstance(self.request.body, (dict, list)):
                kwargs.update(json=self.request.body)
            else:
                kwargs.update(data=self.request.body)
        return kwargs

    def __call__(self, timeout: int = None, **kwargs):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(**self.request_kwargs)
            return HttpxClientResponseAdaptor(resp)

    @awaitable(__call__)
    async def __call__(self, timeout: int = None, **kwargs):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(**self.request_kwargs)
            return HttpxClientResponseAdaptor(resp)
