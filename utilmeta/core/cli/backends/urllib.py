from .base import ClientRequestAdaptor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import urllib


class UrllibRequestAdaptor(ClientRequestAdaptor):
    # @classmethod
    # def reconstruct(cls, adaptor: 'RequestAdaptor'):
    #     return cls(Request(
    #         method=adaptor.method,
    #         url=adaptor.url,
    #         data=adaptor.body,
    #         headers=adaptor.headers
    #     ))
    backend = urllib

    def __call__(self, timeout: int = None, **kwargs):
        from utilmeta.core.response.backends.urllib import UrllibResponseAdaptor
        try:
            resp = urlopen(Request(
                url=self.request.url,
                method=self.request.method,
                data=self.request.body,
                headers=self.request.headers,
            ), timeout=timeout)
        except HTTPError as e:
            resp = e
        return UrllibResponseAdaptor(resp)
