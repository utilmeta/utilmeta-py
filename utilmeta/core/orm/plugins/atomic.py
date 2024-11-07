from utilmeta.utils.plugin import PluginBase
from utilmeta.utils import awaitable
from ..databases.config import DatabaseConnections
import inspect
import functools


class AtomicPlugin(PluginBase):
    def __init__(self, alias: str = 'default', savepoint: bool = True, durable: bool = False,
                 isolation=None, force_rollback: bool = False):
        super().__init__(locals())
        self.alias = alias
        self.savepoint = savepoint
        self.durable = durable
        self.isolation = isolation
        self.force_rollback = force_rollback
        self.db = DatabaseConnections.get(alias)

        self.transaction = None
        self.async_transaction = None

    def __enter__(self):
        self.transaction = self.db.transaction(
            savepoint=self.savepoint,
            isolation=self.isolation,
            force_rollback=self.force_rollback
        )
        return self.transaction.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            self.transaction.__exit__(exc_type, exc_val, exc_tb)
            self.transaction = None

    # def __await__(self):
    #     if self.async_transaction:
    #         return self.async_transaction.__await__()
    #
    def rollback(self):
        if self.async_transaction:
            return self.async_transaction.rollback()

    def commit(self):
        if self.async_transaction:
            return self.async_transaction.commit()

    async def __aenter__(self):
        self.async_transaction = self.db.async_transaction(
            savepoint=self.savepoint,
            isolation=self.isolation,
            force_rollback=self.force_rollback
        )
        return await self.async_transaction.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.async_transaction:
            await self.async_transaction.__aexit__(exc_type, exc_val, exc_tb)
            self.async_transaction = None

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
