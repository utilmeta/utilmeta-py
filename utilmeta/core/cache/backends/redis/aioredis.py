from utilmeta.utils import keys_or_args, requires
from typing import Dict, Optional, Union, Any
from datetime import timedelta, datetime
from ...base import BaseCacheAdaptor
from ...config import Cache


class AioredisAdaptor(BaseCacheAdaptor):
    asynchronous = True

    def __init__(self, config: "Cache", alias: str = None):
        super().__init__(config, alias=alias)
        self._cache = None

    @classmethod
    def load_aioredis(cls):
        try:
            from redis import asyncio as aioredis
            return aioredis
        except (ModuleNotFoundError, ImportError):
            import sys
            if sys.version_info >= (3, 13):
                raise ModuleNotFoundError(f'{cls} requires to install redis>=4.2.0rc1')
            try:
                # try the deprecated aioredis for lower version of Python (still compatible)
                import aioredis
                return aioredis
            except (ModuleNotFoundError, ImportError):
                raise ModuleNotFoundError(f'{cls} requires to install redis>=4.2.0rc1')

    def get_cache(self):
        if self._cache:
            return self._cache
        aioredis = self.load_aioredis()
        rd = aioredis.from_url(
            self.config.get_location(), encoding="utf-8", decode_responses=True
        )
        self._cache = rd
        return rd

    def check(self):
        try:
            from redis import asyncio as aioredis
        except (ModuleNotFoundError, ImportError):
            try:
                requires(redis='redis>=4.2.0rc1')
                # Aioredis is now in redis-py 4.2.0rc1+
            except Exception as e:
                raise e.__class__(
                    f"{self.__class__} as cache adaptor requires to install caches. "
                    f"use pip install redis>=4.2.0rc1"
                ) from e

    async def get(self, key: str, default=None):
        cache = self.get_cache()
        return await cache.get(key)

    async def fetch(
        self, args=None, *keys: str, named: bool = False
    ) -> Union[list, Dict[str, Any]]:
        # get many
        keys = keys_or_args(args, *keys)
        cache = self.get_cache()
        result = await cache.mget(keys)
        if named:
            return {key: result[i] for i, key in enumerate(keys)}
        else:
            return result

    async def set(
        self,
        key: str,
        value,
        *,
        timeout: Union[int, timedelta, datetime] = None,
        exists_only: bool = False,
        not_exists_only: bool = False,
    ):
        cache = self.get_cache()
        return await cache.set(
            key, value, ex=timeout, nx=not_exists_only, xx=exists_only
        )

    async def update(self, data: Dict[str, Any]):
        # set many
        cache = self.get_cache()
        return await cache.mset(data)

    async def pop(self, key: str):
        cache = self.get_cache()
        value = await cache.get(key)
        await cache.delete(key)
        return value

    async def delete(self, args=None, *keys):
        cache = self.get_cache()
        keys = keys_or_args(args, *keys)
        return await cache.delete(*keys)

    async def exists(self, args=None, *keys) -> int:
        cache = self.get_cache()
        keys = keys_or_args(args, *keys)
        return await cache.exists(*keys)

    async def expire(self, *keys: str, timeout: float):
        cache = self.get_cache()
        for key in keys:
            await cache.expire(key, timeout)

    async def alter(
        self, key: str, amount: Union[int, float], limit: int = None
    ) -> Optional[Union[int, float]]:
        if not amount:
            return await self.get(key)
        cache = self.get_cache()
        if isinstance(amount, float):
            return await cache.incrbyfloat(key, amount)
        elif amount > 0:
            return await cache.incrby(key, amount)
        else:
            return await cache.decrby(key, abs(amount))
