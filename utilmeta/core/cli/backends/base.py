from utilmeta.utils.adaptor import BaseAdaptor
from utilmeta.core.request.base import Request


class ClientRequestAdaptor(BaseAdaptor):
    __backends_package__ = 'utilmeta.core.cli.backends'

    @classmethod
    def get_module_name(cls, obj: "Request"):
        if isinstance(obj, Request):
            return super().get_module_name(obj.backend)
        return super().get_module_name(obj)

    @classmethod
    def qualify(cls, obj: Request):
        if not cls.backend or not obj.backend:
            return False
        return (
            cls.get_module_name(obj.backend).lower()
            == cls.get_module_name(cls.backend).lower()
        )

    def __init__(self, request: Request):
        self.request = request

    def __call__(self, **kwargs):
        raise NotImplementedError(
            "This request backend does not support calling outbound requests"
        )
