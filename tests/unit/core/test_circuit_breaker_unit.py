import asyncio

import pytest

from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerOpen,
                                      circuit_breaker, get_circuit_breaker)


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

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, circuit):
        """Test circuit breaker as context manager."""

        async def success_func():
            return "success"

        async with circuit:
            result = await success_func()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_get_state(self, circuit):
        """Test getting current circuit state."""
        state = circuit.get_state()
        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_metrics(self, circuit):
        """Test getting circuit breaker metrics."""

        async def success_func():
            return "success"

        await circuit.call(success_func)

        metrics = circuit.get_metrics()
        assert "state" in metrics
        assert "failure_count" in metrics
        assert "success_count" in metrics
        assert "last_failure_time" in metrics

    async def test_recovery_after_timeout(self):
        """Test circuit recovers after timeout."""
        config = CircuitBreakerConfig(
            fail_max=2, timeout_duration=1, success_threshold=1
        )
        circuit = CircuitBreaker("recovery_test", config)

        async def fail_func():
            raise ValueError("Test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            try:
                await circuit.call(fail_func)
            except ValueError:
                pass

        assert circuit.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Should succeed now
        result = await circuit.call(success_func)
        assert result == "success"
        assert circuit.state == CircuitState.CLOSED
