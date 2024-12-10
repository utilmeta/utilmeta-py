from .base import ClientRequestAdaptor
from aiohttp.client import ClientTimeout
import aiohttp


class AiohttpClientRequestAdaptor(ClientRequestAdaptor):
    # request: ClientRequest
    backend = aiohttp

    async def __call__(
        self, timeout: float = None, allow_redirects: bool = None, **kwargs
    ):
        from utilmeta.core.response.backends.aiohttp import AiohttpClientResponseAdaptor

        async with aiohttp.ClientSession(
            timeout=ClientTimeout(total=float(timeout) if timeout is not None else None)
        ) as session:
            resp = await session.request(
                method=self.request.method,
                url=self.request.url,
                data=self.request.body,
                headers=self.request.headers,
                allow_redirects=allow_redirects,
            )
            await resp.read()
            # read here, not outside the session
            return AiohttpClientResponseAdaptor(resp)
