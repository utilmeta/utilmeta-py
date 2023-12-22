from utilmeta.core.request import Request, var
from datetime import timedelta
from typing import Union, Any, Callable
import hmac
from utype.parser.field import ParserField
from utilmeta.utils import exceptions as exc
from utilmeta.utils import get_interval, awaitable
# from utilmeta.adapt.orm.base import ModelAdaptor
from utype.types import Datetime
from utype.utils.datastructures import unprovided
from .base import BaseAuthentication


class SignatureAccess(BaseAuthentication):
    name = 'signature'
    user_context_var = var.user
    scopes_context_var = var.scopes

    def init(self, field: ParserField):
        from utilmeta.core.orm.backends.base import ModelAdaptor
        self.access_models.extend([
            ModelAdaptor.dispatch(m) for m in field.input_origins
            if m and not isinstance(None, m)]
        )
        if not self.access_models:
            pass
        return super().init(field)

    def _get_pre_data(self, request: Request):
        ak = self.get_request_access_key(request)
        if not ak:
            if self.required:
                raise exc.Unauthorized
            return None
        sig = self.get_request_signature(request)
        if not sig:
            raise exc.BadRequest(f'{self.__class__}: {self.signature_header} required')
        ts = self.get_request_timestamp(request)
        if not ts:
            raise exc.BadRequest(f'{self.__class__}: {self.timestamp_header} required')
        return ak, ts, sig

    def _validate_post_data(self, request: Request, access, ts, sig):
        timeout = self.get_timeout(access)
        if timeout is not None:
            dt = Datetime(ts)
            if abs((request.time - dt).total_seconds()) > timeout:
                raise exc.PermissionDenied('Timestamp expired')
        if not access:
            raise exc.PermissionDenied('invalid Access Key')
        sk = getattr(access, self.secret_key_field)
        if self.user_field:
            user = getattr(access, self.user_field)
            if user:
                self.user_context_var.set(request, user)
        if self.scopes_field:
            self.scopes_context_var.set(getattr(access, self.scopes_field, []))
        gen_sig = self.get_signature(request, timestamp=ts, secret_key=sk)
        if sig != gen_sig:
            raise exc.PermissionDenied('Invalid Signature')

    def getter(self, request: Request, field: ParserField = None):
        r = self._get_pre_data(request)
        if not r:
            return None
        ak, ts, sig = r
        access = self.get_access_instance(ak)
        self._validate_post_data(request, access, ts=ts, sig=sig)
        return access

    @awaitable(getter)
    async def getter(self, request: Request, field: ParserField = None):
        r = self._get_pre_data(request)
        if not r:
            return None
        ak, ts, sig = r
        access = await self.get_access_instance(ak)
        self._validate_post_data(request, access, ts=ts, sig=sig)
        return access

    def __init__(
        self,
        *access_models: type,
        access_key_field: Union[str, Any] = 'access_key',
        secret_key_field: Union[str, Any] = 'secret_key',
        user_field: str = None,
        scopes_field: str = None,
        access_key_header: str = 'X-Access-Key',
        signature_header: str = 'X-Signature',
        timestamp_header: str = 'X-Timestamp',
        timestamp_timeout: Union[timedelta, int, Callable] = 30,
        required: bool = False,
        digest_mode: str = 'SHA256'
    ):
        from utilmeta.core.orm.backends.base import ModelAdaptor
        self.access_models = [ModelAdaptor.dispatch(m) for m in access_models]

        self.access_key_field = access_key_field
        self.secret_key_field = secret_key_field
        self.user_field = user_field
        self.scopes_field = scopes_field
        self.access_key_header = access_key_header
        self.signature_header = signature_header
        self.timestamp_header = timestamp_header
        self.timestamp_timeout = get_interval(timestamp_timeout, null=True) if not \
            callable(timestamp_timeout) else timestamp_timeout
        self.digest_mode = digest_mode
        super().__init__(required=required, default=unprovided if required else None)

    def get_request_access_key(self, request: Request):
        return request.headers.get(self.access_key_header)

    def get_request_signature(self, request: Request):
        return request.headers.get(self.signature_header)

    def get_request_timestamp(self, request: Request):
        return request.headers.get(self.timestamp_header)

    def get_timeout(self, access) -> Union[int, float]:
        if callable(self.timestamp_timeout):
            return self.timestamp_timeout(access)
        return self.timestamp_timeout

    def get_signature(self, request: Request, timestamp: str, secret_key: str) -> str:
        """
        Can be override
        """
        tag = f'{timestamp}{request.adaptor.request_method}{request.url}'.encode()
        tag += request.body or b''
        return hmac.new(key=secret_key.encode(), msg=tag, digestmod=self.digest_mode).hexdigest()

    def get_access_instance(self, access_key: str):
        for model in self.access_models:
            access = model.get_instance(**{self.access_key_field: access_key})
            if access:
                return access
        return None

    @awaitable(get_access_instance)
    async def get_access_instance(self, access_key: str):
        for model in self.access_models:
            access = await model.get_instance(**{self.access_key_field: access_key})
            if access:
                return access
        return None

    def openapi_scheme(self) -> dict:
        # return dict(
        #     type='apikey',
        #     name=self.access_key_header,
        #     in='header',
        #     description=self.description,
        #     bearerFormat='JWT',
        # )
        return {
            'type': 'apikey',
            'name': self.access_key_header,
            'in': 'header',
            'description': self.description or '',
        }

    @property
    def headers(self):
        return [
            self.access_key_header.lower(),
            self.timestamp_header.lower(),
            self.signature_header.lower()
        ]
