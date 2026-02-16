import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from libx0t.core.circuit_breaker import (
    CircuitBreaker, CircuitState, CircuitBreakerOpen, circuit_breaker, create_circuit_breaker, _circuit_breakers
)

class TestCircuitBreaker:
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        _circuit_breakers.clear()
        yield
        _circuit_breakers.clear()

    @pytest.mark.asyncio
    async def test_normal_operation(self):
        cb = CircuitBreaker("test-cb", failure_threshold=2)
        
        async def success():
            return "ok"
            
        assert await cb.call(success) == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.success_count == 1
        assert cb.metrics.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_threshold(self):
        cb = CircuitBreaker("test-fail", failure_threshold=2)
        
        async def fail():
            raise ValueError("boom")
            
        # Fail 1
        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitState.CLOSED # threshold 2
        
        # Fail 2
        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN # threshold reached

    @pytest.mark.asyncio
    async def test_open_circuit_rejection(self):
        cb = CircuitBreaker("test-open", failure_threshold=1)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.time() # Just happened
        
        async def any_func():
            return "ok"
            
        with pytest.raises(CircuitBreakerOpen):
            await cb.call(any_func)

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        cb = CircuitBreaker("test-recover", failure_threshold=1, recovery_timeout=0.1, success_threshold=2)
        
        # Force open
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.time() - 0.2 # Expired
        
        async def success():
            return "ok"
            
        # First call triggers half-open
        assert await cb.call(success) == "ok"
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.metrics.success_count == 1
        
        # Second call closes circuit
        assert await cb.call(success) == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.success_count == 0 # Reset after close

    @pytest.mark.asyncio
    async def test_half_open_failure(self):
        cb = CircuitBreaker("test-half-fail", failure_threshold=1, recovery_timeout=0.1)
        
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = time.time() - 0.2
        
        async def fail():
            raise ValueError("boom")
            
        with pytest.raises(ValueError):
            await cb.call(fail)
            
        assert cb.state == CircuitState.OPEN # Back to open

    @pytest.mark.asyncio
    async def test_fallback(self):
        fallback = AsyncMock(return_value="fallback")
        cb = CircuitBreaker("test-fallback", failure_threshold=1, fallback=fallback)
        
        async def fail():
            raise ValueError("boom")
            
        # Fail -> Open
        with pytest.raises(ValueError): # First failure opens it
            await cb.call(fail)
            
        # Next call uses fallback
        assert await cb.call(fail) == "fallback"
        fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator(self):
        @circuit_breaker("decorated-cb", failure_threshold=1)
        async def target(x):
            if x == "fail":
                raise ValueError("boom")
            return x
            
        assert await target("ok") == "ok"
        
        with pytest.raises(ValueError):
            await target("fail")
            
        # Circuit open now
        with pytest.raises(CircuitBreakerOpen):
            await target("ok")

    def test_create_and_get(self):
        cb1 = create_circuit_breaker("shared", failure_threshold=3)
        cb2 = create_circuit_breaker("shared", failure_threshold=5) # properties ignored if exists
        
        assert cb1 is cb2
        assert cb1.failure_threshold == 3
