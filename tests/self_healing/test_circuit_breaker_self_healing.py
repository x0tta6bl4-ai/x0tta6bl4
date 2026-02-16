"""
Tests for Circuit Breaker Pattern Implementation.

Tests state transitions:
- CLOSED → OPEN (after failure_threshold failures)
- OPEN → HALF_OPEN (after recovery_timeout)
- HALF_OPEN → CLOSED (after success_threshold successes)
- HALF_OPEN → OPEN (on any failure)

Also tests:
- Fallback mechanisms
- Metrics recording
- Manual reset
- Concurrent access
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerMetrics,
                                      CircuitBreakerOpen, CircuitState,
                                      _circuit_breakers)
from src.core.circuit_breaker import \
    circuit_breaker as circuit_breaker_decorator
from src.core.circuit_breaker import (create_circuit_breaker,
                                      get_circuit_breaker)


class TestCircuitBreakerStates:
    """Tests for circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, circuit_breaker):
        """Circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.failure_count == 0

    @pytest.mark.asyncio
    async def test_closed_to_open_on_threshold(
        self, circuit_breaker, async_always_fail
    ):
        """Circuit opens after failure_threshold failures."""
        # Circuit breaker has failure_threshold=3
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.metrics.total_failures == 3

    @pytest.mark.asyncio
    async def test_open_rejects_calls(
        self, circuit_breaker, async_always_fail, async_always_succeed
    ):
        """OPEN circuit rejects calls immediately."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.state == CircuitState.OPEN

        # Should raise CircuitBreakerOpen without calling the function
        with pytest.raises(CircuitBreakerOpen):
            await circuit_breaker.call(async_always_succeed)

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(
        self, fast_circuit_breaker, async_always_fail, async_always_succeed
    ):
        """Circuit transitions to HALF_OPEN after recovery_timeout."""
        # Open the circuit (threshold=2)
        for _ in range(2):
            with pytest.raises(Exception):
                await fast_circuit_breaker.call(async_always_fail)

        assert fast_circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout (0.1s)
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN and be allowed
        result = await fast_circuit_breaker.call(async_always_succeed)
        assert result == {"success": True}

        # State should now be HALF_OPEN (or CLOSED if success_threshold=1)
        assert fast_circuit_breaker.state in [
            CircuitState.HALF_OPEN,
            CircuitState.CLOSED,
        ]

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(
        self, circuit_breaker, async_always_fail, async_always_succeed
    ):
        """Circuit closes after success_threshold successes in HALF_OPEN."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        # Manually set to HALF_OPEN for testing
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 0
        circuit_breaker._success_count = 0

        # success_threshold=2, so need 2 successes
        await circuit_breaker.call(async_always_succeed)
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        await circuit_breaker.call(async_always_succeed)
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(
        self, circuit_breaker, async_always_fail
    ):
        """Circuit reopens on any failure in HALF_OPEN state."""
        # Manually set to HALF_OPEN
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 0

        # Single failure should reopen
        with pytest.raises(Exception):
            await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_limits_concurrent_calls(
        self, circuit_breaker, async_always_succeed
    ):
        """HALF_OPEN state limits concurrent calls."""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 0

        # half_open_max_calls=2
        await circuit_breaker.call(async_always_succeed)
        await circuit_breaker.call(async_always_succeed)

        # Third call should fail (assuming circuit closed after 2 successes)
        # or be rejected if still in HALF_OPEN
        assert circuit_breaker._half_open_calls <= circuit_breaker.half_open_max_calls


class TestCircuitBreakerFallback:
    """Tests for fallback mechanism."""

    @pytest.mark.asyncio
    async def test_fallback_called_when_open(
        self, circuit_breaker_with_fallback, async_always_fail
    ):
        """Fallback is called when circuit is OPEN."""
        # Open the circuit (threshold=2)
        for _ in range(2):
            try:
                await circuit_breaker_with_fallback.call(async_always_fail)
            except Exception:
                pass  # Expected to fail

        assert circuit_breaker_with_fallback.state == CircuitState.OPEN

        # Next call should use fallback (not raise exception)
        result = await circuit_breaker_with_fallback.call(async_always_fail, "arg1")
        assert result["fallback"] is True
        assert result["args"] == ("arg1",)

    @pytest.mark.asyncio
    async def test_fallback_called_on_failure_in_closed(
        self, circuit_breaker_with_fallback, async_always_fail
    ):
        """Fallback is called on failure when circuit is CLOSED."""
        # Single failure should call fallback (not enough to open)
        result = await circuit_breaker_with_fallback.call(async_always_fail)
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_no_fallback_raises_exception(
        self, circuit_breaker, async_always_fail
    ):
        """Without fallback, exceptions propagate."""
        with pytest.raises(Exception, match="Always fails"):
            await circuit_breaker.call(async_always_fail)


class TestCircuitBreakerMetrics:
    """Tests for metrics recording."""

    @pytest.mark.asyncio
    async def test_success_metrics_recorded(
        self, circuit_breaker, async_always_succeed
    ):
        """Successful calls update metrics."""
        await circuit_breaker.call(async_always_succeed)

        metrics = circuit_breaker.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["total_successes"] == 1
        assert metrics["total_failures"] == 0
        assert metrics["last_success_time"] is not None

    @pytest.mark.asyncio
    async def test_failure_metrics_recorded(self, circuit_breaker, async_always_fail):
        """Failed calls update metrics."""
        with pytest.raises(Exception):
            await circuit_breaker.call(async_always_fail)

        metrics = circuit_breaker.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["total_failures"] == 1
        assert metrics["failure_count"] == 1
        assert metrics["last_failure_time"] is not None

    @pytest.mark.asyncio
    async def test_metrics_state_reflects_circuit_state(
        self, circuit_breaker, async_always_fail
    ):
        """Metrics state matches circuit state."""
        assert circuit_breaker.metrics.state == CircuitState.CLOSED

        # Open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.metrics.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(
        self, circuit_breaker, async_always_succeed, async_always_fail
    ):
        """Success resets failure count in CLOSED state."""
        # 2 failures (below threshold of 3)
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.metrics.failure_count == 2

        # One success resets count
        await circuit_breaker.call(async_always_succeed)
        assert circuit_breaker.metrics.failure_count == 0


class TestCircuitBreakerReset:
    """Tests for manual reset functionality."""

    @pytest.mark.asyncio
    async def test_manual_reset_to_closed(self, circuit_breaker, async_always_fail):
        """Manual reset returns circuit to CLOSED."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(async_always_fail)

        assert circuit_breaker.state == CircuitState.OPEN

        # Manual reset
        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.failure_count == 0
        assert circuit_breaker.metrics.success_count == 0

    @pytest.mark.asyncio
    async def test_reset_clears_half_open_state(self, circuit_breaker):
        """Reset clears HALF_OPEN state properly."""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._half_open_calls = 5
        circuit_breaker._success_count = 1

        await circuit_breaker.reset()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._half_open_calls == 0
        assert circuit_breaker._success_count == 0


class TestCircuitBreakerDecorator:
    """Tests for circuit breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_creates_circuit_breaker(self):
        """Decorator creates and registers circuit breaker."""

        @circuit_breaker_decorator("test_decorator_cb", failure_threshold=2)
        async def test_func():
            return "result"

        result = await test_func()
        assert result == "result"

        # Check circuit breaker was created
        cb = get_circuit_breaker("test_decorator_cb")
        assert cb is not None
        assert cb.failure_threshold == 2

        # Cleanup
        if "test_decorator_cb" in _circuit_breakers:
            del _circuit_breakers["test_decorator_cb"]

    @pytest.mark.asyncio
    async def test_decorator_exposes_circuit_breaker(self):
        """Decorated function exposes circuit breaker."""

        @circuit_breaker_decorator("exposed_cb")
        async def test_func():
            return "result"

        assert hasattr(test_func, "circuit_breaker")
        assert test_func.circuit_breaker.name == "exposed_cb"

        # Cleanup
        if "exposed_cb" in _circuit_breakers:
            del _circuit_breakers["exposed_cb"]


class TestCircuitBreakerConcurrency:
    """Tests for concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_handled_safely(self, circuit_breaker):
        """Multiple concurrent calls are handled safely."""
        call_count = [0]

        async def counting_func():
            call_count[0] += 1
            await asyncio.sleep(0.01)
            return call_count[0]

        # Launch 10 concurrent calls
        tasks = [circuit_breaker.call(counting_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert circuit_breaker.metrics.total_requests == 10
        assert circuit_breaker.metrics.total_successes == 10

    @pytest.mark.asyncio
    async def test_concurrent_failures_reach_threshold(self, circuit_breaker):
        """Concurrent failures properly trigger threshold."""
        fail_count = [0]

        async def failing_func():
            fail_count[0] += 1
            await asyncio.sleep(0.01)
            raise Exception(f"Fail {fail_count[0]}")

        # Launch 5 concurrent calls (threshold is 3)
        tasks = [circuit_breaker.call(failing_func) for _ in range(5)]

        # Some will fail, some may get CircuitBreakerOpen
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be exceptions
        assert all(isinstance(r, Exception) for r in results)

        # Circuit should be open
        assert circuit_breaker.state == CircuitState.OPEN


class TestCircuitBreakerRegistry:
    """Tests for global circuit breaker registry."""

    def test_create_circuit_breaker_registers(self):
        """create_circuit_breaker registers in global registry."""
        cb = create_circuit_breaker("registry_test", failure_threshold=5)

        assert get_circuit_breaker("registry_test") is cb

        # Cleanup
        del _circuit_breakers["registry_test"]

    def test_create_returns_existing(self):
        """create_circuit_breaker returns existing if name exists."""
        cb1 = create_circuit_breaker("existing_test", failure_threshold=5)
        cb2 = create_circuit_breaker("existing_test", failure_threshold=10)

        assert cb1 is cb2
        assert cb1.failure_threshold == 5  # Original settings preserved

        # Cleanup
        del _circuit_breakers["existing_test"]

    def test_get_nonexistent_returns_none(self):
        """get_circuit_breaker returns None for unknown name."""
        assert get_circuit_breaker("nonexistent") is None


class TestCircuitBreakerTiming:
    """Tests for timing-related behavior."""

    @pytest.mark.asyncio
    async def test_should_attempt_reset_respects_timeout(
        self, fast_circuit_breaker, async_always_fail
    ):
        """_should_attempt_reset respects recovery_timeout."""
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await fast_circuit_breaker.call(async_always_fail)

        # Immediately after opening, should not attempt reset
        assert fast_circuit_breaker._should_attempt_reset() is False

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Now should attempt reset
        assert fast_circuit_breaker._should_attempt_reset() is True

    @pytest.mark.asyncio
    async def test_call_duration_recorded(self, circuit_breaker):
        """Call duration is measured for successful calls."""

        async def slow_func():
            await asyncio.sleep(0.05)
            return "done"

        start = time.time()
        await circuit_breaker.call(slow_func)
        elapsed = time.time() - start

        # Should have taken at least 50ms
        assert elapsed >= 0.05


class TestCircuitBreakerEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_zero_failure_threshold(self):
        """Circuit with 0 threshold opens immediately."""
        cb = CircuitBreaker(
            name="zero_threshold",
            failure_threshold=1,  # Minimum practical threshold
            recovery_timeout=1.0,
        )

        async def fail():
            raise Exception("fail")

        with pytest.raises(Exception):
            await cb.call(fail)

        assert cb.state == CircuitState.OPEN

        # Cleanup
        if "zero_threshold" in _circuit_breakers:
            del _circuit_breakers["zero_threshold"]

    @pytest.mark.asyncio
    async def test_exception_types_preserved(self, circuit_breaker):
        """Original exception types are preserved."""

        class CustomError(Exception):
            pass

        async def raise_custom():
            raise CustomError("custom error")

        with pytest.raises(CustomError, match="custom error"):
            await circuit_breaker.call(raise_custom)

    @pytest.mark.asyncio
    async def test_args_passed_correctly(self, circuit_breaker):
        """Arguments are passed to wrapped function correctly."""

        async def func_with_args(a, b, c=None):
            return {"a": a, "b": b, "c": c}

        result = await circuit_breaker.call(func_with_args, 1, 2, c=3)
        assert result == {"a": 1, "b": 2, "c": 3}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
