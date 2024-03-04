from .base import ClientRequestAdaptor
import requests


class RequestsRequestAdaptor(ClientRequestAdaptor):
    backend = requests

    def __call__(self, timeout: int = None, allow_redirects: bool = None, proxies: dict = None, **kwargs):
        from utilmeta.core.response.backends.requests import RequestsResponseAdaptor
        resp = requests.request(
            method=self.request.method,
            url=self.request.url,
            headers=self.request.headers,
            data=self.request.body,
            timeout=timeout,
            proxies=proxies,
            allow_redirects=allow_redirects,
        )
        return RequestsResponseAdaptor(resp)
