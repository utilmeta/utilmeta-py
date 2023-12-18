from utilmeta.utils import keys_or_args
from typing import Dict, Optional, Union, Any, ClassVar
from datetime import timedelta, datetime
from ..base import BaseCacheAdaptor
from ..config import Cache


class DjangoCacheAdaptor(BaseCacheAdaptor):
    LOCMEM: ClassVar = 'django.core.cache.backends.locmem.LocMemCache'
    MEMCACHED: ClassVar = 'django.core.cache.backends.memcached.MemcachedCache'
    PYLIBMC: ClassVar = 'django.core.cache.backends.memcached.PyLibMCCache'
    REDIS: ClassVar = 'django.core.cache.backends.redis.RedisCache'

    DEFAULT_ENGINES = {
        'locmem': LOCMEM,
        'memcached': MEMCACHED,
        'pylibmc': PYLIBMC,
        'redis': REDIS
    }

    @property
    def cache(self):
        from django.core.cache import caches, BaseCache
        cache: BaseCache = caches[self.alias]
        return cache

    def check(self):
        try:
            import django
        except (ModuleNotFoundError, ImportError) as e:
            raise e.__class__(f'{self.__class__} as database adaptor requires to install django') from e

    def get(self, key: str, default=None):
        return self.cache.get(key, default)

    def fetch(self, args=None, *keys: str, named: bool = False) -> Union[list, Dict[str, Any]]:
        # get many
        keys = keys_or_args(args, *keys)
        data = self.cache.get_many(keys)
        if named:
            return data
        else:
            return [data.get(key) for key in keys]

    def set(self, key: str, value, *, timeout: Union[int, timedelta, datetime] = None,
            exists_only: bool = False, not_exists_only: bool = False):
        if exists_only:
            if not self.exists(key):
                return
        elif not_exists_only:
            if self.exists(key):
                return
        return self.cache.set(key, value, timeout=timeout)

    def update(self, data: Dict[str, Any]):
        # set many
        return self.cache.set_many(data)

    def pop(self, key: str):
        value = self.get(key)
        self.cache.delete(key)
        return value

    def delete(self, args=None, *keys):
        return self.cache.delete_many(keys_or_args(args, *keys))

    def exists(self, args=None, *keys) -> int:
        num = 0
        for key in keys_or_args(args, *keys):
            if self.cache.has_key(key):
                num += 1
        return num

    def expire(self, *keys: str, timeout: float):
        for key in keys:
            return self.cache.touch(key, timeout=timeout)

    def alter(self, key: str, amount: Union[int, float], limit: int = None) -> Optional[Union[int, float]]:
        if not amount:
            return self.get(key)
        try:
            if amount > 0:
                return self.cache.incr(key, amount)
            else:
                return self.cache.decr(key, abs(amount))
        except ValueError:
            # django cache backend may raise ValueError if key does not exists
            self.cache.set(key, amount)


class DjangoCache(Cache):
    sync_adaptor_cls = DjangoCacheAdaptor
