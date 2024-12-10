from .base import BaseAuthentication
from utilmeta.core.request import Request
from authlib.oauth2.rfc6750 import BearerTokenValidator
from authlib.oauth2.rfc7523 import JWTBearerTokenValidator
from authlib.jose.rfc7517.jwk import JsonWebKey
from authlib.oauth2 import ResourceProtector
from authlib.oauth2.rfc6749 import (
    HttpRequest,
)

from urllib.request import urlopen
import json


class Auth0JWTBearerTokenValidator(JWTBearerTokenValidator):
    def __init__(self, domain, audience):
        issuer = f"https://{domain}/"
        jsonurl = urlopen(f"{issuer}.well-known/jwks.json")
        public_key = JsonWebKey.import_key_set(json.loads(jsonurl.read()))
        super(Auth0JWTBearerTokenValidator, self).__init__(public_key)
        self.claims_options = {
            "exp": {"essential": True},
            "aud": {"essential": True, "value": audience},
            "iss": {"essential": True, "value": issuer},
        }


class OAuth2(BaseAuthentication):
    name = "oauth2"
    protector_cls = ResourceProtector
    headers = ["authorization"]

    def __init__(self, *validators: BearerTokenValidator, scopes_key=None):
        self.protector = self.protector_cls()
        for validator in validators:
            self.protector.register_token_validator(validator)
        super(OAuth2, self).__init__()
        self.scopes_key = scopes_key

    def acquire_token(self, request: Request, scopes=None):
        """A method to acquire current valid token with the given scope.

        :param request: Django HTTP request instance
        :param scopes: a list of scope values
        :return: token object
        """
        req = HttpRequest(
            method=request.method,
            uri=request.url,
            data=request.body,
            headers=request.headers,
        )
        req.req = request
        if isinstance(scopes, str):
            scopes = [scopes]
        token = self.protector.validate_request(scopes, req)
        return token

    def getter(self, request: Request, field=None):
        token = self.acquire_token(request)

    def require(self, scopes=None, required: bool = None):
        pass

    # def param(self, key: str):
    #     pass

    # def __call__(self, scopes=None, optional=False):
    #     def wrapper(f):
    #         @functools.wraps(f)
    #         def decorated(request, *args, **kwargs):
    #             try:
    #                 token = self.acquire_token(request, scopes)
    #                 request.oauth_token = token
    #             except MissingAuthorizationError as error:
    #                 if optional:
    #                     request.oauth_token = None
    #                     return f(request, *args, **kwargs)
    #                 return return_error_response(error)
    #             except OAuth2Error as error:
    #                 return return_error_response(error)
    #             return f(request, *args, **kwargs)
    #         return decorated
    #     return wrapper

    def openapi_scheme(self) -> dict:
        # return dict(
        #     type='apikey',
        #     name=self.access_key_header,
        #     in='header',
        #     description=self.description,
        #     bearerFormat='JWT',
        # )
        return {
            "type": "oauth2",
            "flows": {
                # todo
                # https://spec.openapis.org/oas/v3.1.0#oauthFlowObject
            },
            "description": self.description or "",
        }
