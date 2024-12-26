import os
from utilmeta.conf.base import Config
from utilmeta import UtilMeta
from utilmeta.utils import awaitable, exceptions, localhost
from typing import Dict, List, Optional, Any
from typing import ContextManager, AsyncContextManager
from .base import BaseDatabaseAdaptor
from .encode import EncodeDatabasesAsyncAdaptor


class Database(Config):
    """
    This is just a declaration interface for database
    the real implementation is database adaptor
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORTS = {"postgres": 5432, "mysql": 3306}

    sync_adaptor_cls = None
    async_adaptor_cls = EncodeDatabasesAsyncAdaptor
    # fixme:
    # for backend that does not support async startup function
    # the async connection cannot be established

    # ---
    name: str
    engine: str = "sqlite"
    user: str = ""
    password: str = ""
    host: str = ""
    port: Optional[int] = None
    time_zone: Optional[str] = None
    ssl: Any = None
    max_size: Optional[int] = None
    min_size: Optional[int] = None
    max_age: Optional[int] = 0
    replica_of: Optional["Database"] = None
    options: Optional[dict] = None

    def __init__(
        self,
        name: str,
        engine: str = "sqlite",
        user: str = "",
        password: str = "",
        host: str = "",
        port: Optional[int] = None,
        time_zone: Optional[str] = None,
        ssl: Any = None,
        max_size: Optional[int] = None,  # connection pool
        min_size: Optional[int] = None,  # connection pool
        max_age: Optional[int] = 0,  # connection max age
        replica_of: Optional["Database"] = None,
        options: Optional[dict] = None,
    ):
        super().__init__(locals())
        self.host = self.host or self.DEFAULT_HOST
        if not self.port:
            for engine, p in self.DEFAULT_PORTS.items():
                if engine in self.engine.lower():
                    self.port = p
                    break
        # self.adaptor: Optional[BaseDatabaseAdaptor] = None
        self._sync_adaptor: Optional[BaseDatabaseAdaptor] = None
        self._async_adaptor: Optional[BaseDatabaseAdaptor] = None
        self._alias = None
        self.asynchronous = False

    @property
    def alias(self) -> str:
        return self._alias

    @property
    # @Field(no_input=True)
    def adaptor(self):
        if self.asynchronous:
            return self._async_adaptor
        return self._sync_adaptor

    @property
    def support_pure_async(self):
        return self.is_sqlite or self.is_postgresql

    # @adaptor.setter
    # def adaptor(self, value: BaseDatabaseAdaptor):
    #     if value.asynchronous:
    #         self._async_adaptor = value
    #     else:
    #         self._sync_adaptor = value

    @property
    def params(self):
        options = dict(self.options or {})
        if self.ssl:
            options.update(ssl=self.ssl)  # True or other ssl context
        if self.max_size:
            options.update(max_size=self.max_size)
        if self.min_size:
            options.update(min_size=self.min_size)
        return options

    @property
    def local(self):
        if self.is_sqlite:
            return True
        return localhost(self.host)

    @property
    def location(self):
        if self.is_sqlite:
            return self.name
        return f"{self.host}:{self.port}"

    @property
    def is_sqlite(self):
        return "sqlite" in self.engine

    @property
    def is_postgresql(self):
        return "postgres" in self.engine

    @property
    def is_mysql(self):
        return "mysql" in self.engine

    @property
    def is_oracle(self):
        return "oracle" in self.engine

    # @property
    # def alias(self):
    #     return self.adaptor.alias

    @property
    def pooled(self):
        return self.max_size or self.min_size

    @property
    def database_name(self):
        if self.is_sqlite:
            return os.path.basename(self.name)
        return self.name

    @property
    def type(self):
        if self.is_sqlite:
            return "sqlite"
        elif self.is_postgresql:
            return "postgresql"
        elif self.is_mysql:
            return "mysql"
        elif self.is_oracle:
            return "oracle"
        return self.engine

    @property
    def dsn(self):
        # [user[:password]@][netloc][:port][/dbname]
        if self.is_sqlite:
            # if os.name != 'nt':
            #     if os.path.isabs(self.name):
            #         return self.name
            # https://stackoverflow.com/a/19262231/14026109
            # Also, as Windows doesn't have the concept of root
            # and instead uses drives, you have to specify absolute path with 3 slashes
            return "/" + self.name
        else:
            user = self.user
            if self.password:
                from urllib.parse import quote

                # for special chars like @ will disrupt DNS
                user += f":{quote(self.password)}"
            netloc = self.host
            if self.port:
                netloc += f":{self.port}"
            return f"{user}@{netloc}/{self.name}"

    @property
    def protected_dsn(self):
        if self.is_sqlite:
            return "/" + self.name
        else:
            user = self.user
            if self.password:
                user += f":******"
            netloc = self.host
            if self.port:
                netloc += f":{self.port}"
            return f"{user}@{netloc}/{self.name}"

    def setup_adaptor(self, asynchronous, force: bool = False):
        if asynchronous:
            if not force and self._async_adaptor:
                return
            if self.async_adaptor_cls:
                self._async_adaptor = self.async_adaptor_cls(self, self.alias)
            else:
                raise exceptions.NotConfigured(
                    f"Database adaptor: async not implemented"
                )
        else:
            if not force and self._sync_adaptor:
                return
            if self.sync_adaptor_cls:
                self._sync_adaptor = self.sync_adaptor_cls(self, self.alias)
            else:
                from ..backends.django.database import DjangoDatabaseAdaptor

                self._sync_adaptor = DjangoDatabaseAdaptor(self, self.alias)

    def apply(self, alias: str, asynchronous: bool = None, project_dir: str = None):
        if self._alias and alias != self.alias:
            raise exceptions.ConfigError(
                f"Conflict database aliases: {repr(alias)}, {repr(self.alias)}"
            )

        self._alias = alias
        self.asynchronous = asynchronous
        self.setup_adaptor(asynchronous, force=True)

        if self.is_sqlite and project_dir:
            if not os.path.isabs(self.name):
                self.name = str(os.path.join(project_dir, self.name))

        self.adaptor.check()

    def get_adaptor(self, asynchronous: bool = False) -> BaseDatabaseAdaptor:
        if self.adaptor and self.adaptor.asynchronous == asynchronous:
            return self.adaptor
        self.setup_adaptor(asynchronous)
        if asynchronous:
            return self._async_adaptor
        return self._sync_adaptor

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

    def transaction(
        self, savepoint=None, isolation=None, force_rollback: bool = False
    ) -> ContextManager:
        return self.get_adaptor(False).transaction(
            savepoint, isolation, force_rollback=force_rollback
        )

    def async_transaction(
        self, savepoint=None, isolation=None, force_rollback: bool = False
    ) -> AsyncContextManager:
        if not self.support_pure_async:
            adaptor = self.get_adaptor(False)
            from asgiref.sync import sync_to_async

            class AsyncAtomic:
                def __init__(self):
                    self.atomic = adaptor.transaction(
                        savepoint, isolation, force_rollback=force_rollback
                    )

                async def __aenter__(self):
                    return await sync_to_async(self.atomic.__enter__)()

                def __enter__(self):
                    return self.atomic.__enter__()

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return await sync_to_async(self.atomic.__exit__)(
                        exc_type, exc_val, exc_tb
                    )

                def __exit__(self, exc_type, exc_val, exc_tb):
                    return self.atomic.__exit__(exc_type, exc_val, exc_tb)

            return AsyncAtomic()  # noqa
        return self.get_adaptor(True).transaction(
            savepoint, isolation, force_rollback=force_rollback
        )


class DatabaseConnections(Config):
    database_cls = Database

    def __init__(self, dbs: Dict[str, Database] = None, **databases: Database):
        self.databases = dbs or databases
        super().__init__(self.databases)

    def hook(self, service: UtilMeta):
        for name, db in self.databases.items():
            self.add_database(service, alias=name, database=db)

    def add_database(self, service: UtilMeta, alias: str, database: Database):
        if not database.sync_adaptor_cls:
            if service.adaptor and service.adaptor.sync_db_adaptor_cls:
                database.sync_adaptor_cls = service.adaptor.sync_db_adaptor_cls
        if not database.async_adaptor_cls:
            if service.adaptor and service.adaptor.async_db_adaptor_cls:
                database.async_adaptor_cls = service.adaptor.async_db_adaptor_cls
        database.apply(
            alias, asynchronous=service.asynchronous, project_dir=service.project_dir
        )
        if alias not in self.databases:
            self.databases.setdefault(alias, database)

    @classmethod
    def get(cls, alias: str = "default") -> Database:
        config = cls.config()
        if not config:
            raise exceptions.NotConfigured(cls)
        try:
            return config.databases[alias]
        except KeyError as e:
            raise exceptions.SettingNotConfigured(cls, item=alias) from e

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
