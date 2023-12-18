from typing import Dict, List, Tuple
import random
from ...databases.base import BaseDatabaseAdaptor
from ...databases.config import Database


class DjangoDatabaseAdaptor(BaseDatabaseAdaptor):
    SQLITE = 'django.db.backends.sqlite3'
    ORACLE = 'django.db.backends.oracle'
    MYSQL = 'django.db.backends.mysql'
    POSTGRESQL = 'django.db.backends.postgresql'
    # -- pooled backends
    POOLED_POSTGRESQL = 'utilmeta.util.query.pooled_backends.postgresql'
    POOLED_GEVENT_POSTGRESQL = 'utilmeta.util.query.pooled_backends.postgresql_gevent'
    # POOLED_MYSQL = 'utilmeta.util.query.pooled_backends.mysql'
    # POOLED_ORACLE = 'utilmeta.util.query.pooled_backends.oracle'

    DEFAULT_ENGINES = {
        'sqlite': SQLITE,
        'sqlite3': SQLITE,
        'oracle': ORACLE,
        'mysql': MYSQL,
        'postgresql': POSTGRESQL,
        'postgres': POSTGRESQL
    }

    @classmethod
    def get_constraints_error_cls(cls):
        from django.db.utils import IntegrityError
        return IntegrityError

    @classmethod
    def gen_router(cls, app_dbs: Dict[str, Tuple[str, List[str]]]):
        if not app_dbs:
            return None

        class Router:
            @staticmethod
            def db_for_read(model, **hints):
                app = model._meta.app_label
                if app not in app_dbs:
                    return None
                master, replicas = app_dbs[app]
                return random.choice(replicas) if replicas else master

            @staticmethod
            def db_for_write(model, **hints):
                app = model._meta.app_label
                if app not in app_dbs:
                    return None
                master, replicas = app_dbs[app]
                return master

            @staticmethod
            def allow_relation(obj1, obj2, **hints):
                return None

            @staticmethod
            def allow_migrate(db, app_label, model_name=None, **hints):
                if app_label in app_dbs:
                    master, replicas = app_dbs[app_label]
                    return db in [master, *replicas]
                else:
                    return None

        return Router

    def connect(self):
        from django.db import connections
        return connections[self.alias]

    def disconnect(self):
        from django.db import connections
        connections.close_all()

    def execute(self, sql, params=None):
        db = self.connect()
        with db.cursor() as cursor:
            return cursor.execute(sql, params)

    def execute_many(self, sql, params: list):
        db = self.connect()
        with db.cursor() as cursor:
            return cursor.execute(sql, params)
        # await db.execute_many(sql, params)

    def fetchone(self, sql, params=None):
        db = self.connect()
        with db.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def fetchall(self, sql, params=None):
        from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
        db = self.connect()
        with db.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE))

    def transaction(self, savepoint=None, isolation=None, force_rollback: bool = False):
        from django.db import transaction
        return transaction.atomic(self.alias, savepoint=savepoint)

    def check(self):
        try:
            import django
        except (ModuleNotFoundError, ImportError) as e:
            raise e.__class__(f'{self.__class__} as database adaptor requires to install django') from e


class DjangoDatabase(Database):
    sync_adaptor_cls = DjangoDatabaseAdaptor
