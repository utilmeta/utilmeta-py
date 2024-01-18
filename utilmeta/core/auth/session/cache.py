from .schema import BaseSessionSchema, SchemaSession, SessionCreateError, SessionUpdateError
from utilmeta.core.cache import CacheConnections, Cache
# from utilmeta.utils import awaitable
from typing import Type
from utype import Field


class CacheSessionSchema(BaseSessionSchema):
    __connections_cls__ = CacheConnections
    _config: 'CacheSession'

    def get_cache(self) -> Cache:
        return self.__connections_cls__.get(self._config.cache_alias)

    @property
    @Field(no_output=True)
    def cache_key_prefix(self):
        common_prefix = f'{CacheSessionSchema.__module__}'
        # not self.__class__, cause this class may be inherited by different schema classes
        key_prefix = self._config.key_prefix or ''
        return f'{common_prefix}{key_prefix}'

    @property
    @Field(no_output=True)
    def timeout(self) -> int:
        # if expiry_age=0 (at browser close), still means a not clear timeout
        return self.expiry_age or self._config.cookie.age

    def get_key(self, session_key: str = None) -> str:
        return self.cache_key_prefix + (session_key or self._session_key)

    def exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        cache = self.get_cache()
        return bool(cache.exists(session_key))

    # @awaitable(exists)
    async def aexists(self, session_key: str) -> bool:
        if not session_key:
            return False
        cache = self.get_cache()
        return bool(await cache.exists(session_key))

    def create(self):
        self._session_key = self._get_new_session_key()
        try:
            self.save(must_create=True)
        except SessionCreateError:
            return
        self._modified = True
        return

    # @awaitable(create)
    async def acreate(self):
        self._session_key = await self._aget_new_session_key()
        try:
            await self.asave(must_create=True)
        except SessionCreateError:
            return
        self._modified = True
        return

    def save(self, must_create: bool = False):
        if self.session_key is None:
            return self.create()
        cache = self.get_cache()

        if not must_create:
            if self._config.interrupted != 'override':
                if cache.get(self.get_key()) is None:
                    # old session data is deleted
                    if self._config.interrupted == 'cycle':
                        self._session_key = self._get_new_session_key()
                    else:
                        raise SessionUpdateError

        result = cache.set(
            self.get_key(),
            self.encode(dict(self)),
            not_exists_only=must_create,
            timeout=self.timeout,
        )
        if must_create and not result:
            raise SessionCreateError

    # @awaitable(save)
    async def asave(self, must_create: bool = False):
        if self.session_key is None:
            return await self.acreate()
        cache = self.get_cache()

        if not must_create:
            if self._config.interrupted != 'override':
                if await cache.get(self.get_key()) is None:
                    # old session data is deleted
                    if self._config.interrupted == 'cycle':
                        self._session_key = await self._aget_new_session_key()
                    else:
                        raise SessionUpdateError

        result = await cache.set(
            self.get_key(),
            self.encode(dict(self)),
            not_exists_only=must_create,
            timeout=self.timeout,
        )
        if must_create and not result:
            raise SessionCreateError

    def delete(self, session_key: str = None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        if session_key:
            self.get_cache().delete(session_key)

    # @awaitable(delete)
    async def adelete(self, session_key: str = None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        if session_key:
            await self.get_cache().delete(self.get_key(session_key))

    def load_data(self):
        # to be inherited
        return None

    # @awaitable(load_data)
    async def aload_data(self):
        # to be inherited
        return None

    def load(self):
        if not self._session_key:
            return {}
        try:
            session_data = self.get_cache().get(self.get_key())
            if session_data:
                session_data = self.decode(session_data)
            else:
                session_data = None
        except Exception:
            # Some backends (e.g. memcache) raise an exception on invalid
            # cache keys. If this happens, reset the session. See #17810.
            session_data = None
        if session_data is None:
            session_data = self.load_data()
        if session_data is not None:
            return session_data
        self._session_key = None
        return {}

    # @awaitable(load)
    async def aload(self):
        if not self._session_key:
            return {}
        try:
            session_data = await self.get_cache().get(self.get_key())
            if session_data:
                session_data = self.decode(session_data)
            else:
                session_data = None
        except Exception:
            # Some backends (e.g. memcache) raise an exception on invalid
            # cache keys. If this happens, reset the session. See #17810.
            session_data = None
        if session_data is None:
            session_data = await self.aload_data()
        if session_data is not None:
            return session_data
        self._session_key = None
        return {}


class CacheSession(SchemaSession):
    DEFAULT_ENGINE = CacheSessionSchema
    schema = CacheSessionSchema

    def __init__(self, engine=None, cache_alias: str = 'default', key_prefix: str = None, **kwargs):
        super().__init__(engine, **kwargs)
        self.cache_alias = cache_alias
        self.key_prefix = key_prefix

    def init(self, field):
        # check cache exists
        if not CacheConnections.get(self.cache_alias):
            raise ValueError(f'{self.__class__.__name__}: cache_alias ({repr(self.cache_alias)}) '
                             f'not defined in {CacheConnections}')
        return super().init(field)
