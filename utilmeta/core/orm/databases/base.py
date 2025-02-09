from typing import Type, TYPE_CHECKING, List, Tuple

from utilmeta.utils import cached_property, detect_package_manager, requires, exceptions
import os

if TYPE_CHECKING:
    from .config import Database


class BaseDatabaseAdaptor:
    asynchronous = False
    DEFAULT_ENGINES = {}

    def __init__(self, config: "Database", alias: str = None):
        self.config = config
        self.alias = alias

    def get_engine(self):
        if "." in self.config.engine:
            return self.config.engine
        if self.config.engine.lower() in self.DEFAULT_ENGINES:
            return self.DEFAULT_ENGINES[self.config.engine.lower()]
        return self.config.engine

    def get_integrity_errors(self) -> Tuple[Type[Exception], ...]:
        return ()

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def execute(self, sql, params=None):
        raise NotImplementedError

    def execute_many(self, sql, params: list):
        raise NotImplementedError

    def fetchone(self, sql, params=None):
        raise NotImplementedError

    def fetchall(self, sql, params=None):
        raise NotImplementedError

    def transaction(self, savepoint=None, isolation=None, force_rollback: bool = False):
        raise NotImplementedError

    def check(self):
        # if self.checked.get(self.alias):
        #     raise ValueError
        # self.checked[self.alias] = True
        if self.config.is_mysql:
            try:
                import MySQLdb
            except (ModuleNotFoundError, ImportError):
                self.install_mysql()
                requires(MySQLdb="mysqlclient")

        elif self.config.is_postgresql:
            try:
                import psycopg2
            except (ModuleNotFoundError, ImportError):
                try:
                    import psycopg
                except (ModuleNotFoundError, ImportError):
                    self.install_postgresql()
                    requires(psycopg="psycopg[binary,pool]", psycopg2="psycopg2")

    @cached_property
    def package_manager(self):
        return detect_package_manager()

    def install_postgresql(self):
        pkg = self.package_manager
        if not pkg:
            return
        if pkg == "apt":
            os.system("sudo apt-get install -y libpq-dev")
        elif pkg == "yum":
            os.system("sudo yum install -y libpq-devel")

    def install_mysql(self):
        pkg = self.package_manager
        if not pkg:
            return
        if pkg == "apt":
            os.system(
                "sudo apt-get install pkg-config python3-dev build-essential"
                " libmysqlclient-dev default-libmysqlclient-dev -y -m"
            )
        elif pkg == "yum":
            os.system("sudo yum install python-devel mysql-devel -y")
