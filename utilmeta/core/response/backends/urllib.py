from http.client import HTTPResponse
from urllib.error import HTTPError
from typing import Union
from .base import ResponseAdaptor


class UrllibResponseAdaptor(ResponseAdaptor):
    response: Union[HTTPResponse, HTTPError]

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, (HTTPResponse, HTTPError))

    @property
    def status(self):
        return self.response.status

    @property
    def reason(self):
        return self.response.reason

    @property
    def headers(self):
        return self.response.headers

    @property
    def body(self):
        return self.response.read()

    @property
    def cookies(self):
        from http.cookies import SimpleCookie
        cookies = SimpleCookie()
        for cookie in self.headers.get_all('Set-Cookie') or []:
            # use get_all, cause Set-Cookie can be multiple
            cookies.load(cookie)
        return cookies

    def close(self):
        self.response.close()
