"""
Tests for monitoring, optimization, core/circuit_breaker, core/connection_retry,
security/password_auth, security/password_migration.

All modules verified importable before test creation.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Monitoring: MetricsRegistry
# ---------------------------------------------------------------------------

class TestMetricsRegistry:
    def test_request_count_increment(self):
        from src.monitoring.metrics import MetricsRegistry
        MetricsRegistry.request_count.labels(
            method="GET", endpoint="/health", status="200", api_key="test"
        ).inc()
        metric = MetricsRegistry.request_count.labels(
            method="GET", endpoint="/health", status="200", api_key="test"
        )
        assert metric._value._value >= 1

    def test_db_connections_gauge(self):
        from src.monitoring.metrics import MetricsRegistry
        MetricsRegistry.db_connections_active.set(5)
        assert MetricsRegistry.db_connections_active._value._value == 5

    def test_mapek_cycle_duration(self):
        from src.monitoring.metrics import MetricsRegistry
        MetricsRegistry.mapek_cycle_duration.labels(phase="monitor").observe(0.05)
        metric = MetricsRegistry.mapek_cycle_duration.labels(phase="monitor")
        assert metric._sum._value > 0

    def test_request_duration_histogram(self):
        from src.monitoring.metrics import MetricsRegistry
        MetricsRegistry.request_duration.labels(
            method="POST", endpoint="/api/v1/mesh", api_key="test"
        ).observe(0.25)
        metric = MetricsRegistry.request_duration.labels(
            method="POST", endpoint="/api/v1/mesh", api_key="test"
        )
        assert metric._sum._value > 0


# ---------------------------------------------------------------------------
# Core: CircuitBreaker (async)
# ---------------------------------------------------------------------------

class TestAsyncCircuitBreaker:
    @pytest.fixture
    def cb(self):
        from src.core.circuit_breaker import CircuitBreaker
        return CircuitBreaker(
            name="test-cb",
            failure_threshold=3,
            recovery_timeout=999,
            success_threshold=2,
        )

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, cb):
        from src.core.circuit_breaker import CircuitState
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call(self, cb):
        async def ok():
            return "ok"
        result = await cb.call(ok)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self, cb):
        from src.core.circuit_breaker import CircuitState, CircuitBreakerOpen
        async def fail():
            raise ValueError("boom")
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(fail)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_raises_circuit_breaker_open(self, cb):
        from src.core.circuit_breaker import CircuitBreakerOpen
        async def fail():
            raise ValueError("boom")
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(fail)
        async def ok():
            return "ok"
        with pytest.raises(CircuitBreakerOpen):
            await cb.call(ok)

    @pytest.mark.asyncio
    async def test_fallback_on_open(self):
        from src.core.circuit_breaker import CircuitBreaker, CircuitState
        async def fallback(*args, **kwargs):
            return "fallback-result"
        cb = CircuitBreaker(
            name="test-fb", failure_threshold=1,
            recovery_timeout=999, fallback=fallback,
        )
        async def fail():
            raise ValueError("boom")
        with pytest.raises(ValueError):
            await cb.call(fail)
        result = await cb.call(fail)
        assert result == "fallback-result"

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        from src.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(
            name="test-reset",
            failure_threshold=5,
            recovery_timeout=0,
            success_threshold=1,
        )
        async def ok():
            return "ok"
        async def fail():
            raise ValueError("boom")
        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb._failure_count == 1
        await cb.call(ok)
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, cb):
        async def ok():
            return "ok"
        await cb.call(ok)
        assert cb.metrics.total_requests >= 1
        assert cb.metrics.total_successes >= 1


# ---------------------------------------------------------------------------
# Core: Connection Retry
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_default_policy(self):
        from src.core.connection_retry import RetryPolicy
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay == 1.0

    def test_calculate_delay_exponential(self):
        from src.core.connection_retry import RetryPolicy
        p = RetryPolicy(base_delay=1.0, jitter=False, exponential_base=2.0)
        assert p.calculate_delay(0) == 1.0
        assert p.calculate_delay(1) == 2.0
        assert p.calculate_delay(2) == 4.0

    def test_calculate_delay_max_cap(self):
        from src.core.connection_retry import RetryPolicy
        p = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)
        assert p.calculate_delay(10) == 5.0

    def test_jitter_adds_variance(self):
        from src.core.connection_retry import RetryPolicy
        p = RetryPolicy(base_delay=1.0, jitter=True, jitter_max=1.0)
        delays = [p.calculate_delay(0) for _ in range(10)]
        assert len(set(delays)) > 1  # Not all identical


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        from src.core.connection_retry import RetryPolicy, with_retry
        p = RetryPolicy(max_retries=3, base_delay=0, jitter=False)
        call_count = 0

        async def ok():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await with_retry(ok, policy=p)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        from src.core.connection_retry import RetryPolicy, with_retry
        p = RetryPolicy(max_retries=2, base_delay=0, jitter=False)
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = await with_retry(flaky, policy=p)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_raises(self):
        from src.core.connection_retry import RetryPolicy, RetryExhausted, with_retry
        p = RetryPolicy(max_retries=1, base_delay=0, jitter=False)

        async def always_fail():
            raise ConnectionError("permanent")

        with pytest.raises(RetryExhausted):
            await with_retry(always_fail, policy=p)


# ---------------------------------------------------------------------------
# Optimization: LRUCache
# ---------------------------------------------------------------------------

class TestLRUCache:
    def test_set_get(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache(max_size=10)
        cache.set("k1", "v1")
        assert cache.get("k1") == "v1"

    def test_miss_returns_none(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache()
        assert cache.get("nonexistent") is None

    def test_eviction_on_max_size(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache(max_size=3)
        for i in range(5):
            cache.set(f"k{i}", f"v{i}")
        assert cache.stats.evictions >= 2
        assert cache.get("k0") is None  # evicted
        assert cache.get("k4") == "v4"  # still present

    def test_lru_ordering(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # access "a" → moves to end
        cache.set("d", 4)  # should evict "b" (least recently used)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_ttl_expiration(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache(max_size=10, ttl_seconds=0)
        cache.set("k1", "v1")
        time.sleep(0.01)
        assert cache.get("k1") is None  # expired

    def test_stats_tracking(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache()
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.get_stats()
        assert stats.hits >= 1
        assert stats.misses >= 1

    def test_clear(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.stats.items_cached == 0

    def test_overwrite_key(self):
        from src.optimization.performance_core import LRUCache
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("a", 2)
        assert cache.get("a") == 2
        assert len(cache.cache) == 1


class TestCacheStats:
    def test_hit_rate_zero_when_empty(self):
        from src.optimization.performance_core import CacheStats
        stats = CacheStats()
        stats.update()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        from src.optimization.performance_core import CacheStats
        stats = CacheStats(hits=7, misses=3)
        stats.update()
        assert stats.hit_rate == 0.7

    def test_to_dict(self):
        from src.optimization.performance_core import CacheStats
        stats = CacheStats(hits=10, misses=5, evictions=2, items_cached=8)
        d = stats.to_dict()
        assert d["hits"] == 10
        assert d["evictions"] == 2
        assert d["hit_rate_percent"] > 0


# ---------------------------------------------------------------------------
# Security: Password Auth
# ---------------------------------------------------------------------------

class TestPasswordAuth:
    def test_hash_password(self):
        from src.security.password_auth import hash_password
        h = hash_password("mypassword123")
        assert h.startswith("$2")
        assert len(h) > 20

    def test_verify_correct_password(self):
        from src.security.password_auth import hash_password, verify_password
        h = hash_password("correct")
        valid, rehash = verify_password("correct", h)
        assert valid is True
        assert rehash is False

    def test_verify_wrong_password(self):
        from src.security.password_auth import hash_password, verify_password
        h = hash_password("correct")
        valid, _ = verify_password("wrong", h)
        assert valid is False

    def test_verify_non_bcrypt_rejects(self):
        from src.security.password_auth import verify_password
        valid, rehash = verify_password("any", "not_a_bcrypt_hash")
        assert valid is False
        assert rehash is False

    def test_verify_oidc_sentinel_rejects(self):
        from src.security.password_auth import verify_password
        valid, _ = verify_password("test", "OIDC_USER")
        assert valid is False

    def test_different_hashes_for_same_password(self):
        from src.security.password_auth import hash_password
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts


# ---------------------------------------------------------------------------
# Security: Password Migration
# ---------------------------------------------------------------------------

class TestPasswordMigration:
    def test_hash_password(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        h = m.hash_password("strongpass123")
        assert h.startswith("$2b$")

    def test_hash_short_password_raises(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        with pytest.raises(ValueError, match="at least 8 characters"):
            m.hash_password("short")

    def test_hash_non_string_raises(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        with pytest.raises(TypeError):
            m.hash_password(123)

    def test_verify_bcrypt(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        h = m.hash_password("mypass123")
        assert m.verify_password("mypass123", h) is True
        assert m.verify_password("wrong", h) is False

    def test_rehash_md5_to_bcrypt(self):
        import hashlib
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        md5_hash = hashlib.md5(b"old_password").hexdigest()
        marker = m.rehash_md5_to_bcrypt(md5_hash)
        # Returns a migration marker, not a bcrypt hash
        assert marker.startswith("__NEEDS_MIGRATION__")
        assert m.verify_is_migration_marker(marker)

    def test_migration_stats(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        # hash_password doesn't increment stats (stats track migration, not hashing)
        m.hash_password("test1234")
        assert m.stats.total_processed == 0  # stats are for migration operations

    def test_verify_legacy_or_bcrypt_bcrypt(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        h = m.hash_password("test1234")
        is_valid, needs_rehash = m.verify_legacy_or_bcrypt("test1234", h)
        assert is_valid is True
        assert needs_rehash is False

    def test_verify_legacy_or_bcrypt_md5_forces_reset(self):
        import hashlib
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        md5 = hashlib.md5(b"oldpass").hexdigest()
        # MD5 verification always returns (False, True) to force password reset
        is_valid, needs_rehash = m.verify_legacy_or_bcrypt("oldpass", md5)
        assert is_valid is False  # MD5 is rejected, forces reset
        assert needs_rehash is True  # Signals that rehashing is needed

    def test_verify_legacy_or_bcrypt_unknown_format(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        is_valid, needs_rehash = m.verify_legacy_or_bcrypt("pass", "unknown_format")
        assert is_valid is False
        assert needs_rehash is False

    def test_is_md5_hash(self):
        from src.security.password_migration import PasswordMigrator
        m = PasswordMigrator()
        import hashlib
        md5 = hashlib.md5(b"test").hexdigest()
        assert m.is_md5_hash(md5) is True
        assert m.is_md5_hash("$2b$12$abc") is False
        assert m.is_md5_hash("") is False
        assert m.is_md5_hash("not_md5_length") is False


# ---------------------------------------------------------------------------
# Core: create_circuit_breaker / get_circuit_breaker
# ---------------------------------------------------------------------------

class TestCircuitBreakerFactory:
    def test_create_and_get(self):
        from src.core.circuit_breaker import create_circuit_breaker, get_circuit_breaker
        cb = create_circuit_breaker("test-factory-cb", failure_threshold=10)
        assert cb is not None
        fetched = get_circuit_breaker("test-factory-cb")
        assert fetched is cb

    def test_get_nonexistent_returns_none(self):
        from src.core.circuit_breaker import get_circuit_breaker
        assert get_circuit_breaker("does-not-exist") is None
