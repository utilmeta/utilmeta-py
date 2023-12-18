from utilmeta.utils.context import Property
from utilmeta.core.request import Request
from utilmeta.core.orm import ModelAdaptor


class BaseAuthentication(Property):
    name = None

    def login(self, request: Request, key: str, expiry_age: int = None):
        raise NotImplementedError

    def apply_user_model(self, user_model: ModelAdaptor):
        pass

    def openapi_scheme(self) -> dict:
        raise NotImplementedError
