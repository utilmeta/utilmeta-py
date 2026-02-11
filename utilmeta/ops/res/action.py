from utype.types import *
from utilmeta.ops.schema import ActionData
from .base import BaseHandler


class BaseAction(BaseHandler):
    def __init__(self, handler: Callable,
                 name: str = None,
                 idempotent: bool = None,
                 title: str = None,
                 description: str = None,
                 ):
        super().__init__(handler, name=name, title=title, description=description)
        self.idempotent = idempotent

    def dict(self) -> ActionData:
        return ActionData(
            idempotent=self.idempotent,
            **super().dict()
        )


def action_handler(
    idempotent: bool = None,
    title: str = None,
    description: str = None,
    action_cls=BaseAction,
):
    def wrapper(f):
        return action_cls(
            f,
            title=title,
            description=description,
            idempotent=idempotent,
        )
    return wrapper


class BaseActionRegistry:
    __actions__: Dict[str, BaseAction] = {}

    def __init_subclass__(cls, **kwargs):
        actions = dict(cls.__actions__)
        for key, val in cls.__dict__.items():
            if val is None:
                if key in actions:
                    actions.pop(key)
            elif isinstance(val, BaseAction):
                val.setup(cls)
                actions[key] = val
        cls.__actions__ = actions


class ServiceActionRegistry(BaseActionRegistry):
    @action_handler(
        idempotent=True
    )
    def restart_service(self): pass

    @action_handler(
        idempotent=True
    )
    def stop_service(self): pass
