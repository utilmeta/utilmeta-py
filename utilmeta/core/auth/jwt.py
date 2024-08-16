from utilmeta.core.request import Request
from utilmeta.core.request import var
from utilmeta.core.orm import ModelAdaptor
from utilmeta.utils import exceptions
from .base import BaseAuthentication
from typing import Any, Union


class JsonWebToken(BaseAuthentication):
    name = 'jwt'
    jwt_var = var.RequestContextVar('_jwt_token')
    headers = [
        'authorization'
    ]

    def getter(self, request: Request, field = None):
        token_type, token = request.authorization
        if not token:
            return {}
        try:
            from jwt import JWT  # noqa
            from jwt.exceptions import JWTDecodeError  # noqa
            from jwt.jwk import OctetJWK  # noqa
            jwt = JWT()
            key = None
            if self.secret_key:
                key = OctetJWK(key=self.secret_key.encode())
        except ImportError:
            # jwt 1.7
            import jwt  # noqa
            from jwt.exceptions import DecodeError as JWTDecodeError  # noqa
            key = self.secret_key
        try:
            jwt_params = jwt.decode(token, key, self.algorithm)  # noqa
        except JWTDecodeError:
            raise exceptions.BadRequest(f'invalid jwt token')
        if self.audience:
            aud = jwt_params.get('aud')
            if aud != self.audience:
                raise exceptions.PermissionDenied(f'Invalid audience: {repr(aud)}')
        return jwt_params

    def __init__(self,
                 secret_key: Union[str, Any],
                 algorithm: str = 'HS256',
                 # jwk: Union[str, dict] = None,
                 # jwk json string / dict
                 # jwk file path
                 # jwk url
                 audience: str = None,
                 required: bool = False,
                 user_token_field: str = None
                 ):
        super().__init__(required=required)
        if not secret_key:
            raise ValueError('Authentication config error: JWT secret key is required')
        self.algorithm = algorithm
        self.secret_key = secret_key
        # self.jwk = jwk
        self.audience = audience
        self.user_token_field = user_token_field

    def apply_user_model(self, user_model: ModelAdaptor):
        if self.user_token_field and not isinstance(self.user_token_field, str):
            self.user_token_field = user_model.field_adaptor_cls(self.user_token_field).name

    def login(self, request: Request, key: str = 'uid', expiry_age: int = None):
        user = var.user.getter(request)
        if not user:
            return
        import time
        from utilmeta import service
        iat = time.time()
        inv = expiry_age
        token_dict = {
            'iat': iat,
            'iss': service.origin,
            key: user.pk
        }
        if self.audience:
            token_dict['aud'] = self.audience
        if inv:
            token_dict['exp'] = iat + inv
        try:
            # python-jwt
            # pip install jwt
            from jwt import JWT  # noqa
            from jwt.jwk import OctetJWK  # noqa
            jwt = JWT()
            jwt_key = None
            if self.secret_key:
                jwt_key = OctetJWK(key=self.secret_key.encode())
            jwt_token = jwt.encode(token_dict, key=jwt_key, alg=self.algorithm)
        except ImportError:
            # PyJWT
            # pip install pyjwt
            # jwt 1.7
            import jwt  # noqa
            jwt_token = jwt.encode(  # noqa
                token_dict, self.secret_key,
                algorithm=self.algorithm
            )
            if isinstance(jwt_token, bytes):
                # jwt > 2.0 gives the str
                jwt_token = jwt_token.decode('ascii')
        self.jwt_var.setter(request, jwt_token)
        return {self.user_token_field: jwt_token} if isinstance(self.user_token_field, str) else None
        # if conf.jwt_token_field:
        #     setattr(user, conf.jwt_token_field, jwt_token)
        #     user.save(update_fields=[conf.jwt_token_field])
        # request.jwt_token = jwt_token
        # return jwt_token

    def openapi_scheme(self) -> dict:
        return dict(
            type='http',
            scheme='bearer',
            description=self.description or '',
            bearerFormat='JWT',
        )
