from utilmeta import utils
from utilmeta.utils import exceptions as exc
from typing import Callable, Type, TYPE_CHECKING, List
from utilmeta.utils.plugin import PluginEvent
import inspect
from utilmeta.core.api.endpoint import BaseEndpoint
from utilmeta.core.response import Response
from utype.parser.rule import LogicalType

if TYPE_CHECKING:
    from .base import Client

process_request = PluginEvent('process_request', streamline_result=True)
handle_error = PluginEvent('handle_error')
process_response = PluginEvent('process_response', streamline_result=True)
enter_endpoint = PluginEvent('enter_endpoint')
exit_endpoint = PluginEvent('exit_endpoint')


class ClientEndpoint(BaseEndpoint):
    PATH_REGEX = utils.PATH_REGEX

    @classmethod
    def apply_for(cls, func: Callable, client: Type['Client'] = None):
        _cls = getattr(func, 'cls', None)
        if not _cls or not issubclass(_cls, ClientEndpoint):
            # override current class
            _cls = cls

        kwargs = {}
        for key, val in inspect.signature(_cls).parameters.items():
            v = getattr(func, key, None)
            if v is None:
                continue
            # func properties override the default kwargs
            kwargs[key] = v
        if client:
            kwargs.update(client=client)
        return _cls(func, **kwargs)

    def __init__(self, f: Callable, *,
                 client: Type['Client'] = None,
                 method: str,
                 plugins: list = None,
                 idempotent: bool = None,
                 eager: bool = False
                 ):

        super().__init__(
            f,
            plugins=plugins,
            method=method,
            idempotent=idempotent,
            eager=eager
        )
        self.client = client
        self.path_args = self.PATH_REGEX.findall(self.route)
        self.response_types: List[Type[Response]] = self.parse_responses(self.parser.return_type)

    @classmethod
    def parse_responses(cls, return_type):
        def is_response(r):
            return inspect.isclass(r) and issubclass(r, Response)

        if is_response(return_type):
            return [return_type]
        elif isinstance(return_type, LogicalType):
            values = []
            for origin in return_type.resolve_origins():
                if is_response(origin):
                    values.append(origin)
            return values
        return []

    @property
    def ref(self) -> str:
        if self.client:
            return f'{self.client.__ref__}.{self.f.__name__}'
        if self.module_name:
            return f'{self.module_name}.{self.f.__name__}'
        return self.f.__name__

    def __call__(self, client: 'Client', *args, **kwargs):
        # with self:
        r = None
        if not self.is_passed:
            r = self.executor(client, *args, **kwargs)
            if inspect.isawaitable(r):
                raise exc.ServerError('awaitable detected in sync function')
        if r is None:
            r = client.__func__(self, *args, **kwargs)
        return r

    @utils.awaitable(__call__)
    async def __call__(self, client: 'Client', *args, **kwargs):
        # async with self:
        r = None
        if not self.is_passed:
            r = self.executor(client, *args, **kwargs)
            while inspect.isawaitable(r):
                # executor is maybe a sync function, which will not need to await
                r = await r
        if r is None:
            r = await client.__func__(self, *args, **kwargs)
        return r


enter_endpoint.register(ClientEndpoint)
exit_endpoint.register(ClientEndpoint)
