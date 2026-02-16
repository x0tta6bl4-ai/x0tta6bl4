import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from libx0t.core.cache import (
    RedisCache, InMemoryCacheBackend, cached, get_or_warm, CacheWarming, reset_cache
)

class TestInMemoryCacheBackend:
    @pytest.mark.asyncio
    async def test_basic_ops(self):
        backend = InMemoryCacheBackend()
        
        # Set
        assert await backend.set("key", "value") is True
        
        # Get
        assert await backend.get("key") == "value"
        assert await backend.get("missing") is None
        
        # Delete
        assert await backend.delete("key") == 1
        assert await backend.get("key") is None

    @pytest.mark.asyncio
    async def test_expiry(self):
        backend = InMemoryCacheBackend()
        
        # Set with short TTL
        await backend.set("key", "value", ex=-1) # Already expired
        assert await backend.get("key") is None

    @pytest.mark.asyncio
    async def test_nx(self):
        backend = InMemoryCacheBackend()
        
        assert await backend.set("key", "val1", nx=True) is True
        assert await backend.set("key", "val2", nx=True) is False
        assert await backend.get("key") == "val1"

class TestRedisCache:
    @pytest.fixture(autouse=True)
    def reset(self):
        reset_cache()
        yield
        reset_cache()

    @pytest.mark.asyncio
    async def test_singleton(self):
        c1 = RedisCache.create_for_testing()
        c2 = RedisCache()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_operations_delegation(self):
        backend = InMemoryCacheBackend()
        cache = RedisCache(backend)
        
        assert await cache.set("k", "v") is True
        assert await cache.get("k") == "v"
        assert await cache.delete("k") is True

    @pytest.mark.asyncio
    async def test_health_check(self):
        backend = InMemoryCacheBackend()
        cache = RedisCache(backend)
        
        health = await cache.health_check()
        assert health["status"] == "healthy"
        assert health["mode"] == "standalone"

    @pytest.mark.asyncio
    async def test_get_stats_mock(self):
        # Redis backend mock
        mock_backend = AsyncMock()
        mock_backend.info.return_value = {"used_memory_human": "1M"}
        
        cache = RedisCache(mock_backend)
        # Ensure initialized
        cache._initialized = True
        
        stats = await cache.get_stats()
        
        # Use .get() based on actual implementation
        assert stats["used_memory_human"] == "1M"

    @pytest.mark.asyncio
    async def test_not_initialized(self):
        cache = RedisCache()
        cache._backend = None
        cache._initialized = False
        
        # Expect failed operations or auto-init attempt
        with patch("libx0t.core.cache.logger.error"):
            assert await cache.get("k") is None
            assert await cache.set("k", "v") is False

@pytest.mark.asyncio
async def test_cached_decorator():
    reset_cache()
    # Create valid cache for testing
    test_cache = RedisCache.create_for_testing()
    
    # Patch the global cache variable used by decorator
    with patch("libx0t.core.cache.cache", test_cache):
        call_count = 0
        
        @cached(ttl=60)
        async def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2
            
        # First call
        assert await compute(10) == 20
        assert call_count == 1
        
        # Cached call
        assert await compute(10) == 20
        assert call_count == 1
        
        # Different arg
        assert await compute(5) == 10
        assert call_count == 2
        
        # Invalidation
        await compute.invalidate(10)
        assert await compute(10) == 20
        assert call_count == 3

@pytest.mark.asyncio
async def test_cache_warming():
    reset_cache()
    test_cache = RedisCache.create_for_testing()
    
    # Patch global cache and cache_warmer._cache
    with patch("libx0t.core.cache.cache", test_cache):
        # Re-init cache warmer with new cache
        warmer = CacheWarming(test_cache)
        with patch("libx0t.core.cache.cache_warmer", warmer):
            
            call_count = 0
            block_event = asyncio.Event()
            
            async def slow_func(val):
                nonlocal call_count
                call_count += 1
                await block_event.wait()
                return val
                
            # Start two concurrent requests
            # Use warmer explicitly or patch get_or_warm usage
            # create_task needs to run inside loop
            
            task1 = asyncio.create_task(warmer.warm_cache("key", slow_func, 60, "res"))
            task2 = asyncio.create_task(warmer.warm_cache("key", slow_func, 60, "res"))
            
            # Allow execution
            block_event.set()
            
            res1 = await task1
            res2 = await task2
            
            assert res1 == "res"
            assert res2 == "res"
            # Should only run once due to thundering herd protection
            assert call_count == 1
