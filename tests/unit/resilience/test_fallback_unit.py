"""Unit tests for src/resilience/fallback.py."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from src.resilience.fallback import (
    AsyncFallback,
    CacheFallback,
    ChainFallback,
    CircuitFallback,
    DefaultValueFallback,
    FallbackChainBuilder,
    FallbackConfig,
    FallbackExecutor,
    FallbackMetrics,
    FallbackResult,
    FallbackType,
    with_fallback,
    with_fallback_chain,
)


# ── FallbackType ────────────────────────────────────────────────────

class TestFallbackType:
    def test_enum_values(self):
        assert FallbackType.DEFAULT.value == "default"
        assert FallbackType.CACHE.value == "cache"
        assert FallbackType.CHAIN.value == "chain"
        assert FallbackType.CIRCUIT.value == "circuit"
        assert FallbackType.ASYNC.value == "async"


# ── FallbackResult ──────────────────────────────────────────────────

class TestFallbackResult:
    def test_primary_success(self):
        r = FallbackResult(value=42, from_fallback=False)
        assert r.value == 42
        assert r.from_fallback is False
        assert r.fallback_name is None
        assert r.original_error is None
        assert r.execution_time_ms == 0.0
        assert r.cache_hit is False

    def test_fallback_result(self):
        err = ValueError("boom")
        r = FallbackResult(
            value="default",
            from_fallback=True,
            fallback_name="my_fallback",
            original_error=err,
            execution_time_ms=12.3,
            cache_hit=True,
        )
        assert r.from_fallback is True
        assert r.fallback_name == "my_fallback"
        assert r.original_error is err
        assert r.execution_time_ms == 12.3
        assert r.cache_hit is True


# ── FallbackConfig ──────────────────────────────────────────────────

class TestFallbackConfig:
    def test_defaults(self):
        cfg = FallbackConfig()
        assert cfg.enable_cache is True
        assert cfg.cache_ttl_seconds == 300
        assert cfg.max_cache_size == 1000
        assert cfg.log_fallbacks is True
        assert cfg.metrics_enabled is True
        assert cfg.async_timeout_ms == 5000

    def test_custom(self):
        cfg = FallbackConfig(enable_cache=False, cache_ttl_seconds=60)
        assert cfg.enable_cache is False
        assert cfg.cache_ttl_seconds == 60


# ── FallbackMetrics ─────────────────────────────────────────────────

class TestFallbackMetrics:
    def test_defaults(self):
        m = FallbackMetrics()
        assert m.total_calls == 0
        assert m.primary_successes == 0

    def test_to_dict_zero(self):
        d = FallbackMetrics().to_dict()
        assert d["total_calls"] == 0
        assert d["primary_success_rate"] == 1.0
        assert d["fallback_rate"] == 0
        assert d["avg_fallback_time_ms"] == 0

    def test_to_dict_with_values(self):
        m = FallbackMetrics(
            total_calls=10,
            primary_successes=8,
            primary_failures=2,
            fallback_successes=2,
            fallback_failures=0,
            total_fallback_time_ms=100.0,
        )
        d = m.to_dict()
        assert d["primary_success_rate"] == pytest.approx(0.8)
        assert d["fallback_rate"] == pytest.approx(0.2)
        assert d["avg_fallback_time_ms"] == pytest.approx(50.0)


# ── DefaultValueFallback ────────────────────────────────────────────

class TestDefaultValueFallback:
    def test_returns_default(self):
        fb = DefaultValueFallback(default_value={"status": "degraded"})
        result = fb.handle(RuntimeError("fail"))
        assert result == {"status": "degraded"}

    def test_custom_name(self):
        fb = DefaultValueFallback(default_value=0, name="zero_fallback")
        assert fb.name == "zero_fallback"

    def test_returns_none_default(self):
        fb = DefaultValueFallback(default_value=None)
        assert fb.handle(Exception("x")) is None

    def test_returns_list_default(self):
        fb = DefaultValueFallback(default_value=[])
        assert fb.handle(Exception("x")) == []


# ── CacheFallback ───────────────────────────────────────────────────

class TestCacheFallback:
    def test_cache_miss_reraises(self):
        fb = CacheFallback(ttl_seconds=60)
        err = ValueError("no cache")
        with pytest.raises(ValueError, match="no cache"):
            fb.handle(err, "key1")

    def test_set_and_get(self):
        fb = CacheFallback(ttl_seconds=60)
        fb.set("k", "hello")
        assert fb.get("k") == "hello"

    def test_cache_hit_after_set(self):
        fb = CacheFallback(ttl_seconds=60)
        fb.set("user_id=1", "alice")
        result = fb.handle(RuntimeError("fail"), "user_id=1")
        assert result == "alice"

    def test_cache_miss_increments_misses(self):
        fb = CacheFallback()
        fb.get("nonexistent")
        stats = fb.get_stats()
        assert stats["misses"] == 1

    def test_cache_hit_increments_hits(self):
        fb = CacheFallback()
        fb.set("x", 42)
        fb.get("x")
        stats = fb.get_stats()
        assert stats["hits"] == 1

    def test_expired_entry_returns_none(self):
        fb = CacheFallback(ttl_seconds=0)
        fb.set("k", "old_value")
        time.sleep(0.01)
        result = fb.get("k")
        assert result is None

    def test_max_size_eviction(self):
        fb = CacheFallback(max_size=3)
        fb.set("k1", 1)
        fb.set("k2", 2)
        fb.set("k3", 3)
        fb.set("k4", 4)  # triggers eviction
        assert len(fb._cache) <= 3

    def test_make_key_stable(self):
        fb = CacheFallback()
        key1 = fb._make_key("a", "b", x=1)
        key2 = fb._make_key("a", "b", x=1)
        assert key1 == key2

    def test_get_stats_structure(self):
        fb = CacheFallback(name="test_cache")
        stats = fb.get_stats()
        assert stats["name"] == "test_cache"
        assert stats["type"] == "cache"
        assert "hit_rate" in stats

    def test_thread_safety(self):
        fb = CacheFallback(max_size=100)
        errors = []

        def writer():
            for i in range(50):
                try:
                    fb.set(f"key{i}", i)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ── ChainFallback ───────────────────────────────────────────────────

class TestChainFallback:
    def test_first_fallback_succeeds(self):
        fb1 = DefaultValueFallback("first")
        fb2 = DefaultValueFallback("second")
        chain = ChainFallback([fb1.handle, fb2.handle])
        result = chain.handle(RuntimeError("fail"))
        assert result == "first"

    def test_falls_through_to_second(self):
        def failing(e, *a, **kw):
            raise RuntimeError("fallback1 failed")

        fb2 = DefaultValueFallback("second")
        chain = ChainFallback([failing, fb2.handle])
        result = chain.handle(RuntimeError("original"))
        assert result == "second"

    def test_all_fallbacks_fail_raises(self):
        def failing(e, *a, **kw):
            raise RuntimeError("all failed")

        chain = ChainFallback([failing, failing])
        with pytest.raises(RuntimeError, match="all failed"):
            chain.handle(RuntimeError("original"))

    def test_metrics_tracked(self):
        calls = []
        def fb(e, *a, **kw):
            calls.append(1)
            return "ok"

        chain = ChainFallback([fb])
        chain.handle(Exception("x"))
        stats = chain.get_stats()
        assert stats["fallback_metrics"][0]["successes"] == 1

    def test_get_stats_structure(self):
        chain = ChainFallback([lambda e: None], name="my_chain")
        stats = chain.get_stats()
        assert stats["name"] == "my_chain"
        assert stats["type"] == "chain"
        assert stats["fallback_count"] == 1


# ── CircuitFallback ─────────────────────────────────────────────────

class TestCircuitFallback:
    def _mock_cb(self, is_open: bool, state: str = "OPEN") -> MagicMock:
        cb = MagicMock()
        cb.is_open.return_value = is_open
        cb.get_state.return_value = state
        return cb

    def test_circuit_open_invokes_fallback(self):
        cb = self._mock_cb(is_open=True)
        fallback = DefaultValueFallback("degraded")
        cf = CircuitFallback(cb, fallback.handle)
        result = cf.handle(RuntimeError("fail"))
        assert result == "degraded"

    def test_circuit_closed_reraises(self):
        cb = self._mock_cb(is_open=False)
        fallback = DefaultValueFallback("degraded")
        cf = CircuitFallback(cb, fallback.handle)
        with pytest.raises(RuntimeError):
            cf.handle(RuntimeError("fail"))

    def test_circuit_open_increments_counter(self):
        cb = self._mock_cb(is_open=True)
        cf = CircuitFallback(cb, lambda e: "ok")
        cf.handle(RuntimeError("fail"))
        cf.handle(RuntimeError("fail"))
        stats = cf.get_stats()
        assert stats["circuit_fallbacks"] == 2

    def test_get_stats_structure(self):
        cb = self._mock_cb(is_open=False, state="CLOSED")
        cf = CircuitFallback(cb, lambda e: None, name="my_circuit")
        stats = cf.get_stats()
        assert stats["name"] == "my_circuit"
        assert stats["type"] == "circuit"
        assert stats["circuit_state"] == "CLOSED"

    def test_no_is_open_attr_reraises(self):
        cb = object()  # no is_open method
        cf = CircuitFallback(cb, lambda e: "ok")
        with pytest.raises(RuntimeError):
            cf.handle(RuntimeError("fail"))


# ── AsyncFallback ───────────────────────────────────────────────────

class TestAsyncFallback:
    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        async def async_op():
            return "async_result"

        af = AsyncFallback(
            fallback=async_op,
            immediate_value="immediate",
            timeout_ms=1000,
        )
        result = await af.execute_async("key1")
        assert result == "async_result"
        assert af._async_completions == 1

    @pytest.mark.asyncio
    async def test_execute_async_timeout(self):
        async def slow_op():
            await asyncio.sleep(10)
            return "too_late"

        af = AsyncFallback(
            fallback=slow_op,
            immediate_value="immediate",
            timeout_ms=10,  # 10ms timeout
        )
        with pytest.raises(asyncio.TimeoutError):
            await af.execute_async("key2")
        assert af._async_timeouts == 1

    def test_handle_returns_immediate(self):
        async def async_op():
            return "async"

        af = AsyncFallback(
            fallback=async_op,
            immediate_value="immediate",
        )
        result = af.handle(RuntimeError("fail"))
        assert result == "immediate"
        assert af._immediate_returns == 1

    def test_get_stats_structure(self):
        af = AsyncFallback(
            fallback=AsyncMock(),
            immediate_value=None,
            name="my_async",
        )
        stats = af.get_stats()
        assert stats["name"] == "my_async"
        assert stats["type"] == "async"
        assert "async_completions" in stats
        assert "async_timeouts" in stats


# ── FallbackChainBuilder ────────────────────────────────────────────

class TestFallbackChainBuilder:
    def test_build_with_default(self):
        chain = (
            FallbackChainBuilder()
            .with_default({"status": "degraded"})
            .build()
        )
        result = chain.handle(RuntimeError("fail"))
        assert result == {"status": "degraded"}

    def test_build_with_cache(self):
        chain = (
            FallbackChainBuilder()
            .with_cache(ttl_seconds=60)
            .with_default("safe")
            .build()
        )
        # No cache entry → falls through to default
        result = chain.handle(RuntimeError("fail"))
        assert result == "safe"

    def test_build_with_custom(self):
        chain = (
            FallbackChainBuilder()
            .with_custom(lambda e: "custom_result")
            .build()
        )
        assert chain.handle(RuntimeError("fail")) == "custom_result"

    def test_build_with_name(self):
        chain = (
            FallbackChainBuilder()
            .with_name("named_chain")
            .with_default(None)
            .build()
        )
        assert chain.name == "named_chain"

    def test_build_empty_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            FallbackChainBuilder().build()

    def test_with_config(self):
        cfg = FallbackConfig(cache_ttl_seconds=999)
        builder = FallbackChainBuilder().with_config(cfg)
        assert builder._config.cache_ttl_seconds == 999

    def test_with_circuit(self):
        cb = MagicMock()
        cb.is_open.return_value = False
        chain = (
            FallbackChainBuilder()
            .with_default("ok")
            .with_circuit(cb)
            .build()
        )
        # circuit closed → reraises, but chain has only 1 fallback
        with pytest.raises(RuntimeError):
            chain.handle(RuntimeError("fail"))


# ── FallbackExecutor ────────────────────────────────────────────────

class TestFallbackExecutor:
    def test_primary_success(self):
        executor = FallbackExecutor(fallback=lambda e: "fallback")
        result = executor.execute(lambda: "primary")
        assert result.value == "primary"
        assert result.from_fallback is False

    def test_fallback_on_failure(self):
        def failing():
            raise RuntimeError("primary failed")

        executor = FallbackExecutor(fallback=lambda e: "fallback_value")
        result = executor.execute(failing)
        assert result.value == "fallback_value"
        assert result.from_fallback is True
        assert isinstance(result.original_error, RuntimeError)

    def test_both_fail_raises(self):
        def failing():
            raise RuntimeError("primary")

        def failing_fallback(e):
            raise RuntimeError("fallback")

        executor = FallbackExecutor(fallback=failing_fallback)
        with pytest.raises(RuntimeError, match="fallback"):
            executor.execute(failing)

    def test_metrics_primary_success(self):
        executor = FallbackExecutor(fallback=lambda e: None)
        executor.execute(lambda: 42)
        metrics = executor.get_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["primary_successes"] == 1
        assert metrics["primary_failures"] == 0

    def test_metrics_fallback_triggered(self):
        executor = FallbackExecutor(fallback=lambda e: "fb")
        executor.execute(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        metrics = executor.get_metrics()
        assert metrics["primary_failures"] == 1
        assert metrics["fallback_successes"] == 1

    def test_cache_enabled_stores_result(self):
        cfg = FallbackConfig(enable_cache=True, cache_ttl_seconds=60)
        executor = FallbackExecutor(fallback=lambda e: None, config=cfg)
        executor.execute(lambda: "cached_value")
        # Cache should have an entry
        assert executor._cache is not None
        assert len(executor._cache._cache) == 1

    def test_cache_disabled(self):
        cfg = FallbackConfig(enable_cache=False)
        executor = FallbackExecutor(fallback=lambda e: None, config=cfg)
        assert executor._cache is None

    def test_execution_time_recorded(self):
        executor = FallbackExecutor(fallback=lambda e: None)
        result = executor.execute(lambda: 42)
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_async_primary_success(self):
        async def primary():
            return "async_ok"

        executor = FallbackExecutor(fallback=lambda e: None)
        result = await executor.execute_async(primary)
        assert result.value == "async_ok"
        assert result.from_fallback is False

    @pytest.mark.asyncio
    async def test_execute_async_with_async_fallback(self):
        async def primary():
            raise RuntimeError("fail")

        async def async_fallback(e):
            return "async_fallback"

        executor = FallbackExecutor(fallback=async_fallback)
        result = await executor.execute_async(primary)
        assert result.value == "async_fallback"
        assert result.from_fallback is True

    @pytest.mark.asyncio
    async def test_execute_async_with_sync_fallback(self):
        async def primary():
            raise RuntimeError("fail")

        executor = FallbackExecutor(fallback=lambda e: "sync_fallback")
        result = await executor.execute_async(primary)
        assert result.value == "sync_fallback"

    @pytest.mark.asyncio
    async def test_execute_async_both_fail(self):
        async def primary():
            raise RuntimeError("primary")

        async def bad_fallback(e):
            raise RuntimeError("fallback")

        executor = FallbackExecutor(fallback=bad_fallback)
        with pytest.raises(RuntimeError, match="fallback"):
            await executor.execute_async(primary)

    def test_get_metrics_includes_cache(self):
        cfg = FallbackConfig(enable_cache=True)
        executor = FallbackExecutor(fallback=lambda e: None, config=cfg)
        metrics = executor.get_metrics()
        assert "cache" in metrics


# ── with_fallback decorator ─────────────────────────────────────────

class TestWithFallbackDecorator:
    def test_passes_through_on_success(self):
        @with_fallback("default")
        def get_value():
            return "real"

        assert get_value() == "real"

    def test_returns_default_on_failure(self):
        @with_fallback("default")
        def get_value():
            raise RuntimeError("oops")

        assert get_value() == "default"

    def test_callable_fallback(self):
        @with_fallback(lambda e: f"caught: {e}")
        def get_value():
            raise ValueError("bad input")

        result = get_value()
        assert result == "caught: bad input"

    def test_no_log_fallbacks(self):
        @with_fallback("silent", log_fallbacks=False)
        def get_value():
            raise RuntimeError("fail")

        assert get_value() == "silent"

    def test_preserves_function_name(self):
        @with_fallback("default")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_passes_args_to_callable_fallback(self):
        @with_fallback(lambda e, x, y: x + y)
        def compute(x, y):
            raise RuntimeError("fail")

        result = compute(10, 20)
        assert result == 30


# ── with_fallback_chain decorator ───────────────────────────────────

class TestWithFallbackChainDecorator:
    def test_primary_success(self):
        @with_fallback_chain(lambda e: "fb1", lambda e: "fb2")
        def get_data():
            return "primary"

        assert get_data() == "primary"

    def test_first_fallback_used(self):
        @with_fallback_chain(lambda e: "fb1", lambda e: "fb2")
        def get_data():
            raise RuntimeError("fail")

        assert get_data() == "fb1"

    def test_second_fallback_when_first_fails(self):
        def failing_fb(e):
            raise RuntimeError("fb1 failed")

        @with_fallback_chain(failing_fb, lambda e: "fb2")
        def get_data():
            raise RuntimeError("primary failed")

        assert get_data() == "fb2"

    def test_all_fail_raises(self):
        def bad(e):
            raise RuntimeError("chain exhausted")

        @with_fallback_chain(bad)
        def get_data():
            raise RuntimeError("primary")

        with pytest.raises(RuntimeError, match="chain exhausted"):
            get_data()

    def test_exposes_fallback_chain_attribute(self):
        @with_fallback_chain(lambda e: None)
        def get_data():
            pass

        assert hasattr(get_data, "fallback_chain")
        assert isinstance(get_data.fallback_chain, ChainFallback)

    def test_named_chain(self):
        @with_fallback_chain(lambda e: None, name="named")
        def get_data():
            raise RuntimeError("fail")

        assert get_data.fallback_chain.name == "named"
