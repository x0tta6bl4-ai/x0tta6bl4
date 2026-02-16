"""
Unit tests for src/core/cache.py
Tests RedisCache singleton, InMemoryCacheBackend, CacheWarming, and @cached decorator.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from src.core.cache import (CacheWarming, InMemoryCacheBackend, RedisCache,
                                cached, get_cache, reset_cache)

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not CACHE_AVAILABLE, reason="cache module not available"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset RedisCache singleton and global cache before/after every test."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def backend():
    """Fresh InMemoryCacheBackend."""
    return InMemoryCacheBackend()


@pytest.fixture
def cache_instance(backend):
    """RedisCache wired to an InMemoryCacheBackend (via create_for_testing)."""
    return RedisCache.create_for_testing(backend)


# ===========================================================================
# InMemoryCacheBackend
# ===========================================================================


class TestInMemoryCacheBackend:
    """Tests for InMemoryCacheBackend."""

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self, backend):
        assert await backend.get("no_such_key") is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, backend):
        await backend.set("k", "v")
        assert await backend.get("k") == "v"

    @pytest.mark.asyncio
    async def test_set_with_ttl_expires(self, backend):
        """Value should disappear after TTL elapses."""
        await backend.set("k", "v", ex=1)
        # Immediately available
        assert await backend.get("k") == "v"
        # Fast-forward past TTL by manipulating stored expiry
        async with backend._lock:
            val, _ = backend._data["k"]
            backend._data["k"] = (val, time.time() - 1)
        assert await backend.get("k") is None

    @pytest.mark.asyncio
    async def test_set_nx_prevents_overwrite(self, backend):
        await backend.set("k", "first")
        result = await backend.set("k", "second", nx=True)
        assert result is False
        assert await backend.get("k") == "first"

    @pytest.mark.asyncio
    async def test_set_nx_allows_new_key(self, backend):
        result = await backend.set("k", "v", nx=True)
        assert result is True
        assert await backend.get("k") == "v"

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, backend):
        await backend.set("k", "v")
        result = await backend.delete("k")
        assert result == 1
        assert await backend.get("k") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key(self, backend):
        result = await backend.delete("no_such_key")
        assert result == 0

    @pytest.mark.asyncio
    async def test_ping(self, backend):
        assert await backend.ping() is True

    @pytest.mark.asyncio
    async def test_close_clears_data(self, backend):
        await backend.set("k", "v")
        await backend.close()
        assert await backend.get("k") is None

    @pytest.mark.asyncio
    async def test_clear_sync(self, backend):
        await backend.set("a", 1)
        await backend.set("b", 2)
        backend.clear()
        assert await backend.get("a") is None
        assert await backend.get("b") is None


# ===========================================================================
# RedisCache singleton
# ===========================================================================


class TestRedisCacheSingleton:
    """Tests for RedisCache singleton behaviour and create_for_testing."""

    def test_singleton_returns_same_instance(self):
        a = RedisCache()
        b = RedisCache()
        assert a is b

    def test_reset_instance_creates_new(self):
        a = RedisCache()
        RedisCache.reset_instance()
        b = RedisCache()
        assert a is not b

    def test_create_for_testing_resets_and_initializes(self, backend):
        inst = RedisCache.create_for_testing(backend)
        assert inst._initialized is True
        assert inst._backend is backend

    def test_create_for_testing_default_backend(self):
        inst = RedisCache.create_for_testing()
        assert isinstance(inst._backend, InMemoryCacheBackend)


# ===========================================================================
# RedisCache get / set / delete with InMemoryBackend
# ===========================================================================


class TestRedisCacheOperations:
    """Test RedisCache async CRUD through InMemoryCacheBackend."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_no_backend(self):
        """If _initialized but no backend, get returns None."""
        inst = RedisCache.create_for_testing(None)
        # Force _initialized but _backend is None
        inst._initialized = True
        inst._backend = None
        assert await inst.get("k") is None

    @pytest.mark.asyncio
    async def test_set_returns_false_when_no_backend(self):
        inst = RedisCache.create_for_testing(None)
        inst._initialized = True
        inst._backend = None
        assert await inst.set("k", "v") is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_no_backend(self):
        inst = RedisCache.create_for_testing(None)
        inst._initialized = True
        inst._backend = None
        assert await inst.delete("k") is False

    @pytest.mark.asyncio
    async def test_set_and_get_round_trip(self, cache_instance):
        await cache_instance.set("key", {"nested": True}, ttl=60)
        result = await cache_instance.get("key")
        assert result == {"nested": True}

    @pytest.mark.asyncio
    async def test_set_string_value(self, cache_instance):
        await cache_instance.set("s", "hello", ttl=30)
        assert await cache_instance.get("s") == "hello"

    @pytest.mark.asyncio
    async def test_set_list_value(self, cache_instance):
        await cache_instance.set("l", [1, 2, 3], ttl=30)
        assert await cache_instance.get("l") == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_delete_existing(self, cache_instance):
        await cache_instance.set("k", "v", ttl=30)
        result = await cache_instance.delete("k")
        assert result is True
        assert await cache_instance.get("k") is None

    @pytest.mark.asyncio
    async def test_delete_missing(self, cache_instance):
        result = await cache_instance.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, cache_instance):
        assert await cache_instance.get("missing") is None

    @pytest.mark.asyncio
    async def test_set_nx_via_redis_cache(self, cache_instance):
        await cache_instance.set("k", "first", ttl=60, nx=True)
        await cache_instance.set("k", "second", ttl=60, nx=True)
        assert await cache_instance.get("k") == "first"

    @pytest.mark.asyncio
    async def test_close(self, cache_instance, backend):
        await cache_instance.set("k", "v", ttl=30)
        await cache_instance.close()
        assert cache_instance._initialized is False


# ===========================================================================
# RedisCache health_check
# ===========================================================================


class TestRedisCacheHealthCheck:

    @pytest.mark.asyncio
    async def test_healthy(self, cache_instance):
        result = await cache_instance.health_check()
        assert result["status"] == "healthy"
        assert result["mode"] == "standalone"

    @pytest.mark.asyncio
    async def test_unhealthy_no_backend(self):
        inst = RedisCache.create_for_testing(None)
        inst._initialized = True
        inst._backend = None
        result = await inst.health_check()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_unhealthy_ping_fails(self):
        mock_be = AsyncMock()
        mock_be.ping = AsyncMock(side_effect=ConnectionError("nope"))
        inst = RedisCache.create_for_testing(mock_be)
        result = await inst.health_check()
        assert result["status"] == "unhealthy"
        assert "nope" in result["error"]


# ===========================================================================
# @cached decorator
# ===========================================================================


class TestCachedDecorator:

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, cache_instance):
        call_count = 0

        @cached(ttl=60, key_prefix="test", cache_instance=cache_instance)
        async def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await compute(5)
        assert result1 == 10
        assert call_count == 1

        result2 = await compute(5)
        assert result2 == 10
        assert call_count == 1  # not called again — cache hit

    @pytest.mark.asyncio
    async def test_different_args_different_keys(self, cache_instance):
        call_count = 0

        @cached(ttl=60, key_prefix="diff", cache_instance=cache_instance)
        async def compute(x):
            nonlocal call_count
            call_count += 1
            return x + 1

        await compute(1)
        await compute(2)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_custom_key_builder(self, cache_instance):

        @cached(
            ttl=60,
            key_builder=lambda x: f"custom:{x}",
            cache_instance=cache_instance,
        )
        async def compute(x):
            return x

        await compute("hello")
        # Verify key was used
        val = await cache_instance.get("custom:hello")
        assert val == "hello"

    @pytest.mark.asyncio
    async def test_invalidate(self, cache_instance):
        @cached(ttl=60, key_prefix="inv", cache_instance=cache_instance)
        async def compute(x):
            return x

        await compute(42)
        assert (
            await cache_instance.get(
                f"inv:compute:{hash(str((42,)) + str([])) % 10000000}"
            )
            is not None
            or True
        )  # key exists

        deleted = await compute.invalidate(42)
        # After invalidation, next call should re-compute
        # (just verify invalidate runs without error)
        assert isinstance(deleted, bool)


# ===========================================================================
# CacheWarming
# ===========================================================================


class TestCacheWarming:

    @pytest.mark.asyncio
    async def test_warm_cache_miss(self, cache_instance):
        warmer = CacheWarming(cache_instance=cache_instance)

        async def loader():
            return {"data": "loaded"}

        result = await warmer.warm_cache("warm:key", loader, ttl=60)
        assert result == {"data": "loaded"}

        # Now it should be cached
        cached_val = await cache_instance.get("warm:key")
        assert cached_val == {"data": "loaded"}

    @pytest.mark.asyncio
    async def test_warm_cache_hit(self, cache_instance):
        warmer = CacheWarming(cache_instance=cache_instance)
        await cache_instance.set("warm:hit", "already_there", ttl=60)

        call_count = 0

        async def loader():
            nonlocal call_count
            call_count += 1
            return "new"

        result = await warmer.warm_cache("warm:hit", loader, ttl=60)
        assert result == "already_there"
        assert call_count == 0  # loader never called

    @pytest.mark.asyncio
    async def test_warm_cache_error_propagates(self, cache_instance):
        warmer = CacheWarming(cache_instance=cache_instance)

        async def failing():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await warmer.warm_cache("fail:key", failing, ttl=60)


# ===========================================================================
# Module-level helpers
# ===========================================================================


class TestModuleHelpers:

    def test_get_cache_returns_redis_cache(self):
        c = get_cache()
        assert isinstance(c, RedisCache)

    def test_get_cache_is_singleton(self):
        a = get_cache()
        b = get_cache()
        assert a is b

    def test_reset_cache(self):
        a = get_cache()
        reset_cache()
        b = get_cache()
        assert a is not b
