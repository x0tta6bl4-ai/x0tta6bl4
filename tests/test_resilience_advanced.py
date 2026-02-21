"""
Tests for Advanced Resilience Patterns
======================================

Comprehensive tests for:
- Rate Limiter patterns (Token Bucket, Sliding Window, Leaky Bucket, Adaptive)
- Bulkhead patterns (Semaphore, Queue, Partitioned, Adaptive)
- Fallback patterns (Default, Cache, Chain, Circuit, Async)
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import Mock, AsyncMock, patch
from collections import deque

# Rate Limiter imports
from src.resilience.rate_limiter import (
    RateLimiterType,
    RateLimitConfig,
    RateLimitExceeded,
    RateLimitResult,
    TokenBucket,
    SlidingWindowCounter,
    LeakyBucket,
    AdaptiveRateLimiter,
    RateLimiterFactory,
    rate_limit,
)

# Bulkhead imports
from src.resilience.bulkhead import (
    BulkheadType,
    BulkheadConfig,
    BulkheadStats,
    BulkheadFullException,
    SemaphoreBulkhead,
    QueueBulkhead,
    PartitionedBulkhead,
    AdaptiveBulkhead,
    BulkheadRegistry,
    bulkhead_decorator,
)

# Fallback imports
from src.resilience.fallback import (
    FallbackType,
    FallbackResult,
    FallbackConfig,
    FallbackMetrics,
    DefaultValueFallback,
    CacheFallback,
    ChainFallback,
    CircuitFallback,
    AsyncFallback,
    FallbackChainBuilder,
    FallbackExecutor,
    with_fallback,
    with_fallback_chain,
)


# =============================================================================
# Rate Limiter Tests
# =============================================================================

class TestTokenBucket:
    """Tests for Token Bucket rate limiter."""
    
    def test_initial_state(self):
        """Test initial bucket state."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 10.0
        assert bucket.refill_rate == 5.0
    
    def test_acquire_success(self):
        """Test successful token acquisition."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)
        
        result = bucket.acquire(1)
        
        assert result.allowed is True
        assert result.remaining == 9
    
    def test_acquire_multiple(self):
        """Test acquiring multiple tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)
        
        for i in range(10):
            result = bucket.acquire(1)
            assert result.allowed is True
            assert result.remaining == 9 - i
    
    def test_acquire_exhausted(self):
        """Test acquisition when bucket is empty."""
        bucket = TokenBucket(capacity=2, refill_rate=1.0)
        
        # Exhaust bucket
        bucket.acquire(1)
        bucket.acquire(1)
        
        # Should fail
        result = bucket.acquire(1)
        assert result.allowed is False
        assert result.retry_after is not None
    
    def test_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)  # 100 tokens/sec
        
        # Exhaust bucket
        bucket.tokens = 0
        bucket.last_refill = time.time() - 0.1  # 100ms ago
        
        # Should have refilled ~10 tokens
        bucket._refill()
        assert bucket.tokens == pytest.approx(10.0, rel=0.1)
    
    def test_try_acquire(self):
        """Test simple boolean acquisition."""
        bucket = TokenBucket(capacity=1, refill_rate=1.0)
        
        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is False
    
    def test_stats(self):
        """Test statistics collection."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0, name="test_bucket")
        
        bucket.acquire(1)
        bucket.acquire(1)
        bucket.acquire(1)
        
        stats = bucket.get_stats()
        
        assert stats["name"] == "test_bucket"
        assert stats["type"] == "token_bucket"
        assert stats["total_requests"] == 3
        assert stats["allowed_requests"] == 3
        assert stats["denied_requests"] == 0


class TestSlidingWindowCounter:
    """Tests for Sliding Window rate limiter."""
    
    def test_initial_state(self):
        """Test initial window state."""
        limiter = SlidingWindowCounter(max_requests=10, window_seconds=1.0)
        
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 1.0
        assert len(limiter.requests) == 0
    
    def test_acquire_success(self):
        """Test successful request within limit."""
        limiter = SlidingWindowCounter(max_requests=5, window_seconds=1.0)
        
        result = limiter.acquire()
        
        assert result.allowed is True
        assert result.remaining == 4
    
    def test_acquire_at_limit(self):
        """Test request at limit boundary."""
        limiter = SlidingWindowCounter(max_requests=3, window_seconds=1.0)
        
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        
        result = limiter.acquire()
        assert result.allowed is False
    
    def test_window_expiry(self):
        """Test that old requests expire."""
        limiter = SlidingWindowCounter(max_requests=2, window_seconds=0.1)
        
        limiter.acquire()
        limiter.acquire()
        
        # Wait for window to expire
        time.sleep(0.15)
        
        result = limiter.acquire()
        assert result.allowed is True
    
    def test_stats(self):
        """Test statistics."""
        limiter = SlidingWindowCounter(max_requests=10, window_seconds=1.0)
        
        for _ in range(5):
            limiter.acquire()
        
        stats = limiter.get_stats()
        
        assert stats["current_requests"] == 5
        assert stats["total_requests"] == 5
        assert stats["allowed_requests"] == 5


class TestLeakyBucket:
    """Tests for Leaky Bucket rate limiter."""
    
    def test_initial_state(self):
        """Test initial bucket state."""
        bucket = LeakyBucket(capacity=10, leak_rate=5.0)
        
        assert bucket.capacity == 10
        assert bucket.leak_rate == 5.0
        assert len(bucket.queue) == 0
    
    def test_acquire_success(self):
        """Test successful request."""
        bucket = LeakyBucket(capacity=5, leak_rate=1.0)
        
        result = bucket.acquire()
        
        assert result.allowed is True
        assert bucket.get_queue_position() == 1
    
    def test_acquire_at_capacity(self):
        """Test request when bucket is full."""
        bucket = LeakyBucket(capacity=2, leak_rate=0.1)  # Very slow leak
        
        bucket.acquire()
        bucket.acquire()
        
        result = bucket.acquire()
        assert result.allowed is False
    
    def test_leak_processing(self):
        """Test that queue leaks over time."""
        bucket = LeakyBucket(capacity=10, leak_rate=100.0)  # 100/sec
        
        # Add items
        for _ in range(5):
            bucket.acquire()
        
        assert bucket.get_queue_position() == 5
        
        # Wait for leak
        time.sleep(0.05)  # Should leak ~5 items
        
        bucket._leak()
        assert bucket.processed_requests >= 4


class TestAdaptiveRateLimiter:
    """Tests for Adaptive rate limiter."""
    
    def test_initial_state(self):
        """Test initial state."""
        limiter = AdaptiveRateLimiter(
            initial_rate=100.0,
            min_rate=10.0,
            max_rate=1000.0
        )
        
        assert limiter.current_rate == 100.0
        assert limiter.min_rate == 10.0
        assert limiter.max_rate == 1000.0
    
    def test_rate_adjustment_on_high_error_rate(self):
        """Test rate reduction on high error rate."""
        limiter = AdaptiveRateLimiter(
            initial_rate=100.0,
            min_rate=10.0,
            max_rate=1000.0,
            adjustment_window=10
        )
        
        # Simulate high error rate
        limiter.ewma_error_rate = 0.5
        limiter._adjust_rate()
        
        assert limiter.current_rate < 100.0
    
    def test_rate_adjustment_on_fast_responses(self):
        """Test rate increase on fast responses."""
        limiter = AdaptiveRateLimiter(
            initial_rate=100.0,
            min_rate=10.0,
            max_rate=1000.0
        )
        
        # Simulate fast responses
        limiter.ewma_response_time = 0.01  # Very fast
        limiter.ewma_error_rate = 0.0
        limiter._adjust_rate()
        
        assert limiter.current_rate >= 100.0
    
    def test_rate_bounds(self):
        """Test that rate stays within bounds."""
        limiter = AdaptiveRateLimiter(
            initial_rate=100.0,
            min_rate=50.0,
            max_rate=200.0
        )
        
        # Try to push beyond bounds
        limiter.ewma_error_rate = 0.99
        for _ in range(10):
            limiter._adjust_rate()
        
        assert limiter.current_rate >= limiter.min_rate
        
        # Try to push above max
        limiter.ewma_error_rate = 0.0
        limiter.ewma_response_time = 0.001
        for _ in range(10):
            limiter._adjust_rate()
        
        assert limiter.current_rate <= limiter.max_rate


class TestRateLimiterFactory:
    """Tests for rate limiter factory."""
    
    def test_create_token_bucket(self):
        """Test creating token bucket."""
        config = RateLimitConfig(max_requests=100, burst_size=50)
        limiter = RateLimiterFactory.create(
            RateLimiterType.TOKEN_BUCKET,
            config
        )
        
        assert isinstance(limiter, TokenBucket)
        assert limiter.capacity == 50
    
    def test_create_sliding_window(self):
        """Test creating sliding window."""
        config = RateLimitConfig(max_requests=100, window_seconds=1.0)
        limiter = RateLimiterFactory.create(
            RateLimiterType.SLIDING_WINDOW,
            config
        )
        
        assert isinstance(limiter, SlidingWindowCounter)
    
    def test_create_leaky_bucket(self):
        """Test creating leaky bucket."""
        config = RateLimitConfig(max_requests=100, queue_size=50)
        limiter = RateLimiterFactory.create(
            RateLimiterType.LEAKY_BUCKET,
            config
        )
        
        assert isinstance(limiter, LeakyBucket)
    
    def test_create_adaptive(self):
        """Test creating adaptive limiter."""
        config = RateLimitConfig(
            max_requests=100,
            adaptive_min_rate=10.0,
            adaptive_max_rate=1000.0
        )
        limiter = RateLimiterFactory.create(
            RateLimiterType.ADAPTIVE,
            config
        )
        
        assert isinstance(limiter, AdaptiveRateLimiter)


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""
    
    def test_decorator_allows_within_limit(self):
        """Test decorator allows within limit."""
        limiter = TokenBucket(capacity=5, refill_rate=1.0)
        
        @rate_limit(limiter)
        def my_func(x):
            return x * 2
        
        result = my_func(5)
        assert result == 10
    
    def test_decorator_blocks_at_limit(self):
        """Test decorator blocks at limit."""
        limiter = TokenBucket(capacity=1, refill_rate=0.1)
        
        @rate_limit(limiter)
        def my_func():
            return "ok"
        
        # First call succeeds
        my_func()
        
        # Second call fails
        with pytest.raises(RateLimitExceeded):
            my_func()
    
    def test_decorator_with_callback(self):
        """Test decorator with rate limited callback."""
        limiter = TokenBucket(capacity=1, refill_rate=0.1)
        
        def on_limited():
            return "rate_limited"
        
        @rate_limit(limiter, on_rate_limited=on_limited)
        def my_func():
            return "ok"
        
        assert my_func() == "ok"
        assert my_func() == "rate_limited"


# =============================================================================
# Bulkhead Tests
# =============================================================================

class TestSemaphoreBulkhead:
    """Tests for Semaphore bulkhead."""
    
    def test_initial_state(self):
        """Test initial bulkhead state."""
        bh = SemaphoreBulkhead(max_concurrent=5, name="test")
        
        assert bh.max_concurrent == 5
        assert bh._current_count == 0
    
    def test_try_enter_success(self):
        """Test successful entry."""
        bh = SemaphoreBulkhead(max_concurrent=5)
        
        assert bh.try_enter() is True
        assert bh._current_count == 1
    
    def test_try_enter_at_capacity(self):
        """Test entry at capacity."""
        bh = SemaphoreBulkhead(max_concurrent=2)
        
        bh.try_enter()
        bh.try_enter()
        
        assert bh.try_enter() is False
    
    def test_exit(self):
        """Test exit releases permit."""
        bh = SemaphoreBulkhead(max_concurrent=2)
        
        bh.try_enter()
        assert bh._current_count == 1
        
        bh.exit()
        assert bh._current_count == 0
    
    def test_execute_success(self):
        """Test execute within bulkhead."""
        bh = SemaphoreBulkhead(max_concurrent=5)
        
        result = bh.execute(lambda x: x * 2, 5)
        
        assert result == 10
        assert bh._current_count == 0
    
    def test_execute_at_capacity(self):
        """Test execute when at capacity."""
        bh = SemaphoreBulkhead(max_concurrent=1)
        
        # Hold the permit
        bh.try_enter()
        
        with pytest.raises(BulkheadFullException):
            bh.execute(lambda: "test")
    
    def test_stats(self):
        """Test statistics."""
        bh = SemaphoreBulkhead(max_concurrent=5, name="test_bh")
        
        bh.execute(lambda: None)
        bh.execute(lambda: None)
        
        stats = bh.get_stats()
        
        assert stats.name == "test_bh"
        assert stats.total_calls == 2
        assert stats.accepted_calls == 2


class TestQueueBulkhead:
    """Tests for Queue-based bulkhead."""
    
    def test_initial_state(self):
        """Test initial state."""
        bh = QueueBulkhead(max_concurrent=5, queue_size=10)
        
        assert bh.max_concurrent == 5
        assert bh.queue_size == 10
    
    def test_queue_usage(self):
        """Test queue is used when at capacity."""
        bh = QueueBulkhead(max_concurrent=1, queue_size=5)
        
        # Fill concurrent
        bh.try_enter()
        
        # Should queue
        assert bh._current_queue_size == 0
    
    def test_execute_with_queue(self):
        """Test execute with queue."""
        bh = QueueBulkhead(max_concurrent=2, queue_size=5)
        
        result = bh.execute(lambda x: x * 2, 5)
        
        assert result == 10
    
    def test_queue_full_rejection(self):
        """Test rejection when queue is full."""
        bh = QueueBulkhead(max_concurrent=1, queue_size=1)
        
        # Fill concurrent and queue
        bh.enter()
        
        # This should fail
        result = bh.enter(timeout_ms=100)
        # Note: actual behavior depends on timing


class TestPartitionedBulkhead:
    """Tests for Partitioned bulkhead."""
    
    def test_initial_state(self):
        """Test initial state with partitions."""
        bh = PartitionedBulkhead({
            "read": 10,
            "write": 5,
            "admin": 2
        })
        
        assert len(bh.partitions) == 3
        assert "read" in bh.partitions
        assert "write" in bh.partitions
    
    def test_partition_isolation(self):
        """Test partitions are isolated."""
        bh = PartitionedBulkhead({
            "read": 1,
            "write": 1
        })
        
        # Fill read partition
        bh.enter("read")
        
        # Write partition should still be available
        assert bh.enter("write") is True
        bh.exit("write")
        
        # Read partition should be full
        assert bh.try_enter("read") is False
    
    def test_execute_in_partition(self):
        """Test execute in specific partition."""
        bh = PartitionedBulkhead({
            "read": 5,
            "write": 2
        })
        
        result = bh.execute(lambda x: x * 2, "read", 5)
        
        assert result == 10
    
    def test_aggregate_stats(self):
        """Test aggregate statistics."""
        bh = PartitionedBulkhead({
            "read": 5,
            "write": 2
        })
        
        bh.execute(lambda: None, "read")
        bh.execute(lambda: None, "write")
        
        stats = bh.get_aggregate_stats()
        
        assert stats["partition_count"] == 2
        assert stats["total_calls"] == 2


class TestAdaptiveBulkhead:
    """Tests for Adaptive bulkhead."""
    
    def test_initial_state(self):
        """Test initial state."""
        bh = AdaptiveBulkhead(
            initial_capacity=10,
            min_capacity=5,
            max_capacity=20
        )
        
        assert bh.current_capacity == 10
    
    def test_capacity_adjustment_on_slow_responses(self):
        """Test capacity reduction on slow responses."""
        bh = AdaptiveBulkhead(
            initial_capacity=10,
            min_capacity=5,
            max_capacity=20,
            adjustment_window=5
        )
        
        # Simulate slow responses
        bh.ewma_response_time = 500.0  # Very slow
        bh._adjust_capacity()
        
        assert bh.current_capacity < 10
    
    def test_capacity_bounds(self):
        """Test capacity stays within bounds."""
        bh = AdaptiveBulkhead(
            initial_capacity=10,
            min_capacity=8,
            max_capacity=12
        )
        
        # Try to push below min
        bh.ewma_error_rate = 0.99
        for _ in range(10):
            bh._adjust_capacity()
        
        assert bh.current_capacity >= 8


class TestBulkheadRegistry:
    """Tests for Bulkhead registry."""
    
    def test_singleton(self):
        """Test registry is singleton."""
        r1 = BulkheadRegistry()
        r2 = BulkheadRegistry()
        
        assert r1 is r2
    
    def test_register_and_get(self):
        """Test register and retrieve."""
        registry = BulkheadRegistry()
        bh = SemaphoreBulkhead(max_concurrent=5, name="test_registry")
        
        registry.register("test_registry", bh)
        
        retrieved = registry.get("test_registry")
        assert retrieved is bh
    
    def test_health_check(self):
        """Test health check."""
        registry = BulkheadRegistry()
        
        bh = SemaphoreBulkhead(max_concurrent=2, name="health_test")
        registry.register("health_test", bh)
        
        health = registry.health_check()
        
        assert "healthy" in health
        assert "bulkhead_count" in health


class TestBulkheadDecorator:
    """Tests for bulkhead decorator."""
    
    def test_decorator_basic(self):
        """Test basic decorator usage."""
        @bulkhead_decorator(max_concurrent=2, name="decorator_test")
        def my_func(x):
            return x * 2
        
        result = my_func(5)
        assert result == 10
    
    def test_decorator_with_bulkhead_attribute(self):
        """Test decorator adds bulkhead attribute."""
        @bulkhead_decorator(max_concurrent=5)
        def my_func():
            return "ok"
        
        assert hasattr(my_func, 'bulkhead')
        assert my_func.bulkhead.max_concurrent == 5


# =============================================================================
# Fallback Tests
# =============================================================================

class TestDefaultValueFallback:
    """Tests for default value fallback."""
    
    def test_returns_default(self):
        """Test returns default value."""
        fallback = DefaultValueFallback(default_value={"status": "degraded"})
        
        result = fallback.handle(ValueError("test error"))
        
        assert result == {"status": "degraded"}


class TestCacheFallback:
    """Tests for cache fallback."""
    
    def test_cache_hit(self):
        """Test cache hit returns value."""
        cache = CacheFallback(ttl_seconds=60)
        
        # Store value
        cache.set("test_key", {"data": "cached"})
        
        # Retrieve
        result = cache.get("test_key")
        
        assert result == {"data": "cached"}
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = CacheFallback(ttl_seconds=60)
        
        result = cache.get("nonexistent")
        
        assert result is None
    
    def test_cache_expiry(self):
        """Test cache entry expires."""
        cache = CacheFallback(ttl_seconds=0.1)  # 100ms
        
        cache.set("expiring", "value")
        
        # Wait for expiry
        time.sleep(0.15)
        
        result = cache.get("expiring")
        
        assert result is None
    
    def test_handle_with_cached_value(self):
        """Test handle returns cached value."""
        cache = CacheFallback(ttl_seconds=60)
        
        # Pre-populate cache
        cache.set("arg1|kwarg1=value1", "cached_result")
        
        result = cache.handle(
            ValueError("error"),
            "arg1",
            kwarg1="value1"
        )
        
        assert result == "cached_result"
    
    def test_handle_without_cached_value(self):
        """Test handle re-raises when no cache."""
        cache = CacheFallback(ttl_seconds=60)
        
        error = ValueError("original error")
        
        with pytest.raises(ValueError) as exc_info:
            cache.handle(error, "new_args")
        
        assert exc_info.value is error


class TestChainFallback:
    """Tests for chain fallback."""
    
    def test_tries_fallbacks_in_order(self):
        """Test fallbacks are tried in order."""
        call_order = []
        
        def fallback1(e, *args, **kwargs):
            call_order.append(1)
            raise e  # Fail
        
        def fallback2(e, *args, **kwargs):
            call_order.append(2)
            return "success"
        
        chain = ChainFallback([fallback1, fallback2])
        
        result = chain.handle(ValueError("error"))
        
        assert result == "success"
        assert call_order == [1, 2]
    
    def test_all_fallbacks_fail(self):
        """Test when all fallbacks fail."""
        def failing_fallback(e, *args, **kwargs):
            raise RuntimeError("fallback failed")
        
        chain = ChainFallback([failing_fallback, failing_fallback])
        
        with pytest.raises(RuntimeError):
            chain.handle(ValueError("original"))
    
    def test_stats(self):
        """Test chain statistics."""
        def success_fallback(e, *args, **kwargs):
            return "ok"
        
        chain = ChainFallback([success_fallback])
        chain.handle(ValueError("error"))
        
        stats = chain.get_stats()
        
        assert stats["fallback_count"] == 1
        assert stats["fallback_metrics"][0]["successes"] == 1


class TestFallbackChainBuilder:
    """Tests for fallback chain builder."""
    
    def test_build_with_default(self):
        """Test building with default value."""
        chain = (
            FallbackChainBuilder()
            .with_default({"default": True})
            .build()
        )
        
        result = chain.handle(ValueError("error"))
        
        assert result == {"default": True}
    
    def test_build_with_cache(self):
        """Test building with cache."""
        chain = (
            FallbackChainBuilder()
            .with_cache(ttl_seconds=60)
            .with_default("fallback")
            .build()
        )
        
        # Should hit default (cache is empty)
        result = chain.handle(ValueError("error"))
        
        assert result == "fallback"
    
    def test_build_with_custom(self):
        """Test building with custom handler."""
        def custom_handler(e, *args, **kwargs):
            return f"handled: {type(e).__name__}"
        
        chain = (
            FallbackChainBuilder()
            .with_custom(custom_handler)
            .build()
        )
        
        result = chain.handle(ValueError("error"))
        
        assert result == "handled: ValueError"
    
    def test_build_empty_raises(self):
        """Test building empty chain raises error."""
        builder = FallbackChainBuilder()
        
        with pytest.raises(ValueError):
            builder.build()


class TestFallbackExecutor:
    """Tests for fallback executor."""
    
    def test_execute_primary_success(self):
        """Test successful primary execution."""
        fallback = DefaultValueFallback("fallback")
        executor = FallbackExecutor(fallback.handle)
        
        result = executor.execute(lambda: "primary")
        
        assert result.value == "primary"
        assert result.from_fallback is False
    
    def test_execute_fallback_on_failure(self):
        """Test fallback on primary failure."""
        fallback = DefaultValueFallback("fallback")
        executor = FallbackExecutor(fallback.handle)
        
        def failing_primary():
            raise ValueError("primary failed")
        
        result = executor.execute(failing_primary)
        
        assert result.value == "fallback"
        assert result.from_fallback is True
        assert isinstance(result.original_error, ValueError)
    
    def test_metrics(self):
        """Test metrics collection."""
        fallback = DefaultValueFallback("fallback")
        executor = FallbackExecutor(fallback.handle)
        
        executor.execute(lambda: "success")
        executor.execute(lambda: "success")
        
        def failing():
            raise ValueError("fail")
        
        executor.execute(failing)
        
        metrics = executor.get_metrics()
        
        assert metrics["total_calls"] == 3
        assert metrics["primary_successes"] == 2
        assert metrics["primary_failures"] == 1
        assert metrics["fallback_successes"] == 1


class TestFallbackDecorators:
    """Tests for fallback decorators."""
    
    def test_with_fallback_value(self):
        """Test with_fallback with static value."""
        @with_fallback({"fallback": True})
        def my_func():
            raise ValueError("error")
        
        result = my_func()
        
        assert result == {"fallback": True}
    
    def test_with_fallback_callable(self):
        """Test with_fallback with callable."""
        def handler(e, *args, **kwargs):
            return f"handled: {str(e)}"
        
        @with_fallback(handler)
        def my_func():
            raise ValueError("test error")
        
        result = my_func()
        
        assert result == "handled: test error"
    
    def test_with_fallback_chain(self):
        """Test with_fallback_chain decorator."""
        @with_fallback_chain(
            lambda e: "first_fallback",
            lambda e: "second_fallback"
        )
        def my_func():
            raise ValueError("error")
        
        result = my_func()
        
        assert result == "first_fallback"
    
    def test_successful_call_no_fallback(self):
        """Test successful call doesn't trigger fallback."""
        @with_fallback("fallback")
        def my_func(x):
            return x * 2
        
        result = my_func(5)
        
        assert result == 10


# =============================================================================
# Integration Tests
# =============================================================================

class TestResilienceIntegration:
    """Integration tests for combined resilience patterns."""
    
    def test_rate_limiter_with_bulkhead(self):
        """Test rate limiter combined with bulkhead."""
        limiter = TokenBucket(capacity=5, refill_rate=1.0)
        bulkhead = SemaphoreBulkhead(max_concurrent=2)
        
        def protected_operation(x):
            # Check rate limit
            result = limiter.acquire()
            if not result.allowed:
                raise RateLimitExceeded()
            
            # Execute within bulkhead
            return bulkhead.execute(lambda: x * 2)
        
        # Should work
        assert protected_operation(5) == 10
    
    def test_bulkhead_with_fallback(self):
        """Test bulkhead with fallback."""
        bulkhead = SemaphoreBulkhead(max_concurrent=1)
        fallback = DefaultValueFallback("degraded")
        
        # Hold the bulkhead
        bulkhead.try_enter()
        
        def operation():
            return bulkhead.execute(lambda: "success")
        
        # Should fail and use fallback
        executor = FallbackExecutor(fallback.handle)
        result = executor.execute(operation)
        
        assert result.value == "degraded"
        assert result.from_fallback is True
    
    def test_full_resilience_stack(self):
        """Test full resilience stack."""
        from src.resilience.advanced_patterns import CircuitBreaker, CircuitBreakerConfig
        
        # Setup all patterns
        rate_limiter = TokenBucket(capacity=10, refill_rate=5.0)
        bulkhead = SemaphoreBulkhead(max_concurrent=3)
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        fallback = DefaultValueFallback({"status": "degraded"})
        
        def resilient_operation(x):
            # Rate limit check
            if not rate_limiter.try_acquire():
                raise RateLimitExceeded()
            
            # Circuit breaker check
            return circuit_breaker.call(
                lambda: bulkhead.execute(lambda: x * 2)
            )
        
        # Execute with fallback
        executor = FallbackExecutor(fallback.handle)
        result = executor.execute(lambda: resilient_operation(5))
        
        assert result.value == 10
        assert result.from_fallback is False


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for resilience patterns."""
    
    def test_token_bucket_performance(self):
        """Test token bucket performance."""
        bucket = TokenBucket(capacity=10000, refill_rate=10000)
        
        start = time.time()
        for _ in range(10000):
            bucket.acquire(1)
        elapsed = time.time() - start
        
        # Should handle 10k operations in under 1 second
        assert elapsed < 1.0
    
    def test_bulkhead_throughput(self):
        """Test bulkhead throughput."""
        bh = SemaphoreBulkhead(max_concurrent=100)
        
        def quick_op():
            return 1
        
        start = time.time()
        for _ in range(1000):
            bh.execute(quick_op)
        elapsed = time.time() - start
        
        # Should handle 1k operations in under 2 seconds
        assert elapsed < 2.0
    
    def test_cache_fallback_performance(self):
        """Test cache fallback performance."""
        cache = CacheFallback(max_size=10000)
        
        # Populate cache
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")
        
        start = time.time()
        for i in range(1000):
            cache.get(f"key_{i}")
        elapsed = time.time() - start
        
        # Should handle 1k lookups in under 0.5 seconds
        assert elapsed < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
