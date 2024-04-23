from utilmeta.utils.plugin import Plugin
from utilmeta.utils import awaitable
from ..databases.config import DatabaseConnections
import inspect
import functools


class AtomicPlugin(Plugin):
    def __init__(self, alias: str = 'default', savepoint: bool = True, durable: bool = False,
                 isolation=None, force_rollback: bool = False):
        super().__init__(locals())
        self.alias = alias
        self.savepoint = savepoint
        self.durable = durable
        self.isolation = isolation
        self.force_rollback = force_rollback
        self.db = DatabaseConnections.get(alias)

    def __call__(self, f, *_, **__):
        if inspect.iscoroutinefunction(f) or inspect.isasyncgenfunction(f):
            transaction = self.db.async_transaction(
                savepoint=self.savepoint,
                isolation=self.isolation,
                force_rollback=self.force_rollback
            )

            @functools.wraps(f)
            async def wrapper(*args, **kwargs):
                async with transaction:
                    return await f(*args, **kwargs)
            return wrapper

        elif inspect.isfunction(f):
            transaction = self.db.transaction(
                savepoint=self.savepoint,
                isolation=self.isolation,
                force_rollback=self.force_rollback
            )

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                with transaction:
                    return f(*args, **kwargs)

            try:
                from utilmeta import service
            except ImportError:
                pass
            else:
                if service.asynchronous:
                    @functools.wraps(f)
                    def threaded_wrapper(*args, **kwargs):
                        return service.pool.get_result(wrapper, *args, **kwargs)
                    return threaded_wrapper

            return wrapper

        return super().__call__(f, *_, **__)
