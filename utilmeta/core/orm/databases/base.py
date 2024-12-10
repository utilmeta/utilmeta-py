from typing import Type, TYPE_CHECKING, List, Tuple

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
        pass
