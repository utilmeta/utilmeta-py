from typing import Type, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from utilmeta import UtilMeta


class BaseAPISpec:
    spec = None
    __version__ = None

    def __init__(self, service: 'UtilMeta'):
        self.service = service
        self.format = format

    def __call__(self):
        raise NotImplementedError

    def save(self, file: str):
        pass
