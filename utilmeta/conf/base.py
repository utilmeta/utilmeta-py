from utype import DataClass
from typing import Type, TypeVar, Optional

T = TypeVar('T')


class Config(DataClass):
    __eager__ = False

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
