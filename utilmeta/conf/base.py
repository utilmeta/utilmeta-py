from typing import Type, TypeVar, Optional
from utype import DataClass
from utilmeta.utils import pop

T = TypeVar('T')


class Config(DataClass):
    __eager__ = False

    def __init__(self, kwargs=None):
        if kwargs:
            pop(kwargs, '__class__')
            pop(kwargs, 'self')
        self._kwargs = kwargs or {}
        super().__init__(**self._kwargs)

    @classmethod
    def config(cls: Type[T]) -> Optional[T]:
        try:
            from utilmeta import service
        except ImportError:
            return None
        return service.get_config(cls)

    def hook(self, service):
        pass

    def setup(self, service):
        # call when the service is setting up
        pass

    def on_startup(self, service):
        pass

    def on_shutdown(self, service):
        pass

    def on_api_mount(self, service, api, route: str):
        pass
