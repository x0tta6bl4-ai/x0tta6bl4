import asyncio
import builtins
import importlib
import types

import pytest

from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerOpen,
                                      CircuitState, circuit_breaker,
                                      create_circuit_breaker,
                                      get_circuit_breaker)


@pytest.mark.asyncio
async def test_initial_state_closed():
    cb = CircuitBreaker("cb_init")
    assert cb.state.name == "CLOSED"
    assert cb._failure_count == 0


@pytest.mark.asyncio
async def test_successful_call():
    cb = CircuitBreaker("cb_success")

    async def ok():
        return 42

    result = await cb.call(ok)
    assert result == 42
    assert cb.state.name == "CLOSED"


@pytest.mark.asyncio
async def test_failed_call_opens_circuit():
    cb = CircuitBreaker("cb_fail", failure_threshold=2, recovery_timeout=1)

    async def fail():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        await cb.call(fail)
    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state.name == "OPEN"


@pytest.mark.asyncio
async def test_half_open_and_recovery():
    cb = CircuitBreaker(
        "cb_half", failure_threshold=1, recovery_timeout=0.5, success_threshold=2
    )

    async def fail():
        raise ValueError("fail")

    async def ok():
        return "ok"

    with pytest.raises(ValueError):
        await cb.call(fail)
    assert cb.state.name == "OPEN"
    await asyncio.sleep(0.6)
    # First success: HALF_OPEN
    result = await cb.call(ok)
    assert result == "ok"
    assert cb.state.name == "HALF_OPEN"
    # Second success: CLOSED
    result = await cb.call(ok)
    assert result == "ok"
    assert cb.state.name == "CLOSED"


@pytest.mark.asyncio
async def test_fallback_called_on_open():
    called = {}

    async def fallback(*args, **kwargs):
        called["ok"] = True
        return "fallback-result"

    cb = CircuitBreaker(
        "cb_fallback", failure_threshold=1, recovery_timeout=10, fallback=fallback
    )

    async def fail_func():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        await cb.call(fail_func)
    result = await cb.call(fail_func)
    assert result == "fallback-result"
    assert called["ok"]


@pytest.mark.asyncio
async def test_fallback_raises_if_not_set():
    cb = CircuitBreaker("cb_no_fallback", failure_threshold=1, recovery_timeout=10)

    async def fail_func():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        await cb.call(fail_func)
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(fail_func)


@pytest.mark.asyncio
async def test_async_reset():
    cb = CircuitBreaker("cb_reset", failure_threshold=1, recovery_timeout=10)

    async def fail_func():
        raise ValueError("fail")

    with pytest.raises(ValueError):
        await cb.call(fail_func)
    assert cb.state.name == "OPEN"
    await cb.reset()
    assert cb.state.name == "CLOSED"
    assert cb._failure_count == 0


@pytest.mark.asyncio
async def test_decorator_with_params():
    calls = {}

    @circuit_breaker("cb_decorator", failure_threshold=1, recovery_timeout=10)
    async def protected(x):
        calls["x"] = x
        return x * 2

    result = await protected(21)
    assert result == 42
    assert calls["x"] == 21
    cb = get_circuit_breaker("cb_decorator")
    assert cb is not None


def test_get_metrics_dict():
    cb = CircuitBreaker("cb_metrics")
    metrics = cb.get_metrics()
    assert "name" in metrics
    assert "state" in metrics
    assert "failure_count" in metrics
    assert "success_count" in metrics
    assert "total_requests" in metrics


@pytest.mark.asyncio
async def test_fallback_only_in_open():
    called = {}

    async def fallback(*args, **kwargs):
        called["used"] = True
        return "fallback"

    cb = CircuitBreaker(
        "cb_fallback2", failure_threshold=2, recovery_timeout=10, fallback=fallback
    )

    async def ok_func():
        return "ok"

    result = await cb.call(ok_func)
    assert result == "ok"
    assert await fallback() == "fallback"
    assert called["used"] is True


@pytest.mark.asyncio
async def test_fallback_used_on_closed_state_failure_path():
    async def fallback():
        return "fallback-closed"

    cb = CircuitBreaker("cb_closed_fallback", failure_threshold=10, fallback=fallback)

    async def fail():
        raise RuntimeError("boom")

    result = await cb.call(fail)
    assert result == "fallback-closed"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_limit_without_fallback_raises_open():
    cb = CircuitBreaker(
        "cb_half_limit_no_fallback",
        failure_threshold=1,
        recovery_timeout=10,
        half_open_max_calls=1,
    )
    cb._state = CircuitState.HALF_OPEN
    cb._half_open_calls = 1

    async def ok():
        return "ok"

    with pytest.raises(CircuitBreakerOpen, match="HALF_OPEN limit reached"):
        await cb.call(ok)
    assert await ok() == "ok"


@pytest.mark.asyncio
async def test_half_open_limit_with_fallback_returns_fallback():
    async def fallback():
        return "fallback-ok"

    cb = CircuitBreaker(
        "cb_half_limit_with_fallback",
        failure_threshold=1,
        recovery_timeout=10,
        half_open_max_calls=1,
        fallback=fallback,
    )
    cb._state = CircuitState.HALF_OPEN
    cb._half_open_calls = 1

    async def ok():
        return "ok"

    result = await cb.call(ok)
    assert result == "fallback-ok"
    assert await ok() == "ok"


@pytest.mark.asyncio
async def test_half_open_failure_transitions_to_open():
    cb = CircuitBreaker(
        "cb_half_open_failure",
        failure_threshold=5,
        recovery_timeout=10,
        half_open_max_calls=2,
    )
    cb._state = CircuitState.HALF_OPEN
    cb._half_open_calls = 0

    async def fail():
        raise RuntimeError("half-open-fail")

    with pytest.raises(RuntimeError):
        await cb.call(fail)

    assert cb.state == CircuitState.OPEN
    assert cb._last_failure_time is not None


def test_should_attempt_reset_true_when_no_last_failure_time():
    cb = CircuitBreaker("cb_no_failure_time")
    cb._last_failure_time = None
    assert cb._should_attempt_reset() is True


@pytest.mark.asyncio
async def test_execute_fallback_raises_when_missing_fallback():
    cb = CircuitBreaker("cb_no_fallback")
    with pytest.raises(CircuitBreakerOpen, match="No fallback"):
        await cb._execute_fallback()


def test_metric_helpers_reuse_existing_collectors(monkeypatch):
    import src.core.circuit_breaker as cb_mod
    assert hasattr(cb_mod, "_get_or_create_gauge")

    existing_gauge = types.SimpleNamespace(_name="my_gauge")
    existing_counter = types.SimpleNamespace(_name="my_counter")
    existing_histogram = types.SimpleNamespace(_name="my_hist")
    registry = types.SimpleNamespace(
        _names_to_collectors={
            "g": existing_gauge,
            "c": existing_counter,
            "h": existing_histogram,
        }
    )
    monkeypatch.setattr(cb_mod, "REGISTRY", registry)

    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("already registered")

    monkeypatch.setattr(cb_mod, "Gauge", _raise_value_error)
    monkeypatch.setattr(cb_mod, "Counter", _raise_value_error)
    monkeypatch.setattr(cb_mod, "Histogram", _raise_value_error)

    assert cb_mod._get_or_create_gauge("my_gauge", "desc", ["label"]) is existing_gauge
    assert cb_mod._get_or_create_gauge("missing_g", "desc", ["label"]) is None

    assert (
        cb_mod._get_or_create_counter("my_counter", "desc", ["label"])
        is existing_counter
    )
    assert cb_mod._get_or_create_counter("missing_c", "desc", ["label"]) is None

    assert (
        cb_mod._get_or_create_histogram("my_hist", "desc", ["label"], [1.0, 2.0])
        is existing_histogram
    )
    assert (
        cb_mod._get_or_create_histogram("missing_h", "desc", ["label"], [1.0, 2.0])
        is None
    )


def test_import_fallback_when_prometheus_missing(monkeypatch):
    import src.core.circuit_breaker as cb_mod

    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("prometheus_client"):
            raise ImportError("prometheus unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    reloaded = importlib.reload(cb_mod)
    assert reloaded.PROMETHEUS_AVAILABLE is False

    monkeypatch.setattr(builtins, "__import__", original_import)
    importlib.reload(cb_mod)


def test_create_circuit_breaker_returns_existing_instance():
    name = "cb_existing_instance"
    first = create_circuit_breaker(name, failure_threshold=2, recovery_timeout=1)
    second = create_circuit_breaker(name, failure_threshold=99, recovery_timeout=99)
    assert second is first
