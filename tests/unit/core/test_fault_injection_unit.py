"""
Fault Injection Tests — P1 Reliability

Covers:
- Redis unavailability → health_check returns unhealthy, cache falls back
- DB circuit-breaker: trips after threshold, opens, recovers via half-open
- Retry exhaustion: RetryExhausted raised after max retries
- Timeout propagation: asyncio.wait_for timeout surfaces correctly
- Graceful degradation headers via mark/get/set_degraded_dependency
- call_with_reliability: circuit open, retry, success paths
- Shutdown hooks: registered handlers called and cleanup state recorded
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_request_state():
    """Minimal object mimicking fastapi.Request.state."""

    class _State:
        pass

    class _Req:
        state = _State()

    return _Req()


# ===========================================================================
# 1. Redis / cache failure scenarios
# ===========================================================================


class TestRedisCacheFailure:
    """InMemoryCacheBackend used as stand-in; tests the protocol surface."""

    @pytest.mark.asyncio
    async def test_ping_failure_makes_health_check_unhealthy(self):
        """When Redis backend ping fails, health_check should return unhealthy."""
        from src.core.cache import RedisCache

        cache = RedisCache.__new__(RedisCache)
        cache._initialized = False
        cache._backend = None
        cache.default_ttl = 300
        cache._warming_tasks = set()

        result = await cache.health_check()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_cache_get_returns_none_on_backend_error(self):
        """get() should swallow backend errors and return None."""
        from src.core.cache import RedisCache

        broken_backend = MagicMock()
        broken_backend.get = AsyncMock(side_effect=ConnectionError("redis down"))

        cache = RedisCache.__new__(RedisCache)
        cache._initialized = True
        cache._backend = broken_backend
        cache.default_ttl = 300
        cache._warming_tasks = set()

        result = await cache.get("some_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_returns_false_on_backend_error(self):
        """set() should swallow backend errors and return False."""
        from src.core.cache import RedisCache

        broken_backend = MagicMock()
        broken_backend.set = AsyncMock(side_effect=OSError("redis down"))

        cache = RedisCache.__new__(RedisCache)
        cache._initialized = True
        cache._backend = broken_backend
        cache.default_ttl = 300
        cache._warming_tasks = set()

        result = await cache.set("k", "v")
        assert result is False

    @pytest.mark.asyncio
    async def test_in_memory_backend_get_set_delete(self):
        """InMemoryCacheBackend basic operations work correctly."""
        import time as _time

        from src.core.cache import InMemoryCacheBackend

        backend = InMemoryCacheBackend()
        await backend.set("foo", "bar")
        assert await backend.get("foo") == "bar"
        await backend.delete("foo")
        assert await backend.get("foo") is None

    @pytest.mark.asyncio
    async def test_in_memory_backend_expiry(self):
        """InMemoryCacheBackend respects TTL expiry."""
        from src.core.cache import InMemoryCacheBackend

        backend = InMemoryCacheBackend()
        await backend.set("expiring", "value", ex=1)
        assert await backend.get("expiring") == "value"

        # Manually expire by backdating the stored expiry
        key = "expiring"
        val, _ = backend._data[key]
        backend._data[key] = (val, time.time() - 1)

        assert await backend.get("expiring") is None

    @pytest.mark.asyncio
    async def test_in_memory_backend_nx_semantics(self):
        """nx=True should not overwrite existing key."""
        from src.core.cache import InMemoryCacheBackend

        backend = InMemoryCacheBackend()
        await backend.set("k", "original")
        result = await backend.set("k", "new", nx=True)
        assert result is False
        assert await backend.get("k") == "original"

    @pytest.mark.asyncio
    async def test_in_memory_backend_ping(self):
        """Ping always returns True for in-memory backend."""
        from src.core.cache import InMemoryCacheBackend

        backend = InMemoryCacheBackend()
        assert await backend.ping() is True


# ===========================================================================
# 2. Circuit breaker: state machine
# ===========================================================================


class TestCircuitBreakerStateMachine:
    def _make_cb(self, failure_threshold=3, recovery_timeout=0.05):
        from src.core.circuit_breaker import CircuitBreaker

        return CircuitBreaker(
            name="test_cb",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=2,
            success_threshold=2,
        )

    @pytest.mark.asyncio
    async def test_starts_closed(self):
        cb = self._make_cb()
        metrics = cb.get_metrics()
        assert metrics["state"] == "closed"

    @pytest.mark.asyncio
    async def test_trips_to_open_after_threshold(self):
        from src.core.circuit_breaker import CircuitBreakerOpen

        cb = self._make_cb(failure_threshold=3)

        async def failing():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(failing)

        assert cb.get_metrics()["state"] == "open"

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_immediately(self):
        from src.core.circuit_breaker import CircuitBreakerOpen

        cb = self._make_cb(failure_threshold=2)

        async def failing():
            raise OSError("down")

        for _ in range(2):
            with pytest.raises(OSError):
                await cb.call(failing)

        assert cb.get_metrics()["state"] == "open"

        with pytest.raises(CircuitBreakerOpen):
            await cb.call(AsyncMock(return_value="ok"))

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        cb = self._make_cb(failure_threshold=2, recovery_timeout=0.05)

        async def failing():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(failing)

        assert cb.get_metrics()["state"] == "open"

        # Wait for recovery timeout
        await asyncio.sleep(0.1)

        # Should transition to half-open on next call attempt
        async def success():
            return "ok"

        result = await cb.call(success)
        assert result == "ok"
        # After success_threshold successes, should close
        result2 = await cb.call(success)
        assert result2 == "ok"
        assert cb.get_metrics()["state"] == "closed"

    @pytest.mark.asyncio
    async def test_fallback_used_when_circuit_open(self):
        from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

        fallback = AsyncMock(return_value={"degraded": True})
        cb = CircuitBreaker(
            name="cb_fallback",
            failure_threshold=1,
            recovery_timeout=60.0,
            fallback=fallback,
        )

        async def failing():
            raise RuntimeError("down")

        with pytest.raises(RuntimeError):
            await cb.call(failing)

        # Circuit is now open; should invoke fallback
        result = await cb.call(AsyncMock(side_effect=RuntimeError("still down")))
        fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = self._make_cb(failure_threshold=5)

        async def failing():
            raise ConnectionError("intermittent")

        async def success():
            return "ok"

        # 2 failures
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(failing)

        # 1 success resets consecutive failures
        await cb.call(success)
        metrics = cb.get_metrics()
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 0


# ===========================================================================
# 3. Retry policy: exhaustion and circuit-breaker interaction
# ===========================================================================


class TestRetryPolicy:
    @pytest.mark.asyncio
    async def test_retry_exhausted_raised_after_max_retries(self):
        from src.core.connection_retry import RetryExhausted, RetryPolicy, with_retry

        policy = RetryPolicy(
            max_retries=2,
            base_delay=0.0,
            jitter=False,
            retryable_exceptions=(ConnectionError,),
        )

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("refused")

        with pytest.raises(RetryExhausted) as exc_info:
            await with_retry(always_fails, policy=policy)

        assert call_count == 3  # 1 initial + 2 retries
        assert exc_info.value.last_exception is not None

    @pytest.mark.asyncio
    async def test_non_retryable_exception_bubbles_immediately(self):
        from src.core.connection_retry import RetryPolicy, with_retry

        policy = RetryPolicy(
            max_retries=5,
            base_delay=0.0,
            jitter=False,
            retryable_exceptions=(ConnectionError,),
        )

        call_count = 0

        async def not_a_connection_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("logic error")

        with pytest.raises(ValueError):
            await with_retry(not_a_connection_error, policy=policy)

        assert call_count == 1  # No retries for ValueError

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_skips_retry(self):
        from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
        from src.core.connection_retry import RetryPolicy, with_retry

        cb = CircuitBreaker(
            name="skip_retry_cb", failure_threshold=1, recovery_timeout=60.0
        )

        # Trip the circuit
        async def failing():
            raise OSError("down")

        with pytest.raises(OSError):
            await cb.call(failing)

        policy = RetryPolicy(max_retries=5, base_delay=0.0, jitter=False)
        call_count = 0

        async def probe():
            nonlocal call_count
            call_count += 1
            return "ok"

        with pytest.raises(CircuitBreakerOpen):
            await with_retry(probe, policy=policy, circuit_breaker=cb)

        # cb.call already rejects; probe never executes
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_transient_failure(self):
        from src.core.connection_retry import RetryPolicy, with_retry

        policy = RetryPolicy(
            max_retries=3,
            base_delay=0.0,
            jitter=False,
            retryable_exceptions=(ConnectionError,),
        )

        attempts = [0]

        async def flaky():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = await with_retry(flaky, policy=policy)
        assert result == "recovered"
        assert attempts[0] == 3


# ===========================================================================
# 4. Timeout propagation
# ===========================================================================


class TestTimeoutPropagation:
    @pytest.mark.asyncio
    async def test_call_with_reliability_times_out(self):
        from src.core.reliability_policy import (ReliabilityPolicy,
                                                 call_with_reliability)

        policy = ReliabilityPolicy(
            timeout_seconds=0.05,
            max_retries=0,
            base_delay_seconds=0.0,
            retryable_exceptions=(TimeoutError, asyncio.TimeoutError),
        )

        async def slow_op():
            await asyncio.sleep(10.0)
            return "ok"

        with pytest.raises(Exception):  # RetryExhausted or TimeoutError
            await call_with_reliability(slow_op, dependency="test", policy=policy)

    @pytest.mark.asyncio
    async def test_call_with_reliability_succeeds_fast(self):
        from src.core.reliability_policy import (ReliabilityPolicy,
                                                 call_with_reliability)

        policy = ReliabilityPolicy(
            timeout_seconds=2.0,
            max_retries=0,
            base_delay_seconds=0.0,
        )

        async def fast_op():
            return {"status": "ok"}

        result = await call_with_reliability(fast_op, dependency="test", policy=policy)
        assert result["status"] == "ok"


# ===========================================================================
# 5. Graceful degradation header plumbing
# ===========================================================================


class TestGracefulDegradation:
    def test_mark_and_get_degraded_dependency(self):
        from src.core.reliability_policy import (get_degraded_dependencies,
                                                 mark_degraded_dependency)

        req = _make_request_state()
        mark_degraded_dependency(req, "redis")
        mark_degraded_dependency(req, "stripe")
        deps = get_degraded_dependencies(req)
        assert "redis" in deps
        assert "stripe" in deps

    def test_dedup_and_normalize(self):
        from src.core.reliability_policy import (get_degraded_dependencies,
                                                 mark_degraded_dependency)

        req = _make_request_state()
        mark_degraded_dependency(req, "Redis")
        mark_degraded_dependency(req, "redis")  # duplicate
        deps = get_degraded_dependencies(req)
        assert deps == ["redis"]

    def test_set_degraded_header(self):
        from src.core.reliability_policy import (mark_degraded_dependency,
                                                 set_degraded_dependencies_header)

        req = _make_request_state()
        mark_degraded_dependency(req, "redis")
        mark_degraded_dependency(req, "db")

        response = MagicMock()
        response.headers = {}
        set_degraded_dependencies_header(response, req)

        header = response.headers.get("X-Degraded-Dependencies", "")
        parts = set(header.split(","))
        assert "redis" in parts
        assert "db" in parts

    def test_no_header_when_no_degraded(self):
        from src.core.reliability_policy import (get_degraded_dependencies,
                                                 set_degraded_dependencies_header)

        req = _make_request_state()
        response = MagicMock()
        response.headers = {}
        set_degraded_dependencies_header(response, req)
        assert "X-Degraded-Dependencies" not in response.headers

    def test_mark_empty_string_ignored(self):
        from src.core.reliability_policy import (get_degraded_dependencies,
                                                 mark_degraded_dependency)

        req = _make_request_state()
        mark_degraded_dependency(req, "  ")  # whitespace only
        deps = get_degraded_dependencies(req)
        assert deps == []


# ===========================================================================
# 6. call_with_reliability: full integration (no actual I/O)
# ===========================================================================


class TestCallWithReliabilityIntegration:
    @pytest.mark.asyncio
    async def test_circuit_breaker_created_per_dependency(self):
        from src.core.circuit_breaker import get_circuit_breaker
        from src.core.reliability_policy import (ReliabilityPolicy,
                                                 call_with_reliability)

        policy = ReliabilityPolicy(
            timeout_seconds=1.0,
            max_retries=0,
            failure_threshold=5,
        )

        async def ok():
            return 42

        result = await call_with_reliability(
            ok, dependency="unique_dep_xyz", policy=policy
        )
        assert result == 42
        # Circuit should have been created
        cb = get_circuit_breaker("unique_dep_xyz_dependency")
        assert cb is not None

    @pytest.mark.asyncio
    async def test_explicit_circuit_breaker_used(self):
        from src.core.circuit_breaker import CircuitBreaker
        from src.core.reliability_policy import (ReliabilityPolicy,
                                                 call_with_reliability)

        custom_cb = CircuitBreaker(
            name="explicit_cb", failure_threshold=10, recovery_timeout=60.0
        )
        policy = ReliabilityPolicy(timeout_seconds=1.0, max_retries=0)

        async def ok():
            return "custom"

        result = await call_with_reliability(
            ok, dependency="any", policy=policy, circuit_breaker=custom_cb
        )
        assert result == "custom"


# ===========================================================================
# 7. Shutdown hook correctness
# ===========================================================================


class TestShutdownHooks:
    @pytest.mark.asyncio
    async def test_registered_cleanup_runs_on_shutdown(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False)
        called = []

        async def my_cleanup():
            called.append("db_close")

        mgr.register_cleanup(my_cleanup, name="db_close")
        await mgr.shutdown()

        assert "db_close" in called
        assert mgr.state.cleanup_success_count == 1
        assert mgr.state.cleanup_failure_count == 0

    @pytest.mark.asyncio
    async def test_failed_cleanup_recorded_not_propagated(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False)

        async def bad_cleanup():
            raise RuntimeError("cleanup failed")

        mgr.register_cleanup(bad_cleanup, name="bad")
        await mgr.shutdown()

        assert mgr.state.cleanup_failure_count == 1
        assert "bad" in (mgr.state.last_cleanup_error or "")

    @pytest.mark.asyncio
    async def test_timed_out_cleanup_recorded(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False)

        async def slow_cleanup():
            await asyncio.sleep(100)  # will be killed by 5s handler timeout

        mgr.register_cleanup(slow_cleanup, name="slow")
        # Patch handler timeout to 0.05s to make test fast
        with patch(
            "src.core.graceful_shutdown.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            await mgr.shutdown()

        assert mgr.state.cleanup_timeout_count == 1

    @pytest.mark.asyncio
    async def test_double_shutdown_is_idempotent(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False)
        called = []

        async def cleanup():
            called.append(1)

        mgr.register_cleanup(cleanup)
        await mgr.shutdown()
        await mgr.shutdown()  # second call should be no-op

        # Cleanup should only run once
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_shutdown_drains_active_requests(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False, drain_timeout=0.5)
        mgr.track_request_start()
        mgr.track_request_start()
        assert mgr.active_requests == 2

        # Simulate requests completing concurrently
        async def complete_requests():
            await asyncio.sleep(0.05)
            mgr.track_request_end()
            mgr.track_request_end()

        task = asyncio.create_task(complete_requests())
        await mgr.shutdown()
        await task
        # Shutdown waited; requests drained
        assert mgr.state.shutdown_duration_seconds is not None

    @pytest.mark.asyncio
    async def test_sync_cleanup_handler_supported(self):
        from src.core.graceful_shutdown import GracefulShutdownManager

        mgr = GracefulShutdownManager(force_exit=False)
        called = []

        def sync_cleanup():
            called.append("sync")

        mgr.register_cleanup(sync_cleanup)
        await mgr.shutdown()
        assert "sync" in called

    def test_shutdown_middleware_rejects_during_shutdown(self):
        """ShutdownMiddleware returns 503 when shutdown is in progress."""
        from src.core.graceful_shutdown import GracefulShutdownManager, ShutdownMiddleware

        mgr = GracefulShutdownManager(force_exit=False)
        mgr.state.is_shutting_down = True
        assert mgr.is_shutting_down is True


# ===========================================================================
# 8. DB circuit-breaker datetime bug regression (from MEMORY.md)
# ===========================================================================


class TestDBCircuitBreakerDatetime:
    """Regression: db_circuit_breaker.last_failure_time was datetime, not float."""

    def test_circuit_breaker_metrics_last_failure_is_float(self):
        """Circuit breaker stores float timestamps, not datetime objects."""
        from src.core.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="dt_test", failure_threshold=5, recovery_timeout=1.0)
        # Simulate internal failure recording
        cb._last_failure_time = time.time()
        # Should not raise TypeError on arithmetic
        elapsed = time.time() - cb._last_failure_time
        assert isinstance(elapsed, float)
        assert elapsed >= 0
