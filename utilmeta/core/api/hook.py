from utilmeta import utils
from utype.parser.func import FunctionParser
from utilmeta.core.response import Response
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
    parse_params = False
    parse_result = False

    @classmethod
    def dispatch_for(cls, func: Callable, hook_type: str) -> 'Hook':
        for hook in cls.__subclasses__():
            hook: Type[Hook]
            if hook.hook_type == hook_type:
                return hook.apply_for(func)
        return cls.apply_for(func)

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
            return await r
        return r


class BeforeHook(Hook):
    hook_type = utils.EndpointAttr.before_hook
    wrapper_cls = RequestContextWrapper
    parse_params = True

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
            kwargs = dict(var.path_params.get(request))
            kwargs.update(self.wrapper.parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
        except utype.exc.ParseError as e:
            raise exceptions.BadRequest(str(e)) from e

    @utils.awaitable(parse_request)
    async def parse_request(self, request: Request):
        try:
            kwargs = dict(await var.path_params.get(request))
            kwargs.update(await self.wrapper.parse_context(request))
            return self.parser.parse_params((), kwargs, context=self.parser.options.make_context())
            # in base Endpoint, args is not supported
        except utype.exc.ParseError as e:
            raise exceptions.BadRequest(str(e)) from e

    def serve(self, api: 'API'):
        args, kwargs = self.parse_request(api.request)
        return self(api, **kwargs)

    @utils.awaitable(serve)
    async def serve(self, api: 'API'):
        args, kwargs = await self.parse_request(api.request)
        return await self(api, *args, **kwargs)


class AfterHook(Hook):
    hook_type = utils.EndpointAttr.after_hook
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
        self.response = None
        rt = self.parser.return_type
        if inspect.isclass(rt) and issubclass(rt, Response):
            self.response = rt

    def prepare(self, api, *args, **kwargs):
        if self.response:
            api.response = self.response


class ErrorHook(Hook):
    hook_type = utils.EndpointAttr.error_hook
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
        self.response = None
        rt = self.parser.return_type
        if inspect.isclass(rt) and issubclass(rt, Response):
            self.response = rt
