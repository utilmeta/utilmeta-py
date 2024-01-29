import httpx
from .base import ClientRequestAdaptor
from utilmeta.utils import awaitable


class HttpxClientRequestAdaptor(ClientRequestAdaptor):
    backend = httpx

    def __call__(self, timeout: int = None, **kwargs):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(
                method=self.request.method,
                url=self.request.url,
                content=self.request.body,
                headers=self.request.headers,
            )
            return HttpxClientResponseAdaptor(resp)

    @awaitable(__call__)
    async def __call__(self, timeout: int = None, **kwargs):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=self.request.method,
                url=self.request.url,
                content=self.request.body,
                headers=self.request.headers,
            )
            return HttpxClientResponseAdaptor(resp)
