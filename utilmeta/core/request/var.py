from typing import Callable
from utilmeta.utils import awaitable
from utilmeta.utils.context import Property
from utype.utils.datastructures import unprovided
import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Request


class RequestContextVar(Property):
    def __init__(
        self,
        key: str,
        cached: bool = False,
        static: bool = False,
        default=None,
        factory: Callable = None,
    ):
        super().__init__(
            default_factory=default if callable(default) else None,
            default=default if not callable(default) else unprovided,
        )
        self.key = key
        self.default = default
        self.factories = [factory] if callable(factory) else []
        self.cached = cached
        self.static = static

    def setup(self, request: "Request"):
        class c:
            @staticmethod
            def contains():
                return self.contains(request)

            @staticmethod
            def get():
                return self.getter(request)

            @staticmethod
            @awaitable(get)
            async def get():
                return await self.getter(request)

            @staticmethod
            def set(v):
                return self.setter(request, value=v)

            @staticmethod
            def delete():
                return self.deleter(request)

        return c

    def contains(self, request: "Request"):
        return request.adaptor.in_context(self.key)

    def getter(self, request: "Request", field=None, default=unprovided):
        r = default
        if self.contains(request):
            r = request.adaptor.get_context(self.key)
        elif unprovided(r):
            for f in self.factories:
                r = f(request)
                if not unprovided(r):
                    break
            if unprovided(r):
                if callable(self.default):
                    r = self.default()
                else:
                    r = self.default
        if self.cached and not unprovided(r):
            self.setter(request, r)
        return r

    @awaitable(getter)
    async def getter(self, request: "Request", field=None, default=unprovided):
        r = default
        if self.contains(request):
            r = request.adaptor.get_context(self.key)
        elif unprovided(r):
            for f in self.factories:
                r = f(request)
                if inspect.isawaitable(r):
                    r = await r
                if not unprovided(r):
                    break
            if unprovided(r):
                if callable(self.default):
                    r = self.default()
                    if inspect.isawaitable(r):
                        r = await r
                else:
                    r = self.default
            # else:
            #     raise KeyError(f'context: {repr(self.key)} missing')
        if self.cached and not unprovided(r):
            self.setter(request, r)
        return r

    def setter(self, request: "Request", value, field=None):
        if self.static and self.contains(request):
            return
        request.adaptor.update_context(**{self.key: value})

    def deleter(self, request: "Request", field=None):
        if self.static and self.contains(request):
            return
        request.adaptor.delete_context(self.key)

    def register_factory(self, func):
        if not callable(func):
            raise ValueError(f'Invalid factory function: {func} for {self.key}: not callable')
        if func not in self.factories:
            self.factories.append(func)


# cached context var
user = RequestContextVar("_user", cached=True)
user_id = RequestContextVar("_user_id", cached=True)
user_config = RequestContextVar("_user_config", cached=True)
ip = RequestContextVar("_ip", factory=lambda request: str(request.ip_address), cached=True)
scopes = RequestContextVar("_scopes", cached=True)
data = RequestContextVar("_data", cached=True)  # parsed str/dict data
# variable context var
time = RequestContextVar(
    "_time", factory=lambda request: request.adaptor.time, static=True
)
path_params = RequestContextVar("_path_params", default=dict)
allow_methods = RequestContextVar("_allow_methods", default=list)
allow_headers = RequestContextVar("_allow_headers", default=list)
unmatched_route = RequestContextVar(
    "_unmatched_route", factory=lambda request: request.adaptor.route
)
operation_names = RequestContextVar("_operation_names", default=list)
# all the passing-by route's name, to combine the endpoint operationId
endpoint_ref = RequestContextVar("_endpoint_ref", default=None)
