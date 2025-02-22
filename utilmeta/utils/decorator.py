import time
from functools import wraps
import threading
import multiprocessing.pool
from typing import List, Callable, Union, Type
from .constant import COMMON_ERRORS
from .exceptions import BadRequest, CombinedError
from datetime import timedelta
from utilmeta.utils.error import Error
from utilmeta.utils import time_now
import warnings

__all__ = [
    "omit",
    "error_convert",
    "handle_retries",
    "cached_property",
    "awaitable",
    "async_to_sync",
    "adapt_async",
    "handle_parse",
    "handle_timeout",
    "ignore_errors",
    "static_require",
]


def ignore_errors(
    _f=None,
    *,
    default=None,
    log: bool = True,
    log_detail: bool = True,
    errors=(Exception,),
    on_finally=None,
):
    if on_finally:
        assert callable(
            on_finally
        ), f"@ignore_errors on_finally must be a callable, got {on_finally}"

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except errors as e:
                if log:
                    warnings.warn(f"[{str(time_now())}] IGNORED ERROR for {f.__name__}: {e}")
                    if log_detail:
                        # ?fixme: if the repr of the exception variable
                        #   is also the cause to trigger the exception
                        #   this log might be FATAL (causing infinite loop that will drain the system resources)
                        Error(e).log(console=True)
                # to avoid a public mutable value (like dict) cause unpredictable result
                # allow to pass a value like dict or list and call it at runtime
                return default() if callable(default) else default
            finally:
                if on_finally:
                    on_finally()

        return wrapper

    if _f:
        return decorator(_f)
    return decorator


def static_require(*args_func: Callable, runtime: bool = True):
    def not_implement(*_, **__):
        raise NotImplementedError("you current settings does not support this method")

    @ignore_errors(default=False, log=False)
    def satisfied():
        for arg_func in args_func:
            if not arg_func():
                return False
        return True

    def decorator(f):
        if not runtime:
            if satisfied():
                return f
            else:
                return not_implement
        else:

            @wraps(f)
            def wrapper(*args, **kwargs):
                if satisfied():
                    return f(*args, **kwargs)
                return not_implement()

            return wrapper

    return decorator


def error_convert(errors: List[Type[Exception]], target: Type[Exception]):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except errors:
                raise Error().throw(target)
            except CombinedError as e:
                for err in e.errors:
                    if not isinstance(err, tuple(errors)):
                        raise Error().throw()
                raise Error().throw(target)

        return wrapper

    return deco


handle_parse = error_convert(errors=COMMON_ERRORS, target=BadRequest)


def handle_timeout(timeout: timedelta):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            pool = multiprocessing.pool.ThreadPool(processes=1)
            async_result = pool.apply_async(f, args, kwargs)
            try:
                r = async_result.get(timeout.total_seconds())
            except multiprocessing.context.TimeoutError:
                # pool.terminate()
                raise TimeoutError(
                    f"function <{f.__name__}> execute beyond expect"
                    f" time limit {timeout.total_seconds()} seconds"
                )
            finally:
                pool.close()
            return r

        return wrapper

    return decorator


def handle_retries(
    retries: int = 2, on_errors=None, retry_interval: Union[float, Callable] = None
):
    assert retries > 1
    on_errors = on_errors or Exception

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            errors = []
            for i in range(0, retries):
                try:
                    if i and retry_interval:
                        inv = retry_interval
                        if callable(retry_interval):
                            inv = retry_interval()
                        time.sleep(inv)
                    return f(*args, **kwargs)
                except on_errors as e:
                    errors.append(e)
            if not errors:
                raise RuntimeError("Invalid retry status")
            if len(errors) == 1:
                raise Error(errors[0]).throw()
            raise CombinedError(*errors)

        return wrapper

    return decorator


def omit(f, daemon=False):
    """
    @omit
    this decorator is for log save
    as the operation system saving log to database, usually cost 50ms~200ms
    letting request to wait for save is done while result doesn't affect the response is unwise
    so it's function is to execute a async thread task to "fire and forget" the save mission

    further: in next generation, with cache system, the log will be sync load to memory cache
            and batch save to database
    """

    # @ignore_errors(on_finally=close_connections)
    @wraps(f)
    def handler(func, *args, **kwargs):
        func(*args, **kwargs)

    @wraps(f)
    def wrapper(*args, **kwargs):
        args = [f] + [a for a in args]
        threading.Thread(
            target=handler, args=args, kwargs=kwargs, daemon=daemon
        ).start()

    return wrapper


class cached_property:
    """
    Decorator that converts a method with a single self argument into a
    property cached on the instance.

    A cached property can be made out of an existing method:
    (e.g. ``url = cached_property(get_absolute_url)``).
    The optional ``name`` argument is obsolete as of Python 3.6 and will be
    deprecated in Django 4.0 (#30127).
    """

    name = None

    @staticmethod
    def func(instance):
        raise TypeError(
            "Cannot use cached_property instance without calling "
            "__set_name__() on it."
        )

    def __init__(self, func, name=None):
        self.real_func = func
        self.__doc__ = getattr(func, "__doc__")

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name
            self.func = self.real_func
        elif name != self.name:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                "(%r and %r)." % (self.name, name)
            )

    def __get__(self, instance, cls=None):
        """
        Call the function and put the return value in instance.__dict__ so that
        subsequent attribute access on the instance returns the cached value
        instead of calling cached_property.__get__().
        """
        if instance is None:
            return self
        res = instance.__dict__[self.name] = self.func(instance)
        return res


import inspect

_CO_NESTED = inspect.CO_NESTED
_CO_FROM_COROUTINE = (
    inspect.CO_COROUTINE | inspect.CO_ITERABLE_COROUTINE | inspect.CO_ASYNC_GENERATOR
)


def from_coroutine(level=2, _cache={}):
    from sys import _getframe

    f_code = _getframe(level).f_code
    if f_code in _cache:
        return _cache[f_code]
    if f_code.co_flags & _CO_FROM_COROUTINE:
        _cache[f_code] = True
        return True
    else:
        # Comment:  It's possible that we could end up here if one calls a function
        # from the context of a list comprehension or a generator expression. For
        # example:
        #
        #   async def coro():
        #        ...
        #        a = [ func() for x in s ]
        #        ...
        #
        # Where func() is some function that we've wrapped with one of the decorators
        # below.  If so, the code object is nested and has a name such as <listcomp> or <genexpr>
        if f_code.co_flags & _CO_NESTED and f_code.co_name[0] == "<":
            return from_coroutine(level + 2)
        else:
            _cache[f_code] = False
            return False


def adapt_async(f=None, close_conn=True):
    def decorator(func):
        if inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
            return func

        def close_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                if close_conn:
                    from django.db import connections

                    if isinstance(close_conn, str):
                        conn = connections[close_conn]
                        if conn:
                            conn.close()
                    else:
                        connections.close_all()

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from utilmeta import service
            except ImportError:
                pass
            else:
                if service.asynchronous:
                    return service.pool.get_result(close_wrapper, *args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    if f:
        return decorator(f)
    return decorator


from contextvars import ContextVar

from_thread = ContextVar("from_thread")


def awaitable(syncfunc, bind_service: bool = False, close_conn: bool = False):
    """
    Decorator that allows an asynchronous function to be paired with a
    synchronous function in a single function call.  The selection of
    which function executes depends on the calling context.  For example:
        def spam(sock, maxbytes):                       (A)
            return sock.recv(maxbytes)
        @awaitable(spam)                                (B)
        async def spam(sock, maxbytes):
            return await sock.recv(maxbytes)
    In later code, you could use the spam() function in either a synchronous
    or asynchronous context.  For example:
        def foo():
            ...
            r = spam(s, 1024)          # Calls synchronous function (A) above
            ...
        async def bar():
            ...
            r = await spam(s, 1024)    # Calls async function (B) above
            ...
    """

    def decorate(asyncfunc):
        if not inspect.iscoroutinefunction(
            asyncfunc
        ) and not inspect.isasyncgenfunction(asyncfunc):
            raise TypeError(f"{asyncfunc} must be async def function")

        # origin = None
        if isinstance(syncfunc, (classmethod, staticmethod)):
            # origin = syncfunc.__class__
            sync_func = syncfunc.__func__
        else:
            sync_func = syncfunc

        if inspect.signature(sync_func) != inspect.signature(asyncfunc):
            raise TypeError(
                f"{sync_func.__name__} and async {asyncfunc.__name__} have different signatures"
            )

        @wraps(asyncfunc)
        def wrapper(*args, **kwargs):
            if from_coroutine():
                return asyncfunc(*args, **kwargs)
            else:
                if bind_service and not from_thread.get(None):
                    try:
                        from utilmeta import service
                    except ImportError:
                        pass
                    else:
                        if service.asynchronous:
                            import utilmeta

                            if not getattr(utilmeta, "_cmd_env", False):

                                def sync_func_wrapper(*_, **__):
                                    from_thread.set(True)
                                    try:
                                        return sync_func(*_, **__)
                                    finally:
                                        from_thread.set(False)
                                        if close_conn:
                                            from django.db import connections

                                            connections.close_all()

                                return service.pool.get_result(
                                    sync_func_wrapper, *args, **kwargs
                                )
                return sync_func(*args, **kwargs)

        wrapper._syncfunc = sync_func
        wrapper._asyncfunc = asyncfunc
        wrapper._awaitable = True
        wrapper.__doc__ = sync_func.__doc__ or asyncfunc.__doc__
        return wrapper

    return decorate


try:
    from asgiref.sync import async_to_sync
except ImportError:

    def async_to_sync(to_await):
        import asyncio

        async_response = []

        def wrapper(*args, **kwargs):
            try:
                event_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                if event_loop.is_running():
                    raise RuntimeError(
                        "You cannot use AsyncToSync in the same thread as an async event loop - "
                        "just await the async function directly."
                    )

            async def run_and_capture_result():
                r = await to_await(*args, **kwargs)
                async_response.append(r)

            loop = asyncio.get_event_loop()
            coroutine = run_and_capture_result()
            loop.run_until_complete(coroutine)
            return async_response[0]

        return wrapper
