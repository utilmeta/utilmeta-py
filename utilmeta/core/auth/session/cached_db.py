# from utilmeta.utils import awaitable
from .cache import CacheSessionSchema, CacheSession
from .db import DBSessionSchema
from utilmeta.core.orm import ModelAdaptor

__all__ = ["CachedDBSessionSchema", "CachedDBSession"]


class CachedDBSessionSchema(CacheSessionSchema, DBSessionSchema):
    def exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        try:
            return super().exists(session_key)
        except Exception:
            return self.db_exists(session_key)

    async def aexists(self, session_key: str) -> bool:
        if not session_key:
            return False
        try:
            return await super().aexists(session_key)
        except Exception:
            return await self.adb_exists(session_key)

    def save(self, must_create: bool = False):
        if self.db_save(must_create):
            # skip cache
            return
        try:
            super().save(must_create)
        except Exception as e:
            print(f"Save with error: {e}")
            # ignore cache failed

    async def asave(self, must_create: bool = False):
        if await self.adb_save(must_create):
            # skip cache
            return
        try:
            await super().asave(must_create)
        except Exception as e:
            print(f"Save with error: {e}")
            # ignore cache failed

    def delete(self, session_key: str = None):
        if self.db_delete(session_key):
            return
        try:
            super().delete(session_key)
        except Exception as e:
            print(f"Delete with error: {e}")
            # ignore cache failed

    # @awaitable(delete)
    async def adelete(self, session_key: str = None):
        if await self.adb_delete(session_key):
            return
        try:
            await super().adelete(session_key)
        except Exception as e:
            print(f"Delete with error: {e}")
            # ignore cache failed

    def load_data(self):
        if not self._session_key:
            return None
        # to be inherited
        session = self._model_cls.get_instance(
            session_key=self._session_key, deleted_time=None
        )
        if session:
            try:
                self.get_cache().set(
                    self.get_key(),
                    session.encoded_data,
                    timeout=self.timeout,
                )
            except Exception as e:
                print(f"Sync to cache failed: {e}")
                # ignore
            return self.decode(session.encoded_data)
        return None

    async def aload_data(self):
        # to be inherited
        if not self._session_key:
            return None
        # to be inherited
        session = await self._model_cls.aget_instance(
            session_key=self._session_key, deleted_time=None
        )
        if session:
            try:
                await self.get_cache().aset(
                    self.get_key(),
                    session.encoded_data,
                    timeout=self.timeout,
                )
            except Exception as e:
                print(f"Sync to cache failed: {e}")
                # ignore
            return self.decode(session.encoded_data)
        return None


class CachedDBSession(CacheSession):
    DEFAULT_ENGINE = CachedDBSessionSchema
    schema = CachedDBSessionSchema

    def __init__(self, session_model, **kwargs):
        super().__init__(**kwargs)
        self.session_model = ModelAdaptor.dispatch(session_model)
