from ...config import Cache
from typing import Optional
from .aioredis import AioredisAdaptor
from ..django import DjangoCacheAdaptor


class RedisCache(Cache):
    async_adaptor_cls = AioredisAdaptor

    username: Optional[str] = None
    password: Optional[str] = None
    db: int = 0
    scheme: str = 'redis'

    def __init__(
        self, *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        scheme: str = 'redis',
        db: int = 0,
        **kwargs
    ):
        super().__init__(
            engine='redis',
            username=username,
            password=password,
            scheme=scheme,
            db=db,
            **kwargs
        )

    def get_location(self):
        if self.location:
            return self.location
        if not self.password:
            return f'{self.scheme}://{self.host}:{self.port}/{self.db}'
        else:
            return f'{self.scheme}://{self.username or ""}:{self.password}@{self.host}:{self.port}/{self.db}'

    @property
    def con(self):
        from redis import Redis
        return Redis.from_url(self.get_location())

    @property
    def async_con(self):
        from aioredis.client import Redis
        cli: Redis = self.get_adaptor(True).get_cache()
        return cli
