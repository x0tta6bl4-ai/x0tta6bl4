import pytest
from src.resilience.advanced_patterns import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryStrategy,
    BulkheadIsolation,
    FallbackHandler,
    ResilientExecutor,
)


class TestCircuitBreaker:
    def test_circuit_closed_by_default(self):
        breaker = CircuitBreaker(CircuitBreakerConfig())
        assert breaker.get_state() == CircuitState.CLOSED.value
    
    def test_circuit_opens_on_failures(self):
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config)
        
        def failing_func():
            raise Exception("failure")
        
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(failing_func)
        
        assert breaker.get_state() == CircuitState.OPEN.value
    
    def test_circuit_rejects_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)
        
        with pytest.raises(Exception):
            breaker.call(lambda: 1/0)
        
        with pytest.raises(Exception):
            breaker.call(lambda: "ok")


class TestRetryStrategy:
    def test_successful_on_first_try(self):
        strategy = RetryStrategy()
        result = strategy.execute(lambda: "success")
        assert result == "success"
    
    def test_retry_on_failure(self):
        call_count = 0
        
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"
        
        strategy = RetryStrategy()
        result = strategy.execute(flaky_func)
        assert result == "success"
        assert call_count == 3


class TestBulkheadIsolation:
    def test_allow_within_limit(self):
        bulkhead = BulkheadIsolation(max_concurrent=2)
        result = bulkhead.execute(lambda: "success")
        assert result == "success"


class TestFallbackHandler:
    def test_primary_succeeds(self):
        handler = FallbackHandler()
        result = handler.execute_with_fallback(
            "key", 
            lambda: "primary"
        )
        assert result == "primary"
    
    def test_fallback_on_failure(self):
        handler = FallbackHandler()
        handler.register_fallback("key", lambda: "fallback")
        
        result = handler.execute_with_fallback(
            "key",
            lambda: 1/0
        )
        assert result == "fallback"


class TestResilientExecutor:
    def test_successful_execution(self):
        executor = ResilientExecutor()
        result = executor.execute(lambda: "success")
        assert result == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
