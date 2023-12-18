from typing import Dict, Optional, Union, Any, ClassVar
from datetime import timedelta, datetime


class BaseCacheAdaptor:
    asynchronous: ClassVar = False
    DEFAULT_ENGINES: ClassVar = {}

    def __init__(self, config, alias: str = None):
        self.config = config
        self.alias = alias
        self.engine = self.get_engine()

    def get_cache(self):
        return

    def get_engine(self):
        if '.' in self.config.engine:
            return self.config.engine
        if self.config.engine.lower() in self.DEFAULT_ENGINES:
            return self.DEFAULT_ENGINES[self.config.engine.lower()]
        return self.config.engine

    def check(self):
        pass

    def exec(self, command: str):
        pass

    def get(self, key: str, default=None):
        raise NotImplementedError

    def fetch(self, args=None, *keys: str, named: bool = False) -> Union[list, Dict[str, Any]]:
        # get many
        raise NotImplementedError

    def set(self, key: str, value, *, timeout: Union[int, timedelta, datetime] = None,
            exists_only: bool = False, not_exists_only: bool = False):
        raise NotImplementedError

    def update(self, data: Dict[str, Any]):
        # set many
        raise NotImplementedError

    def pop(self, key: str):
        raise NotImplementedError

    def delete(self, args=None, *keys):
        raise NotImplementedError

    def exists(self, args=None, *keys) -> int:
        raise NotImplementedError

    def expire(self, *keys: str, timeout: float):
        raise NotImplementedError

    def alter(self, key: str, amount: Union[int, float], limit: int = None) -> Optional[Union[int, float]]:
        raise NotImplementedError
