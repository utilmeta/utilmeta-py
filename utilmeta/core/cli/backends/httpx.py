import httpx
from .base import ClientRequestAdaptor
from utilmeta.utils import awaitable, pop


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

    def __call__(
        self,
        timeout: float = None,
        allow_redirects: bool = None,
        stream: bool = False,
        clients: dict = None,
        **kwargs
    ):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor

        client: httpx.Client = (clients or {}).get('httpx_client')

        if not isinstance(client, httpx.Client) or client.is_closed:
            client = httpx.Client(
                timeout=float(timeout) if timeout is not None else None,
                follow_redirects=allow_redirects,
            )
            if isinstance(clients, dict):
                # set for cache
                clients['httpx_client'] = client

        try:
            request = client.build_request(
                **self.request_kwargs,
            )
            resp = client.send(request, stream=stream)
            return HttpxClientResponseAdaptor(resp)
        except Exception:
            if stream:
                if clients is None:
                    client.close()
            raise
        finally:
            if not stream and clients is None:
                # not cacheable
                client.close()

    @awaitable(__call__)
    async def __call__(
        self,
        timeout: float = None,
        allow_redirects: bool = None,
        stream: bool = False,
        clients: dict = None,
        **kwargs
    ):
        from utilmeta.core.response.backends.httpx import HttpxClientResponseAdaptor

        client: httpx.AsyncClient = (clients or {}).get('httpx_async_client')

        if not isinstance(client, httpx.AsyncClient) or client.is_closed:
            client = httpx.AsyncClient(
                timeout=float(timeout) if timeout is not None else None,
                follow_redirects=allow_redirects,
            )
            if isinstance(clients, dict):
                # set for cache
                clients['httpx_async_client'] = client

        try:
            request = client.build_request(
                **self.request_kwargs,
            )
            resp = await client.send(request, stream=stream)
            return HttpxClientResponseAdaptor(resp)
        except Exception:
            if stream:
                if clients is None:
                    await client.aclose()
            raise
        finally:
            if not stream and clients is None:
                # not cacheable
                await client.aclose()

        # async with httpx.AsyncClient(
        #     timeout=float(timeout) if timeout is not None else None,
        #     follow_redirects=allow_redirects,
        # ) as client:
        #     request = client.build_request(
        #         **self.request_kwargs,
        #     )
        #     resp = await client.send(request, stream=stream)
        #     return HttpxClientResponseAdaptor(resp)
