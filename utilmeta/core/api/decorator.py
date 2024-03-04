import inspect
from typing import Callable, TypeVar
from utilmeta.utils import METHODS, EndpointAttr, multi, CommonMethod, HOOK_TYPES
import warnings


T = TypeVar('T')

__all__ = [
    # bare route: only for API/Module
    # 'APIDecoratorWrapper',
    # 'APIGenerator',
    # hooks
    'before',
    'after',
    'handle',
    'plugin'
]


def set_hook(f, hook_type: str, value, priority: int = None):
    if not f:
        return f
    if not inspect.isfunction(f):
        raise TypeError(f'Invalid hook: {f}, must be a function')

    if f.__name__.startswith('_'):
        raise ValueError(f'{hook_type} hook func: <{f.__name__}> is startswith "_", which will not be'
                         f' recognized as a api hook')
    if f.__name__.lower() in CommonMethod.gen():
        raise ValueError(f'{hook_type} hook func: <{f.__name__}> name is a HTTP method, which will not be'
                         f' recognized as a api hook')

    if hasattr(f, EndpointAttr.method):
        raise ValueError(f'{hook_type} hook func: {f} has HTTP method set, which means it is a api endpoint')

    assert hook_type in HOOK_TYPES
    for t in HOOK_TYPES:
        if hasattr(f, t):
            if t != hook_type:
                raise AttributeError(f'Function: {f.__name__} is already '
                                     f'hook for <{t}>, cannot hook for {hook_type}')
            else:
                return

    setattr(f, EndpointAttr.hook, hook_type)        # indicate the hook type
    setattr(f, hook_type, value)                # indicate the hook params
    if priority:
        setattr(f, 'priority', priority)
    return f


def set_excludes(f, excludes):
    if not excludes:
        return f
    if hasattr(f, EndpointAttr.excludes):
        return

    if multi(excludes):
        excludes = list(excludes)
    else:
        excludes = [excludes]

    setattr(f, EndpointAttr.excludes, excludes)
    return f


def get_hook_type(f):
    for t in HOOK_TYPES:
        if getattr(f, t, None):
            return t
    return None


class APIGenerator:
    def __init__(self, func, **kwargs):
        self.func = func
        self.kwargs = kwargs

    def __call__(self, f):
        return self.func(f, self)


class APIDecoratorWrapper:
    def __init__(self, method: str = None):
        self.method = method.lower() if isinstance(method, str) else None

    def decorator(self, func, generator: APIGenerator = None):
        # func = generator.func
        kwargs = generator.kwargs if generator else {}

        if isinstance(func, (staticmethod, classmethod)):
            raise TypeError(f'@api can only decorate instance method or API class, got {func}')

        if inspect.isclass(func):
            if self.method:
                raise ValueError(f'@api.{self.method} cannot decorate an API class: {func}')
            rep_func = getattr(func, '__reproduce_with__', None)
            if not rep_func:
                raise ValueError(f'@api decorated an unsupported class: {func}')
            return rep_func(generator)

        name = func.__name__.lower()
        if name in METHODS:
            if self.method:
                if self.method != name:
                    raise ValueError(
                        f'HTTP Method: {self.method} '
                        f'must not decorate another Http Method named function: {name}'
                    )

            self.method = name
        if name.startswith('_'):
            raise ValueError(f'Endpoint func: <{func.__name__}> is startswith "_", which will not be'
                             f' recognized as a api function')

        if kwargs.get('route') == func.__name__:
            warnings.warn(f'Endpoint alias is same as function name: {func.__name__},'
                          f' remove redundant params of decorators')

        kwargs.update(method=self.method)
        for k, v in kwargs.items():
            setattr(func, k, v)

        return func

    def __call__(self, *fn_or_routes,
                 cls=None,
                 summary: str = None,
                 deprecated: bool = None,
                 idempotent: bool = None,
                 private: bool = None,
                 priority: int = None,
                 eager: bool = None,
                 **kwargs,
                 ):

        if len(fn_or_routes) == 1:
            f = fn_or_routes[0]
            if inspect.isfunction(f):  # no parameter @api.get will wrap a callable as this param
                if getattr(f, 'method', None):
                    # already decorated
                    route = getattr(f, 'route', f.__name__)
                else:
                    return self.decorator(f)
            elif isinstance(f, str):
                route = f
            else:
                # routes
                route = (f,)
        elif fn_or_routes:
            route = fn_or_routes
        else:
            f = None

        del f
        del fn_or_routes
        for key, val in locals().items():
            if key == 'self' or key == 'kwargs':
                continue
            if val is None:
                continue
            else:
                kwargs[key] = val
        # return partial(self.decorator, **kwargs)
        return APIGenerator(self.decorator, **kwargs)


def before(*units, excludes=None, priority: int = None):
    if '*' in units:
        assert len(units) == 1, f'@api.before("*") means hook all units, remove the redundant units'
    elif excludes:
        raise ValueError('@api.before excludes only affect when @api.before("*") is applied')

    def wrapper(f: T) -> T:
        return set_hook(
            set_excludes(f, excludes),
            EndpointAttr.before_hook,
            units,
            priority=priority
        )
    return wrapper


def after(*units, excludes=None, priority: int = None):
    if '*' in units:
        assert len(units) == 1, f'@api.after("*") means hook all units, remove the redundant units'
    elif excludes:
        raise ValueError('@api.after excludes only affect when @api.after("*") is applied')

    def wrapper(f: T) -> T:
        return set_hook(
            set_excludes(f, excludes),
            EndpointAttr.after_hook,
            units,
            priority=priority
        )
    return wrapper


def handle(*unit_and_errors, excludes=None, priority: int = None):
    errors = []
    units = []
    for e in unit_and_errors:
        if inspect.isclass(e) and issubclass(e, BaseException):
            errors.append(e)
        else:
            units.append(e)

    if '*' in units:
        assert len(units) == 1, f'@api.accept("*") means hook all units, remove the redundant units'
    if not errors:
        errors = (Exception,)

    def wrapper(f: T) -> T:
        setattr(f, EndpointAttr.errors, errors)
        return set_hook(
            set_excludes(f, excludes),
            EndpointAttr.error_hook,
            units,
            priority=priority
        )
    return wrapper


def plugin(*plugins):
    def wrapper(func):
        for plg in plugins:
            plg(func)
        return func
    return wrapper
