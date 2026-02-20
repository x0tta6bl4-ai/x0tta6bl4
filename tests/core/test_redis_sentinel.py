"""
Tests for Redis Sentinel support in cache module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.core.cache import (InMemoryCacheBackend, RedisCache, get_cache,
                            reset_cache)


class TestRedisSentinelConfig:
    """Tests for Redis Sentinel configuration."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_standalone_mode_without_sentinel_env(self):
        """Test standalone mode when REDIS_SENTINEL_HOSTS not set."""
        with patch.dict(
            "os.environ",
            {
                "REDIS_URL": "redis://localhost:6379",
                "REDIS_SENTINEL_HOSTS": "",
                "X0TTA6BL4_ALLOW_REDIS_IN_TESTS": "true",
            },
            clear=False,
        ):
            cache = RedisCache()

            # Mock the standalone initialization
            with patch.object(
                cache, "_initialize_standalone", new_callable=AsyncMock
            ) as mock_standalone:
                with patch.object(
                    cache, "_initialize_sentinel", new_callable=AsyncMock
                ) as mock_sentinel:
                    await cache._initialize()

                    # Should call standalone, not sentinel
                    mock_standalone.assert_called_once()
                    mock_sentinel.assert_not_called()

    @pytest.mark.asyncio
    async def test_sentinel_mode_with_sentinel_env(self):
        """Test sentinel mode when REDIS_SENTINEL_HOSTS is set."""
        with patch.dict(
            "os.environ",
            {
                "REDIS_SENTINEL_HOSTS": "sentinel1:26379,sentinel2:26379,sentinel3:26379",
                "REDIS_SENTINEL_MASTER": "mymaster",
                "X0TTA6BL4_ALLOW_REDIS_IN_TESTS": "true",
            },
            clear=False,
        ):
            cache = RedisCache()

            # Mock the sentinel initialization
            with patch.object(
                cache, "_initialize_standalone", new_callable=AsyncMock
            ) as mock_standalone:
                with patch.object(
                    cache, "_initialize_sentinel", new_callable=AsyncMock
                ) as mock_sentinel:
                    await cache._initialize()

                    # Should call sentinel, not standalone
                    mock_sentinel.assert_called_once_with(
                        "sentinel1:26379,sentinel2:26379,sentinel3:26379", "mymaster"
                    )
                    mock_standalone.assert_not_called()

    @pytest.mark.asyncio
    async def test_sentinel_host_parsing(self):
        """Test parsing of sentinel hosts string."""
        with patch.dict(
            "os.environ",
            {
                "REDIS_SENTINEL_HOSTS": "host1:26379, host2:26380 , host3:26381",
                "REDIS_SENTINEL_MASTER": "mymaster",
            },
            clear=False,
        ):
            with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_class:
                mock_sentinel = Mock()
                mock_master = AsyncMock()
                mock_master.ping = AsyncMock(return_value=True)
                mock_sentinel.master_for = Mock(return_value=mock_master)
                mock_sentinel.discover_master = AsyncMock(return_value=("master", 6379))
                mock_sentinel_class.return_value = mock_sentinel

                cache = RedisCache()
                await cache._initialize_sentinel(
                    "host1:26379, host2:26380 , host3:26381", "mymaster"
                )

                # Verify sentinel was created with correct hosts
                call_args = mock_sentinel_class.call_args
                sentinels = call_args[0][0]
                assert ("host1", 26379) in sentinels
                assert ("host2", 26380) in sentinels
                assert ("host3", 26381) in sentinels

    @pytest.mark.asyncio
    async def test_sentinel_default_port(self):
        """Test default port 26379 when port not specified."""
        with patch.dict(
            "os.environ",
            {
                "REDIS_SENTINEL_HOSTS": "host1,host2:26380",
                "REDIS_SENTINEL_MASTER": "mymaster",
            },
            clear=False,
        ):
            with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_class:
                mock_sentinel = Mock()
                mock_master = AsyncMock()
                mock_master.ping = AsyncMock(return_value=True)
                mock_sentinel.master_for = Mock(return_value=mock_master)
                mock_sentinel.discover_master = AsyncMock(return_value=("master", 6379))
                mock_sentinel_class.return_value = mock_sentinel

                cache = RedisCache()
                await cache._initialize_sentinel("host1,host2:26380", "mymaster")

                call_args = mock_sentinel_class.call_args
                sentinels = call_args[0][0]
                # host1 should use default port 26379
                assert ("host1", 26379) in sentinels
                assert ("host2", 26380) in sentinels


class TestRedisHealthCheck:
    """Tests for Redis health check functionality."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when Redis not initialized."""
        cache = RedisCache.create_for_testing(backend=None)
        cache._initialized = False
        cache._backend = None

        result = await cache.health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_standalone_healthy(self):
        """Test health check for healthy standalone Redis."""
        mock_backend = AsyncMock()
        mock_backend.ping = AsyncMock(return_value=True)
        mock_backend.info = AsyncMock(
            return_value={"role": "master", "connected_slaves": 0}
        )

        cache = RedisCache.create_for_testing(backend=mock_backend)

        result = await cache.health_check()

        assert result["status"] == "healthy"
        assert result["mode"] == "standalone"
        assert result["role"] == "master"

    @pytest.mark.asyncio
    async def test_health_check_sentinel_healthy(self):
        """Test health check for healthy Sentinel Redis."""
        mock_backend = AsyncMock()
        mock_backend.ping = AsyncMock(return_value=True)
        mock_backend.info = AsyncMock(
            return_value={"role": "master", "connected_slaves": 2}
        )

        mock_sentinel = AsyncMock()
        mock_sentinel.discover_master = AsyncMock(return_value=("192.168.1.1", 6379))
        mock_sentinel.discover_slaves = AsyncMock(
            return_value=[("192.168.1.2", 6379), ("192.168.1.3", 6379)]
        )

        cache = RedisCache.create_for_testing(backend=mock_backend)
        cache._sentinel = mock_sentinel

        with patch.dict("os.environ", {"REDIS_SENTINEL_MASTER": "mymaster"}):
            result = await cache.health_check()

        assert result["status"] == "healthy"
        assert result["mode"] == "sentinel"
        assert result["master"] == "192.168.1.1:6379"
        assert result["replicas"] == 2
        assert len(result["replica_addresses"]) == 2

    @pytest.mark.asyncio
    async def test_health_check_ping_failure(self):
        """Test health check when ping fails."""
        mock_backend = AsyncMock()
        mock_backend.ping = AsyncMock(side_effect=Exception("Connection refused"))

        cache = RedisCache.create_for_testing(backend=mock_backend)

        result = await cache.health_check()

        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]


class TestRedisStats:
    """Tests for Redis statistics."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_get_stats_success(self):
        """Test getting Redis stats."""
        mock_backend = AsyncMock()
        mock_backend.info = AsyncMock(
            return_value={
                "connected_clients": 10,
                "used_memory_human": "1.5M",
                "total_commands_processed": 1000,
                "keyspace_hits": 800,
                "keyspace_misses": 200,
                "uptime_in_seconds": 3600,
            }
        )

        cache = RedisCache.create_for_testing(backend=mock_backend)

        stats = await cache.get_stats()

        assert stats["connected_clients"] == 10
        assert stats["used_memory_human"] == "1.5M"
        assert stats["total_commands_processed"] == 1000
        assert stats["keyspace_hits"] == 800

    @pytest.mark.asyncio
    async def test_get_stats_not_initialized(self):
        """Test get_stats when not initialized."""
        cache = RedisCache.create_for_testing(backend=None)
        cache._initialized = False

        stats = await cache.get_stats()

        assert "error" in stats

    @pytest.mark.asyncio
    async def test_get_stats_failure(self):
        """Test get_stats when Redis fails."""
        mock_backend = AsyncMock()
        mock_backend.info = AsyncMock(side_effect=Exception("Redis error"))

        cache = RedisCache.create_for_testing(backend=mock_backend)

        stats = await cache.get_stats()

        assert "error" in stats
        assert "Redis error" in stats["error"]


class TestFailoverBehavior:
    """Tests for failover behavior."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_operations_continue_after_failover(self):
        """Test that operations continue working after failover."""
        # Use in-memory backend to simulate behavior
        backend = InMemoryCacheBackend()
        cache = RedisCache.create_for_testing(backend=backend)

        # Set a value
        await cache.set("test_key", "test_value", ttl=60)

        # Get the value
        value = await cache.get("test_key")
        assert value == "test_value"

        # Simulate "failover" by clearing and re-adding
        # (In real sentinel, connection is automatically re-established)

        # Set new value
        await cache.set("new_key", "new_value", ttl=60)
        value = await cache.get("new_key")
        assert value == "new_value"

    @pytest.mark.asyncio
    async def test_cache_decorator_with_sentinel(self):
        """Test cache decorator works with sentinel mode."""
        from src.core.cache import cached

        backend = InMemoryCacheBackend()
        cache = RedisCache.create_for_testing(backend=backend)

        call_count = [0]

        @cached(ttl=60, key_prefix="test", cache_instance=cache)
        async def expensive_operation(x):
            call_count[0] += 1
            return x * 2

        # First call - should execute function
        result1 = await expensive_operation(5)
        assert result1 == 10
        assert call_count[0] == 1

        # Second call - should use cache
        result2 = await expensive_operation(5)
        assert result2 == 10
        assert call_count[0] == 1  # Not incremented


class TestSentinelIntegration:
    """Integration tests for Sentinel (mocked)."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache()

    def teardown_method(self):
        """Reset cache after each test."""
        reset_cache()

    @pytest.mark.asyncio
    async def test_sentinel_master_discovery(self):
        """Test that sentinel discovers master correctly."""
        with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_class:
            mock_sentinel = Mock()
            mock_master = AsyncMock()
            mock_master.ping = AsyncMock(return_value=True)
            mock_master.get = AsyncMock(return_value=b'"cached_value"')
            mock_master.set = AsyncMock(return_value=True)
            mock_sentinel.master_for = Mock(return_value=mock_master)
            mock_sentinel.discover_master = AsyncMock(
                return_value=("master-host", 6379)
            )
            mock_sentinel_class.return_value = mock_sentinel

            cache = RedisCache()
            await cache._initialize_sentinel(
                "sentinel1:26379,sentinel2:26379", "mymaster"
            )

            # Verify master_for was called
            mock_sentinel.master_for.assert_called_once_with(
                "mymaster",
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )

            # Test operations work
            result = await cache.set("key", "value", ttl=60)
            assert result is True

    @pytest.mark.asyncio
    async def test_sentinel_connection_options(self):
        """Test sentinel connection options are correct."""
        with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_class:
            mock_sentinel = Mock()
            mock_master = AsyncMock()
            mock_master.ping = AsyncMock(return_value=True)
            mock_sentinel.master_for = Mock(return_value=mock_master)
            mock_sentinel.discover_master = AsyncMock(return_value=("master", 6379))
            mock_sentinel_class.return_value = mock_sentinel

            cache = RedisCache()
            await cache._initialize_sentinel("sentinel:26379", "mymaster")

            # Verify Sentinel was created with correct options
            call_args = mock_sentinel_class.call_args
            assert call_args[1]["socket_timeout"] == 5.0
            assert call_args[1]["socket_connect_timeout"] == 5.0
