from utilmeta.utils import awaitable
from .cache import CacheSessionSchema


class AbstractCachedDBSessionSchema(CacheSessionSchema):
    def db_exists(self, session_key: str) -> bool:
        raise NotImplementedError

    @awaitable(db_exists)
    async def db_exists(self, session_key: str) -> bool:
        raise NotImplementedError

    def exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        try:
            return super().exists(session_key)
        except Exception:
            return self.db_exists(session_key)

    @awaitable(exists)
    async def exists(self, session_key: str) -> bool:
        if not session_key:
            return False
        try:
            return await super().exists(session_key)
        except Exception:
            return await self.db_exists(session_key)

    def db_save(self, must_create=False) -> bool:
        raise NotImplementedError

    @awaitable(db_save)
    async def db_save(self, must_create=False) -> bool:
        raise NotImplementedError

    def save(self, must_create: bool = False):
        if self.db_save(must_create):
            # skip cache
            return
        try:
            super().save(must_create)
        except Exception as e:
            print(f'Save with error: {e}')
            # ignore cache failed

    @awaitable(save)
    async def save(self, must_create: bool = False):
        if await self.db_save(must_create):
            # skip cache
            return
        try:
            await super().save(must_create)
        except Exception as e:
            print(f'Save with error: {e}')
            # ignore cache failed

    def db_delete(self) -> bool:
        raise NotImplementedError

    @awaitable(db_delete)
    async def db_delete(self) -> bool:
        raise NotImplementedError

    def delete(self, session_key: str = None):
        if self.db_delete(session_key):
            return
        try:
            super().delete(session_key)
        except Exception as e:
            print(f'Delete with error: {e}')
            # ignore cache failed

    @awaitable(delete)
    async def delete(self, session_key: str = None):
        if await self.db_delete(session_key):
            return
        try:
            await super().delete(session_key)
        except Exception as e:
            print(f'Delete with error: {e}')
            # ignore cache failed
