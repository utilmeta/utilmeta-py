from utilmeta import utils
from utype.parser.func import FunctionParser
from utilmeta.core.response import Response
from utilmeta.core.response.base import parse_responses
from utilmeta.core.request import Request, var
from utilmeta.utils import exceptions
from .endpoint import RequestContextWrapper
from typing import Callable, Type, TYPE_CHECKING
import inspect
import utype


if TYPE_CHECKING:
    from .base import API


class Hook:
    parser_cls = FunctionParser
    hook_type = None
    target_type = None
    parse_params = False
    parse_result = False

    @classmethod
    def dispatch_for(cls, func: Callable, hook_type: str, target_type: str = 'api') -> 'Hook':
        for hook in cls.__subclasses__():
            hook: Type[Hook]
            try:
                return hook.dispatch_for(func, hook_type, target_type)
            except NotImplementedError:
                continue
        if cls.hook_type == hook_type and cls.target_type == target_type:
            return cls.apply_for(func)
        raise NotImplementedError(f'{cls}: cannot dispatch for hook: {hook_type} in target: {repr(target_type)}')

    @classmethod
    def apply_for(cls, func: Callable) -> 'Hook':
        if not hasattr(func, utils.EndpointAttr.hook):
            raise ValueError(f'Hook type for function: {func} is not specified')
        return cls(
            func,
            hook_type=getattr(func, utils.EndpointAttr.hook),
            hook_targets=getattr(func, cls.hook_type, None),
            hook_excludes=getattr(func, utils.EndpointAttr.excludes, None),
            priority=getattr(func, 'priority', None)
        )

    def __init__(self, f: Callable,
                 hook_type: str,
                 hook_targets: list = None,
                 hook_excludes: list = None,
                 priority: int = None,
                 ):

        if not inspect.isfunction(f):
            raise TypeError(f'Invalid endpoint function: {f}')

        self.f = f
        self.hook_type = hook_type
        self.hook_targets = hook_targets
        self.hook_excludes = hook_excludes
        self.priority = priority
        self.parser = self.parser_cls.apply_for(f)
        self.executor = self.parser.wrap(
            parse_params=self.parse_params,
            parse_result=self.parse_result,
        )

    @property
    def hook_all(self):
        return '*' in self.hook_targets

    @property
    def error_hook(self):
        return self.hook_type == utils.EndpointAttr.error_hook

    @property
    def before_hook(self):
        return self.hook_type == utils.EndpointAttr.before_hook

    @property
    def after_hook(self):
        return self.hook_type == utils.EndpointAttr.after_hook

    def prepare(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        self.prepare(*args, **kwargs)
        return self.executor(*args, **kwargs)

    @utils.awaitable(__call__)
    async def __call__(self, *args, **kwargs):
        self.prepare(*args, **kwargs)
        r = self.executor(*args, **kwargs)
        if inspect.isawaitable(r):
            # executor is maybe a sync function, which will not need to await
            r = await r
        return r


class BeforeHook(Hook):
    hook_type = utils.EndpointAttr.before_hook
    target_type = 'api'
    wrapper_cls = RequestContextWrapper
    # parse_params = False
    # already pared for request

    @classmethod
    def apply_for(cls, func: Callable) -> 'BeforeHook':
        return cls(
            func,
            hook_targets=getattr(func, cls.hook_type),
            hook_excludes=getattr(func, utils.EndpointAttr.excludes, None),
            priority=getattr(func, 'priority', None)
        )

    def __init__(self, f: Callable,
                 hook_targets: list = None,
                 hook_excludes: list = None,
                 priority: int = None):
        super().__init__(
            f,
            hook_type=utils.EndpointAttr.before_hook,
            hook_targets=hook_targets,
            hook_excludes=hook_excludes,
            priority=priority,
        )
        self.wrapper = self.wrapper_cls(self.parser)

    def parse_request(self, request: Request):
        try:
            kwargs = dict(var.path_params.getter(request))
            kwargs.update(self.wrapper.parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
        except utype.exc.ParseError as e:
            raise exceptions.BadRequest(str(e), detail=e.get_detail()) from e

    async def async_parse_request(self, request: Request):
        try:
            kwargs = dict(await var.path_params.getter(request))
            kwargs.update(await self.wrapper.async_parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
            # in base Endpoint, args is not supported
        except utype.exc.ParseError as e:
            raise exceptions.BadRequest(str(e), detail=e.get_detail()) from e

    def serve(self, api: 'API'):
        args, kwargs = self.parse_request(api.request)
        return self(api, *args, **kwargs)

    async def aserve(self, api: 'API'):
        args, kwargs = await self.async_parse_request(api.request)
        return await self(api, *args, **kwargs)


class AfterHook(Hook):
    hook_type = utils.EndpointAttr.after_hook
    target_type = 'api'
    parse_params = True
    # parse_result = True

    @classmethod
    def apply_for(cls, func: Callable) -> 'AfterHook':
        return cls(
            func,
            hook_targets=getattr(func, cls.hook_type),
            hook_excludes=getattr(func, utils.EndpointAttr.excludes, None),
            priority=getattr(func, 'priority', None)
        )

    def __init__(self, f: Callable,
                 hook_targets: list = None,
                 hook_excludes: list = None,
                 priority: int = None):
        super().__init__(
            f,
            hook_type=utils.EndpointAttr.after_hook,
            hook_targets=hook_targets,
            hook_excludes=hook_excludes,
            priority=priority,
        )
        self.response_types = parse_responses(self.parser.return_type)

    def prepare(self, api, *args, **kwargs):
        if self.response_types:
            api._response_types = self.response_types


class ErrorHook(Hook):
    hook_type = utils.EndpointAttr.error_hook
    target_type = 'api'
    parse_params = True

    @classmethod
    def apply_for(cls, func: Callable) -> 'ErrorHook':
        return cls(
            func,
            hook_targets=getattr(func, cls.hook_type),
            hook_excludes=getattr(func, utils.EndpointAttr.excludes, None),
            hook_errors=getattr(func, utils.EndpointAttr.errors, None),
            priority=getattr(func, 'priority', None)
        )

    def __init__(self, f: Callable,
                 hook_targets: list = None,
                 hook_excludes: list = None,
                 hook_errors: list = None,
                 priority: int = None):
        super().__init__(
            f,
            hook_type=utils.EndpointAttr.error_hook,
            hook_targets=hook_targets,
            hook_excludes=hook_excludes,
            priority=priority,
        )
        self.hook_errors = hook_errors
        self.response_types = parse_responses(self.parser.return_type)

    def prepare(self, api, *args, **kwargs):
        if self.response_types:
            api._response_types = self.response_types

    # def process_result(self, result):
    #     if isinstance(result, Response):
    #         return result
    #     if self.response:
    #         return self.response(result)
    #     return result

    # def __call__(self, *args, **kwargs):
    #     return super().__call__(*args, **kwargs)
    #
    # @utils.awaitable(__call__)
    # async def __call__(self, *args, **kwargs):
    #     return await super().__call__(*args, **kwargs)
