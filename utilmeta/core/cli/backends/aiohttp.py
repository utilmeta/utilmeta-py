from .base import ClientRequestAdaptor
from aiohttp.client import ClientTimeout
import aiohttp


class AiohttpClientRequestAdaptor(ClientRequestAdaptor):
    # request: ClientRequest
    backend = aiohttp

    async def __call__(
        self,
        timeout: float = None,
        allow_redirects: bool = None,
        clients: dict = None,
        stream: bool = False,
        **kwargs
    ):
        from utilmeta.core.response.backends.aiohttp import AiohttpClientResponseAdaptor

        session: aiohttp.ClientSession = (clients or {}).get('aiohttp_session')

        if not isinstance(session, aiohttp.ClientSession) or session.closed:
            session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=float(timeout) if timeout is not None else None)
            )

            if isinstance(clients, dict):
                # set for cache
                clients['aiohttp_session'] = session

        # async with aiohttp.ClientSession(
        #     timeout=ClientTimeout(total=float(timeout) if timeout is not None else None)
        # ) as session:
        try:
            resp = await session.request(
                method=self.request.method,
                url=self.request.url,
                data=self.request.body,
                headers=self.request.headers,
                allow_redirects=allow_redirects,
            )
            if not stream:
                await resp.read()
                # read here, not outside the session
            return AiohttpClientResponseAdaptor(resp)
        except Exception:
            if stream:
                if clients is None:
                    await session.close()
            raise
        finally:
            if not stream and clients is None:
                await session.close()
