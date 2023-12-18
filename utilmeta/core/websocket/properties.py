from utilmeta.types import *
from utilmeta.core.context import Property


class ClientEvent:
    def __init__(self,
                 key='action',
                 path_param=None,
                 data_getter=None):
        super().__init__()

    def __call__(self, name: str,
                 aliases: List[str] = None,
                 deprecated: bool = None
                 ):
        def decorator(f):
            pass
        return decorator


class ServerEvent:
    pass


class Data(Property):
    pass
