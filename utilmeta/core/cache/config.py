from utilmeta.conf.base import Config
from utilmeta import UtilMeta
from utilmeta.utils import awaitable, exceptions, localhost
from typing import Dict, List, Optional, Union, Callable, Any, ClassVar
from datetime import timedelta, datetime
from utype.utils.datastructures import unprovided
from .base import BaseCacheAdaptor


class Cache(Config):
    """
    This is just a declaration interface for database
    the real implementation is database adaptor
    """
    DEFAULT_HOST: ClassVar = '127.0.0.1'
    DEFAULT_PORTS: ClassVar = {
        'redis': 6379,
        'mcache': 11211,
        'memcache': 11211
    }

    sync_adaptor_cls = None
    async_adaptor_cls = None
    # ---

    engine: str  # 'redis' / 'memcached' / 'locmem'
    host: Optional[str] = None
    port: int = 0
    timeout: int = 300
    location: Union[str, List[str]] = ''
    prefix: Optional[str] = None
    max_entries: Optional[int] = None
    key_function: Optional[Callable] = None
    options: Optional[dict] = None

    def __init__(self, *,
                 engine: str,      # 'redis' / 'memcached' / 'locmem'
                 host: Optional[str] = None,
                 port: int = 0,
                 timeout: int = 300,
                 location: Union[str, List[str]] = '',
                 prefix: Optional[str] = None,
                 max_entries: Optional[int] = None,
                 key_function: Optional[Callable] = None,
                 options: Optional[dict] = None,
                 **kwargs
                 ):
        kwargs.update(locals())
        super().__init__(kwargs)
        self.host = self.host or self.DEFAULT_HOST
        if not self.port:
            for engine, p in self.DEFAULT_PORTS.items():
                if engine in self.engine.lower():
                    self.port = p
                    break
        self.adaptor: Optional[BaseCacheAdaptor] = None
        self.asynchronous = False

    @property
    def type(self) -> str:
        if 'redis' in self.engine.lower():
            return 'redis'
        elif 'memcached' in self.engine.lower():
            return 'memcached'
        elif 'locmem' in self.engine.lower():
            return 'locmem'
        elif 'file' in self.engine.lower():
            return 'file'
        elif 'database' in self.engine.lower() or 'db' in self.engine.lower():
            return 'db'
        return 'memory'

    @property
    def is_memory(self) -> bool:
        return self.type in ['locmem', 'memory']

    @property
    def local(self):
        if not self.host:
            return True
        return localhost(self.host)

    @property
    def alias(self):
        return self.adaptor.alias

    def apply(self, alias: str, asynchronous: bool = None):
        if asynchronous:
            if self.async_adaptor_cls:
                self.adaptor = self.async_adaptor_cls(self, alias)
            else:
                from .backends.django import DjangoCacheAdaptor
                self.adaptor = DjangoCacheAdaptor(self, alias)
        else:
            if self.sync_adaptor_cls:
                self.adaptor = self.sync_adaptor_cls(self, alias)
            else:
                from .backends.django import DjangoCacheAdaptor
                self.adaptor = DjangoCacheAdaptor(self, alias)
        self.asynchronous = asynchronous
        self.adaptor.check()

    def get_adaptor(self, asynchronous: bool = False) -> 'BaseCacheAdaptor':
        if self.adaptor and self.adaptor.asynchronous == asynchronous:
            return self.adaptor
        if asynchronous:
            if not self.async_adaptor_cls:
                raise exceptions.SettingNotConfigured(self.__class__, item='async_adaptor_cls')
            return self.async_adaptor_cls(self, self.adaptor.alias)
        if not self.sync_adaptor_cls:
            raise exceptions.SettingNotConfigured(self.__class__, item='sync_adaptor_cls')
        return self.sync_adaptor_cls(self, self.adaptor.alias)

    def get_location(self):
        if self.location:
            return self.location
        return f'{self.host}:{self.port}'

    def get(self, key: str, default=None):
        return self.get_adaptor(False).get(key, default)

    @awaitable(get)
    async def get(self, key: str, default=None):
        return await self.get_adaptor(True).get(key, default)

    def fetch(self, args=None, *keys: str, named: bool = False) -> Union[list, Dict[str, Any]]:
        # get many
        return self.get_adaptor(False).fetch(args, *keys, named=named)

    @awaitable(fetch)
    async def fetch(self, args=None, *keys: str, named: bool = False) -> Union[list, Dict[str, Any]]:
        # get many
        return await self.get_adaptor(True).fetch(args, *keys, named=named)

    def set(self, key: str, value, *, timeout: Union[int, timedelta, datetime] = None,
            exists_only: bool = False, not_exists_only: bool = False):
        return self.get_adaptor(False).set(
            key, value,
            timeout=timeout,
            exists_only=exists_only,
            not_exists_only=not_exists_only
        )

    @awaitable(set)
    async def set(self, key: str, value, *, timeout: Union[int, timedelta, datetime] = None,
                  exists_only: bool = False, not_exists_only: bool = False):
        return await self.get_adaptor(True).set(
            key, value,
            timeout=timeout,
            exists_only=exists_only,
            not_exists_only=not_exists_only
        )

    def update(self, data: Dict[str, Any]):
        # set many
        return self.get_adaptor(False).update(data)

    @awaitable(update)
    async def update(self, data: Dict[str, Any]):
        # set many
        return await self.get_adaptor(True).update(data)

    def pop(self, key: str):
        return self.get_adaptor(False).pop(key)

    @awaitable(pop)
    async def pop(self, key: str):
        # set many
        return await self.get_adaptor(True).pop(key)

    def delete(self, args=None, *keys):
        return self.get_adaptor(False).delete(args, *keys)

    @awaitable(delete)
    async def delete(self, args=None, *keys):
        return await self.get_adaptor(True).delete(args, *keys)

    def exists(self, args=None, *keys) -> int:
        return self.get_adaptor(False).exists(args, *keys)

    @awaitable(exists)
    async def exists(self, args=None, *keys) -> int:
        return await self.get_adaptor(True).exists(args, *keys)

    def expire(self, *keys: str, timeout: float):
        return self.get_adaptor(False).expire(*keys, timeout=timeout)

    @awaitable(expire)
    async def expire(self, *keys: str, timeout: float):
        return await self.get_adaptor(True).expire(*keys, timeout=timeout)

    def alter(self, key: str, amount: Union[int, float], limit: int = None) -> Optional[Union[int, float]]:
        return self.get_adaptor(False).alter(key, amount, limit=limit)

    @awaitable(alter)
    async def alter(self, key: str, amount: Union[int, float], limit: int = None) -> Optional[Union[int, float]]:
        return await self.get_adaptor(True).alter(key, amount, limit=limit)


class CacheConnections(Config):
    def __init__(self, cs: Dict[str, Cache] = None, **caches: Cache):
        self.caches = cs or caches
        super().__init__(**self.caches)

    def hook(self, service: UtilMeta):
        for name, cache in self.caches.items():
            cache.apply(name, asynchronous=service.asynchronous)

    def add_cache(self, service: UtilMeta, alias: str, cache: Cache):
        if not cache.sync_adaptor_cls:
            if service.adaptor and service.adaptor.sync_db_adaptor_cls:
                cache.sync_adaptor_cls = service.adaptor.sync_db_adaptor_cls
        if not cache.async_adaptor_cls:
            if service.adaptor and service.adaptor.async_db_adaptor_cls:
                cache.async_adaptor_cls = service.adaptor.async_db_adaptor_cls
        cache.apply(alias, asynchronous=service.asynchronous)
        if alias not in self.caches:
            self.caches.setdefault(alias, cache)

    @classmethod
    def get(cls, alias: str = 'default', default=unprovided) -> Cache:
        config = cls.config()
        if not config:
            if unprovided(default):
                raise exceptions.NotConfigured(cls)
            return default
        return config.caches[alias]

    def items(self):
        return self.caches.items()

    # def on_startup(self, service):
    #     for key, value in self.caches.items():
    #         value.connect()
    #
    # @awaitable(on_startup)
    # async def on_startup(self, service):
    #     for key, value in self.caches.items():
    #         await value.connect()
    #
    # def on_shutdown(self, service):
    #     for key, value in self.caches.items():
    #         value.connect()
    #
    # @awaitable(on_shutdown)
    # async def on_shutdown(self, service):
    #     for key, value in self.caches.items():
    #         await value.disconnect()


