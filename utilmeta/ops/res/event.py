from utype.types import *
from utilmeta.ops.schema import EventData
from .base import BaseHandler
from utilmeta.utils import awaitable, time_now, get_ref
import inspect


class BaseEvent(BaseHandler):
    DEFAULT_SEVERITY = 3    # INFO

    def __init__(self, handler: Callable,
                 name: str = None,
                 resource_type: str = None,
                 title: str = None,
                 description: str = None,
                 default_severity: int = None,
                 category: str = None,
                 silent: bool = False,
                 source_table: str = None,
                 ):
        super().__init__(handler, name=name, title=title, description=description)
        self.resource_type = resource_type
        self.category = category
        self.description = description
        if default_severity is None:
            default_severity = self.DEFAULT_SEVERITY
        self.default_severity = default_severity
        self.silent = silent
        self.source_table = source_table

    def dict(self) -> EventData:
        return EventData(
            resource_type=self.resource_type,
            default_severity=self.default_severity,
            category=self.category,
            silent=self.silent,
            source_table=self.source_table,
            **super().dict()
        )

    def __call__(
        self,
        event_id: str = None,      # identifier
        **kwargs
    ):
        return self.handler(**kwargs)

    @awaitable(__call__)
    async def __call__(
        self,
        event_id: str = None,  # identifier
        **kwargs
    ):
        r = self.handler(**kwargs)
        if inspect.isawaitable(r):
            r = await r
        return r


def event_handler(
    resource_type: str = None,
    title: str = None,
    description: str = None,
    default_severity: int = None,
    category: str = None,
    silent: bool = False,
    source=None,
    event_cls=BaseEvent
):
    def wrapper(f):
        return event_cls(
            f,
            resource_type=resource_type,
            title=title,
            description=description,
            default_severity=default_severity,
            category=category,
            silent=silent,
            source_table=get_ref(source) if source else None,
        )
    return wrapper


class BaseEventRegistry:
    __events__: Dict[str, BaseEvent] = {}

    def __init_subclass__(cls, **kwargs):
        events = dict(cls.__events__)
        for key, val in cls.__dict__.items():
            if val is None:
                if key in events:
                    events.pop(key)
            elif isinstance(val, BaseEvent):
                val.setup(cls)
                events[key] = val
        cls.__events__ = events
