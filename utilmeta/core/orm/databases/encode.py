from .base import BaseDatabaseAdaptor
from typing import Mapping, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from .config import Database

# fixme: !!ISSUE:
#   when query with the same field across different models, result is broken, only the last model.field is reflected
#   it seems that the aggregation of the databases is broken
#   eg.
#   SELECT "entity"."id", "post"."id" FROM "entity" LEFT OUTER JOIN "post" ON ("entity"."id" = "post"."creator_id")
#   problems seems to attribute to databases/backends/postgres.py
#
#   async def fetch_all(self, query: ClauseElement) -> typing.List[RecordInterface]:
#         assert self._connection is not None, "Connection is not acquired"
#         query_str, args, result_columns = self._compile(query)
#         rows = await self._connection.fetch(query_str, *args)
#         dialect = self._dialect
#         column_maps = self._create_column_maps(result_columns)
#         return [Record(row, result_columns, dialect, column_maps) for row in rows]
#   the easy-but-not-fixing-the-root solution is use __relation=exp.F('relation') to produce a different name
#   but such mistake will definitely happens in the complex query


class EncodeDatabasesAsyncAdaptor(BaseDatabaseAdaptor):
    asynchronous = True

    POSTGRESQL = 'postgresql+asyncpg'
    POSTGRESQL_AIOPG = 'postgresql+aiopg'
    MYSQL = 'mysql+aiomysql'
    MYSQL_ASYNCMY = 'mysql+asyncmy'
    SQLITE = 'sqlite+aiosqlite'

    DEFAULT_ENGINES = {
        'sqlite': SQLITE,
        'sqlite3': SQLITE,
        'mysql': MYSQL,
        'postgresql': POSTGRESQL,
        'postgres': POSTGRESQL
    }
    DEFAULT_ASYNC_ENGINES = {
        'sqlite': 'sqlite+aiosqlite',
        'mysql': 'mysql+aiomysql',
        'postgres': 'postgresql+asyncpg'
    }

    def __init__(self, config: 'Database', alias: str = None):
        super().__init__(config, alias=alias)
        self.async_engine = None
        self.engine = self.config.engine
        if '+' in self.engine:
            self.async_engine = self.engine.split('+')[1]
        else:
            for name, engine in self.DEFAULT_ASYNC_ENGINES.items():
                if name in self.engine.lower():
                    self.engine = engine
                    self.async_engine = self.engine.split('+')[1]
                    break
            if not self.async_engine:
                raise ValueError(f'{self.__class__.__name__}: engine invalid or not implemented: {repr(self.engine)}')

        self._db = None     # process local
        # import threading
        # self.local = threading.local()                  # thread local
        # self._var_db = contextvars.ContextVar('db')     # coroutine local

    def get_constraints_error_cls(self):
        if self.async_engine == 'asyncpg':
            from asyncpg.exceptions import UniqueViolationError
            return UniqueViolationError
        # elif self.async_engine == 'aiopg':
        #     from aiopg
        return Exception

    def get_db(self):
        if self._db:
            return self._db
        # return getattr(self.local, 'db', None)
        # return self._var_db.get(None)
        from databases import Database
        engine = self.engine
        if not engine:
            raise ValueError(f'Invalid engine: {engine}')
        # sqlite://<file>
        # postgresql://[user[:password]@][netloc][:port][/dbname][?param1=value1&...]
        database = Database(f'{engine}://{self.config.dsn}', **self.config.params)
        self._db = database
        return database

    async def connect(self):
        db = self.get_db()
        # db = self._db.get(None)
        if not db.is_connected:
            await db.connect()
        return db
        # from databases import Database
        # engine = self.engine
        # if not engine:
        #     raise ValueError(f'Invalid engine: {engine}')
        # # sqlite://<file>
        # # postgresql://[user[:password]@][netloc][:port][/dbname][?param1=value1&...]
        # database = Database(f'{engine}://{self.config.dsn}', **self.config.params)
        # await database.connect()
        # # self._db.set(database)
        # # self._db = database
        # return database

    async def disconnect(self):
        if not self._db:
            return
        db = self.get_db()
        # db = self._db.get(None)
        if db.is_connected:
            await db.disconnect()
            self._db = None
        return


    @classmethod
    def _parse_sql_params(cls, sql: str, params=None):
        if not params:
            return sql, None
        if isinstance(params, Mapping):
            return sql, {key: str(val) for key, val in params.items()}
        elif isinstance(params, (list, tuple)):
            # regex = re.compile('%s::[a-zA-Z0-9()]+\[\]')
            sql = re.compile('%s::[a-zA-Z0-9()]+\[\]').sub('%s', sql)     # match array (only for postgres)
            replaces = tuple(f':param{i}' for i in range(0, len(params)))
            sql = sql % replaces
            params = {f'param{i}': params[i] for i in range(0, len(params))}
            # print('parsed:', sql, params)
            return sql, params
        else:
            raise ValueError(f'Invalid params: {params}')

    async def execute(self, sql, params=None):
        db = await self.connect()       # lazy connect
        sql, params = self._parse_sql_params(sql, params)
        await db.execute(sql, params)

    async def execute_many(self, sql, params: list):
        db = await self.connect()       # lazy connect
        await db.execute_many(sql, params)

    async def fetchone(self, sql, params=None):
        db = await self.connect()       # lazy connect
        sql, params = self._parse_sql_params(sql, params)
        r = await db.fetch_one(sql, params)
        return dict(r._mapping) if r else None

    async def fetchall(self, sql, params=None):
        db = await self.connect()       # lazy connect
        # db = self.get_db()
        sql, params = self._parse_sql_params(sql, params)
        values = await db.fetch_all(sql, params)
        return [dict(val._mapping) for val in values] if values else []

    def transaction(self, savepoint=None, isolation=None, force_rollback: bool = False):
        db = self.get_db()
        return db.transaction(force_rollback=force_rollback, isolation=isolation)

    def check(self):
        try:
            from databases import Database
        except (ModuleNotFoundError, ImportError) as e:
            raise e.__class__(f'{self.__class__} as database adaptor requires to install databases. '
                              f'use pip install databases[{self.async_engine}]') from e
