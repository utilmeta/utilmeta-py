import os
from utilmeta.conf.base import Config
from utilmeta import UtilMeta
from utilmeta.utils import awaitable, exceptions
from typing import Dict, List, Optional, Union, Any
from typing import ContextManager, AsyncContextManager
from .base import BaseDatabaseAdaptor
from .encode import EncodeDatabasesAsyncAdaptor


class Database(Config):
    """
    This is just a declaration interface for database
    the real implementation is database adaptor
    """
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORTS = {
        'postgres': 5432,
        'mysql': 3306
    }

    sync_adaptor_cls = None
    async_adaptor_cls = EncodeDatabasesAsyncAdaptor
    # ---
    name: str
    engine: str = 'sqlite'
    user: str = ''
    password: str = ''
    host: str = ''
    port: Optional[int] = None
    time_zone: Optional[str] = None
    ssl: Any = None
    max_size: Optional[int] = None
    min_size: Optional[int] = None
    max_age: Optional[int] = 0
    replica_of: Optional['Database'] = None
    options: Optional[dict] = None

    def __init__(self,
                 name: str,
                 engine: str = 'sqlite',
                 user: str = '',
                 password: str = '',
                 host: str = '',
                 port: Optional[int] = None,
                 time_zone: Optional[str] = None,
                 ssl: Any = None,
                 max_size: Optional[int] = None,      # connection pool
                 min_size: Optional[int] = None,      # connection pool
                 max_age: Optional[int] = 0,    # connection max age
                 replica_of: Optional['Database'] = None,
                 options: Optional[dict] = None):
        super().__init__(**locals())
        self.host = self.host or self.DEFAULT_HOST
        if not self.port:
            for engine, p in self.DEFAULT_PORTS.items():
                if engine in self.engine.lower():
                    self.port = p
                    break
        self.adaptor: Optional[BaseDatabaseAdaptor] = None
        self.asynchronous = False

    @property
    def params(self):
        options = dict(self.options or {})
        if self.ssl:
            options.update(ssl=self.ssl)        # True or other ssl context
        if self.max_size:
            options.update(max_size=self.max_size)
        if self.min_size:
            options.update(min_size=self.min_size)
        return options

    @property
    def alias(self):
        return self.adaptor.alias

    @property
    def pooled(self):
        return self.max_size or self.min_size

    @property
    def dsn(self):
        # [user[:password]@][netloc][:port][/dbname]
        if 'sqlite' in self.engine:
            if os.path.isabs(self.name):
                return self.name
            return '/' + self.name
        else:
            user = self.user
            if self.password:
                user += f':{self.password}'
            netloc = self.host
            if self.port:
                netloc += f':{self.port}'
            return f'{user}@{netloc}/{self.name}'

    def apply(self, alias: str, asynchronous: bool = None):
        if asynchronous:
            if self.async_adaptor_cls:
                self.adaptor = self.async_adaptor_cls(self, alias)
        else:
            if self.sync_adaptor_cls:
                self.adaptor = self.sync_adaptor_cls(self, alias)
        self.asynchronous = asynchronous
        self.adaptor.check()

    def get_adaptor(self, asynchronous: bool = False) -> BaseDatabaseAdaptor:
        if self.asynchronous == asynchronous and self.adaptor:
            return self.adaptor
        if asynchronous:
            return self.async_adaptor_cls(self, self.adaptor.alias)
        return self.sync_adaptor_cls(self, self.adaptor.alias)

    def connect(self):
        return self.get_adaptor(False).connect()

    @awaitable(connect)
    async def connect(self):
        return await self.get_adaptor(True).connect()

    def disconnect(self):
        return self.get_adaptor(False).disconnect()

    @awaitable(disconnect)
    async def disconnect(self):
        return await self.get_adaptor(True).disconnect()

    def execute(self, sql, params=None):
        return self.get_adaptor(False).execute(sql, params)

    @awaitable(execute)
    async def execute(self, sql, params=None):
        return await self.get_adaptor(True).execute(sql, params)

    def fetchone(self, sql, params=None) -> dict:
        return self.get_adaptor(False).fetchone(sql, params)

    @awaitable(fetchone)
    async def fetchone(self, sql, params=None) -> dict:
        return await self.get_adaptor(True).fetchone(sql, params)

    def fetchall(self, sql, params=None) -> List[dict]:
        return self.get_adaptor(False).fetchall(sql, params)

    @awaitable(fetchall)
    async def fetchall(self, sql, params=None) -> List[dict]:
        return await self.get_adaptor(True).fetchall(sql, params)

    def transaction(self, savepoint=None, isolation=None, force_rollback: bool = False) -> ContextManager:
        return self.get_adaptor(False).transaction(savepoint, isolation, force_rollback=force_rollback)

    def async_transaction(self, savepoint=None, isolation=None, force_rollback: bool = False) -> AsyncContextManager:
        return self.get_adaptor(True).transaction(savepoint, isolation, force_rollback=force_rollback)


class DatabaseConnections(Config):
    database_cls = Database

    def __init__(self, dbs: Dict[str, Database] = None, **databases: Database):
        self.databases = dbs or databases
        super().__init__(**self.databases)

    def hook(self, service: UtilMeta):
        for name, db in self.databases.items():
            db.apply(name, asynchronous=service.asynchronous)

    @classmethod
    def get(cls, alias: str = 'default') -> Database:
        config = cls.config()
        if not config:
            raise exceptions.NotConfigured(cls)
        return config.databases[alias]

    def items(self):
        return self.databases.items()

    def on_startup(self, service):
        for key, value in self.databases.items():
            value.connect()

    @awaitable(on_startup)
    async def on_startup(self, service):
        for key, value in self.databases.items():
            await value.connect()

    def on_shutdown(self, service):
        for key, value in self.databases.items():
            value.connect()

    @awaitable(on_shutdown)
    async def on_shutdown(self, service):
        for key, value in self.databases.items():
            await value.disconnect()
