import pytest
from tests.conftest import setup_service

setup_service(__name__, backend='django', async_param=[False])


class TestCache:
    def test_cache(self, service):
        from utilmeta.core.cache import Cache
        cache = Cache(
            engine='memory'
        )
        assert cache.get('key') is None
        cache.set('key', '123')
        assert cache.get('key') == '123'
        cache.pop('key')
        assert cache.get('key') is None

    # @pytest.mark.asyncio
    # async def test_async_cache(self):
    #     from utilmeta.core.cache import Cache
    #     cache = Cache(
    #         engine='memory'
    #     )
    #     assert await cache.aget('key') is None
    #     await cache.aset('key', '123')
    #     assert await cache.aget('key') == '123'
    #     await cache.apop('key')
    #     assert await cache.aget('key') is None
