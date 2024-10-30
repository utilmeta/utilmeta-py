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

from databases.core import Transaction, Database


# https://github.com/encode/databases/issues/594
class _Transaction(Transaction):
    async def commit(self) -> None:
        async with self._connection._transaction_lock:
            assert self._connection._transaction_stack[-1] is self
            assert self._transaction is not None
            await self._transaction.commit()
            # POP after committing successfully
            self._connection._transaction_stack.pop()
            await self._connection.__aexit__()
            self._transaction = None

    async def __aexit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting `async with database.transaction()`
        """
        if exc_type is not None or self._force_rollback:
            await self.rollback()
        else:
            try:
                await self.commit()
            except Exception as e:
                try:
                    await self.rollback()
                finally:
                    # raise e no matter rollback failed or succeed
                    raise e


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
        self.db_backend = None
        self.engine = None
        if '+' in self.config.engine:
            self.db_backend, self.async_engine = self.config.engine.split('+')
            self.engine = self.config.engine
        else:
            for name, engine in self.DEFAULT_ASYNC_ENGINES.items():
                if name in self.config.engine.lower():
                    self.engine = engine
                    self.db_backend, self.async_engine = self.engine.split('+')
                    break
            if not self.engine:
                raise ValueError(f'{self.__class__.__name__}: engine invalid or not implemented: '
                                 f'{repr(self.config.engine)}')

        self._db = None     # process local
        self._processed = False
        # import threading
        # self.local = threading.local()                  # thread local
        # self._var_db = contextvars.ContextVar('db')     # coroutine local

    def get_integrity_errors(self):
        if self.db_backend in ('postgres', 'postgresql'):
            errors = []
            try:
                from asyncpg.exceptions import IntegrityConstraintViolationError
                errors.append(IntegrityConstraintViolationError)
            except (ImportError, ModuleNotFoundError):
                pass
            try:
                from psycopg2 import IntegrityError
                errors.append(IntegrityError)
            except (ImportError, ModuleNotFoundError):
                pass
            return tuple(errors)
        elif self.db_backend in ('sqlite', 'sqlite3'):
            from sqlite3 import IntegrityError
            return (IntegrityError,)
        elif self.db_backend == 'mysql':
            errors = []
            try:
                from pymysql.err import IntegrityError
                errors.append(IntegrityError)
            except (ImportError, ModuleNotFoundError):
                pass
            return tuple(errors)
        return ()

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
        params = dict(self.config.params)
        factory = self.connection_factory
        if factory:
            params.update(factory=factory)
        database = Database(f'{engine}://{self.config.dsn}', **params)
        self._db = database
        return database

    @property
    def connection_factory(self):
        if self.db_backend in ('sqlite', 'sqlite3'):
            import sqlite3
            from aiosqlite import Connection

            class SQLiteConnection(sqlite3.Connection):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    # if not self.in_transaction:
                    self.execute('PRAGMA foreign_keys = ON;')
                    # self.execute('PRAGMA legacy_alter_table = OFF;')
                    # print('SQLITE EXECUTE')

            return SQLiteConnection
        return None

    # async def process_db(self, db):
    #     if self._processed:
    #         return
    #     if self.db_backend in ('sqlite', 'sqlite3'):
    #         # ref: django.db.backends.sqlite3.base.get_new_connection
    #         # print('EXECUTE PRAGMA')
    #         await db.execute("PRAGMA foreign_keys = ON;")
    #         await db.execute("PRAGMA legacy_alter_table = OFF;")
    #     self._processed = True

    async def connect(self):
        db = self.get_db()
        # db = self._db.get(None)
        if not db.is_connected:
            await db.connect()
        # if not self._processed:
        # await self.process_db(db)
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
        return _Transaction(db.connection, force_rollback=force_rollback, isolation=isolation)

    def check(self):
        try:
            from databases import Database
        except (ModuleNotFoundError, ImportError) as e:
            raise e.__class__(f'{self.__class__} as database adaptor requires to install databases. '
                              f'use pip install databases[{self.async_engine}]') from e
