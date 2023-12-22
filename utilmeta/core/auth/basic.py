from utilmeta.core.request import Request
import base64
from .base import BaseAuthentication


class BasicAuth(BaseAuthentication):
    name = 'basic'
    headers = [
        'authorization'
    ]

    @classmethod
    def getter(cls, request: Request, field=None):
        token_type, token = request.authorization
        if not token:
            return
        decoded = base64.decodebytes(token.encode())
        lst = decoded.decode().split(':')
        if len(lst) > 1:
            username, password = lst[0], ':'.join(lst[1:])
        else:
            username, password = lst[0], None
        return {'username': username, 'password': password}

    def openapi_scheme(self) -> dict:
        return {
            'type': 'http',
            'scheme': 'basic',
            'description': self.description or '',
        }
