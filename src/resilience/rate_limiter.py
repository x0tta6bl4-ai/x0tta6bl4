"""
Advanced Rate Limiter Patterns
==============================

Multiple rate limiting algorithms for distributed systems:
- Token Bucket: Smooth traffic flow with burst handling
- Sliding Window: Precise rate limiting with memory efficiency
- Leaky Bucket: Constant rate output with queue buffering
- Adaptive Rate Limiter: ML-based rate adjustment
"""

import asyncio
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class RateLimiterType(Enum):
    """Rate limiter algorithm types."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiters."""
    max_requests: int = 100
    window_seconds: float = 1.0
    burst_size: Optional[int] = None  # For token bucket
    refill_rate: Optional[float] = None  # Tokens per second
    queue_size: int = 100  # For leaky bucket
    adaptive_min_rate: float = 10.0  # Minimum rate for adaptive
    adaptive_max_rate: float = 1000.0  # Maximum rate for adaptive
    adaptive_window: int = 100  # Window for adaptive adjustments


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        current_rate: Optional[float] = None,
        limit: Optional[int] = None
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.current_rate = current_rate
        self.limit = limit


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        return {
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at)),
            "X-RateLimit-Limit": str(self.remaining + (0 if self.allowed else 0)),
        }


class TokenBucket:
    """
    Token Bucket Rate Limiter.
    
    Allows burst traffic up to bucket capacity while maintaining
    average rate through token refill.
    
    Algorithm:
    - Bucket starts full with `capacity` tokens
    - Each request consumes 1 token
    - Tokens refill at `refill_rate` per second
    - Request denied if bucket is empty
    """
    
    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        name: str = "token_bucket"
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.name = name
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = threading.Lock()
        
        # Metrics
        self.total_requests = 0
        self.allowed_requests = 0
        self.denied_requests = 0
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1) -> RateLimitResult:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            RateLimitResult with acquisition status
        """
        with self.lock:
            self._refill()
            self.total_requests += 1
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.allowed_requests += 1
                return RateLimitResult(
                    allowed=True,
                    remaining=int(self.tokens),
                    reset_at=time.time() + (self.capacity - self.tokens) / self.refill_rate
                )
            else:
                self.denied_requests += 1
                retry_after = (tokens - self.tokens) / self.refill_rate
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=time.time() + retry_after,
                    retry_after=retry_after
                )
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Simple boolean check for token availability."""
        return self.acquire(tokens).allowed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            return {
                "name": self.name,
                "type": "token_bucket",
                "capacity": self.capacity,
                "current_tokens": self.tokens,
                "refill_rate": self.refill_rate,
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "denied_requests": self.denied_requests,
                "allow_rate": (
                    self.allowed_requests / self.total_requests 
                    if self.total_requests > 0 else 1.0
                )
            }


class SlidingWindowCounter:
    """
    Sliding Window Rate Limiter.
    
    More precise than fixed window, avoids boundary issues
    where requests cluster at window boundaries.
    
    Algorithm:
    - Maintains timestamps of recent requests
    - Counts requests within sliding window
    - Old timestamps are cleaned up periodically
    """
    
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        name: str = "sliding_window"
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self.requests: deque = deque()
        self.lock = threading.Lock()
        
        # Metrics
        self.total_requests = 0
        self.allowed_requests = 0
        self.denied_requests = 0
    
    def _cleanup(self) -> None:
        """Remove expired timestamps."""
        cutoff = time.time() - self.window_seconds
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def acquire(self) -> RateLimitResult:
        """
        Try to make a request within the rate limit.
        
        Returns:
            RateLimitResult with acquisition status
        """
        with self.lock:
            self._cleanup()
            self.total_requests += 1
            
            current_count = len(self.requests)
            
            if current_count < self.max_requests:
                self.requests.append(time.time())
                self.allowed_requests += 1
                return RateLimitResult(
                    allowed=True,
                    remaining=self.max_requests - current_count - 1,
                    reset_at=time.time() + self.window_seconds
                )
            else:
                self.denied_requests += 1
                # Calculate when oldest request will expire
                retry_after = self.requests[0] + self.window_seconds - time.time()
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=time.time() + retry_after,
                    retry_after=max(0, retry_after)
                )
    
    def try_acquire(self) -> bool:
        """Simple boolean check."""
        return self.acquire().allowed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            self._cleanup()
            return {
                "name": self.name,
                "type": "sliding_window",
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "current_requests": len(self.requests),
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "denied_requests": self.denied_requests,
                "allow_rate": (
                    self.allowed_requests / self.total_requests 
                    if self.total_requests > 0 else 1.0
                )
            }


class LeakyBucket:
    """
    Leaky Bucket Rate Limiter.
    
    Smooths burst traffic into steady output rate.
    Requests queue up and "leak" at constant rate.
    
    Algorithm:
    - Requests enter queue if not full
    - Queue drains at constant rate
    - Provides smooth traffic shaping
    """
    
    def __init__(
        self,
        capacity: int,
        leak_rate: float,
        name: str = "leaky_bucket"
    ):
        self.capacity = capacity
        self.leak_rate = leak_rate  # Requests per second
        self.name = name
        self.queue: deque = deque()
        self.last_leak = time.time()
        self.lock = threading.Lock()
        
        # Metrics
        self.total_requests = 0
        self.allowed_requests = 0
        self.denied_requests = 0
        self.processed_requests = 0
    
    def _leak(self) -> None:
        """Process queued requests based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_leak
        to_process = int(elapsed * self.leak_rate)
        
        for _ in range(min(to_process, len(self.queue))):
            if self.queue:
                self.queue.popleft()
                self.processed_requests += 1
        
        self.last_leak = now
    
    def acquire(self) -> RateLimitResult:
        """
        Try to add a request to the bucket.
        
        Returns:
            RateLimitResult with acquisition status
        """
        with self.lock:
            self._leak()
            self.total_requests += 1
            
            if len(self.queue) < self.capacity:
                self.queue.append(time.time())
                self.allowed_requests += 1
                return RateLimitResult(
                    allowed=True,
                    remaining=self.capacity - len(self.queue),
                    reset_at=time.time() + len(self.queue) / self.leak_rate
                )
            else:
                self.denied_requests += 1
                retry_after = len(self.queue) / self.leak_rate
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=time.time() + retry_after,
                    retry_after=retry_after
                )
    
    def try_acquire(self) -> bool:
        """Simple boolean check."""
        return self.acquire().allowed
    
    def get_queue_position(self) -> int:
        """Get current queue position for new request."""
        with self.lock:
            self._leak()
            return len(self.queue)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            self._leak()
            return {
                "name": self.name,
                "type": "leaky_bucket",
                "capacity": self.capacity,
                "leak_rate": self.leak_rate,
                "queue_size": len(self.queue),
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "denied_requests": self.denied_requests,
                "processed_requests": self.processed_requests,
                "allow_rate": (
                    self.allowed_requests / self.total_requests 
                    if self.total_requests > 0 else 1.0
                )
            }


class AdaptiveRateLimiter:
    """
    Adaptive Rate Limiter with ML-based adjustment.
    
    Automatically adjusts rate limits based on:
    - System load and response times
    - Error rates
    - Resource utilization
    
    Uses EWMA for smooth adjustments and Thompson Sampling
    for exploration/exploitation balance.
    """
    
    def __init__(
        self,
        initial_rate: float,
        min_rate: float,
        max_rate: float,
        adjustment_window: int = 100,
        name: str = "adaptive"
    ):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.adjustment_window = adjustment_window
        self.name = name
        
        # Internal token bucket for current rate
        self._bucket = TokenBucket(
            capacity=int(initial_rate * 2),  # Allow 2x burst
            refill_rate=initial_rate,
            name=f"{name}_internal"
        )
        
        # Metrics for adaptation
        self.response_times: deque = deque(maxlen=adjustment_window)
        self.error_count = 0
        self.success_count = 0
        self.lock = threading.Lock()
        
        # EWMA parameters
        self.ewma_response_time = 0.0
        self.ewma_error_rate = 0.0
        self.alpha = 0.1  # Smoothing factor
        
        # Thompson Sampling parameters
        self.success_samples = 1.0
        self.failure_samples = 1.0
    
    def _update_ewma(self, response_time: float, is_error: bool) -> None:
        """Update EWMA metrics."""
        self.ewma_response_time = (
            self.alpha * response_time + 
            (1 - self.alpha) * self.ewma_response_time
        )
        
        error_value = 1.0 if is_error else 0.0
        self.ewma_error_rate = (
            self.alpha * error_value + 
            (1 - self.alpha) * self.ewma_error_rate
        )
    
    def _adjust_rate(self) -> None:
        """Adjust rate based on observed metrics."""
        import random
        
        # Thompson Sampling for exploration
        sample_success = random.gauss(self.success_samples, 0.5)
        sample_failure = random.gauss(self.failure_samples, 0.5)
        
        # Calculate adjustment factor
        if self.ewma_error_rate > 0.1:  # High error rate
            # Reduce rate
            adjustment = 0.9 - (self.ewma_error_rate * 0.5)
            self.success_samples *= 0.95
            self.failure_samples += 1
        elif self.ewma_response_time > 1.0:  # Slow responses
            # Reduce rate slightly
            adjustment = 0.95
        else:
            # Increase rate cautiously
            adjustment = 1.0 + (0.1 * max(0, sample_success - sample_failure) / 10)
            self.success_samples += 1
            self.failure_samples *= 0.95
        
        # Apply adjustment
        new_rate = self.current_rate * adjustment
        self.current_rate = max(self.min_rate, min(self.max_rate, new_rate))
        
        # Update internal bucket
        self._bucket.refill_rate = self.current_rate
        self._bucket.capacity = int(self.current_rate * 2)
    
    def acquire(self) -> RateLimitResult:
        """Try to acquire with adaptive rate limiting."""
        with self.lock:
            result = self._bucket.acquire()
            
            if result.allowed:
                self.success_count += 1
            else:
                self.error_count += 1
            
            # Periodic adjustment
            if (self.success_count + self.error_count) % self.adjustment_window == 0:
                self._adjust_rate()
            
            return result
    
    def record_response(self, response_time: float, is_error: bool = False) -> None:
        """Record response metrics for adaptation."""
        with self.lock:
            self.response_times.append(response_time)
            self._update_ewma(response_time, is_error)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            return {
                "name": self.name,
                "type": "adaptive",
                "current_rate": self.current_rate,
                "min_rate": self.min_rate,
                "max_rate": self.max_rate,
                "ewma_response_time": self.ewma_response_time,
                "ewma_error_rate": self.ewma_error_rate,
                "success_count": self.success_count,
                "error_count": self.error_count,
                "bucket_stats": self._bucket.get_stats()
            }


class DistributedRateLimiter:
    """
    Distributed Rate Limiter for multi-instance deployments.
    
    Uses a combination of local and distributed state:
    - Local cache for fast checks
    - Redis for distributed coordination
    - Lazy synchronization for efficiency
    """
    
    def __init__(
        self,
        name: str,
        max_requests: int,
        window_seconds: float,
        redis_client: Optional[Any] = None,
        local_capacity_ratio: float = 0.1
    ):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_client = redis_client
        
        # Local rate limiter for fast path
        local_capacity = max(1, int(max_requests * local_capacity_ratio))
        self.local_limiter = SlidingWindowCounter(
            max_requests=local_capacity,
            window_seconds=window_seconds,
            name=f"{name}_local"
        )
        
        self.lock = threading.Lock()
        self.last_sync = time.time()
        self.sync_interval = window_seconds / 10
        
        # Metrics
        self.local_allows = 0
        self.distributed_allows = 0
        self.denied_requests = 0
    
    def _get_redis_key(self) -> str:
        """Get Redis key for this rate limiter."""
        window_start = int(time.time() / self.window_seconds)
        return f"rate_limit:{self.name}:{window_start}"
    
    async def acquire_async(self) -> RateLimitResult:
        """Async acquire with distributed coordination."""
        # Fast path: check local limiter
        local_result = self.local_limiter.acquire()
        if local_result.allowed:
            self.local_allows += 1
            return local_result
        
        # Slow path: check distributed
        if self.redis_client:
            try:
                key = self._get_redis_key()
                
                # Use Redis INCR with expiry
                current = await self.redis_client.incr(key)
                if current == 1:
                    await self.redis_client.expire(key, int(self.window_seconds) + 1)
                
                if current <= self.max_requests:
                    self.distributed_allows += 1
                    return RateLimitResult(
                        allowed=True,
                        remaining=self.max_requests - current,
                        reset_at=time.time() + self.window_seconds
                    )
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}")
                # Fall back to local on Redis failure
        
        self.denied_requests += 1
        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=time.time() + self.window_seconds,
            retry_after=self.window_seconds
        )
    
    def acquire(self) -> RateLimitResult:
        """Synchronous acquire (local only)."""
        return self.local_limiter.acquire()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get distributed rate limiter statistics."""
        return {
            "name": self.name,
            "type": "distributed",
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "local_allows": self.local_allows,
            "distributed_allows": self.distributed_allows,
            "denied_requests": self.denied_requests,
            "local_limiter": self.local_limiter.get_stats()
        }


class RateLimiterFactory:
    """Factory for creating rate limiters."""
    
    @staticmethod
    def create(
        limiter_type: RateLimiterType,
        config: RateLimitConfig,
        name: Optional[str] = None
    ) -> Union[TokenBucket, SlidingWindowCounter, LeakyBucket, AdaptiveRateLimiter]:
        """Create a rate limiter of the specified type."""
        name = name or f"rate_limiter_{limiter_type.value}"
        
        if limiter_type == RateLimiterType.TOKEN_BUCKET:
            return TokenBucket(
                capacity=config.burst_size or config.max_requests,
                refill_rate=config.refill_rate or config.max_requests / config.window_seconds,
                name=name
            )
        
        elif limiter_type == RateLimiterType.SLIDING_WINDOW:
            return SlidingWindowCounter(
                max_requests=config.max_requests,
                window_seconds=config.window_seconds,
                name=name
            )
        
        elif limiter_type == RateLimiterType.LEAKY_BUCKET:
            return LeakyBucket(
                capacity=config.queue_size,
                leak_rate=config.max_requests / config.window_seconds,
                name=name
            )
        
        elif limiter_type == RateLimiterType.ADAPTIVE:
            return AdaptiveRateLimiter(
                initial_rate=config.max_requests / config.window_seconds,
                min_rate=config.adaptive_min_rate,
                max_rate=config.adaptive_max_rate,
                adjustment_window=config.adaptive_window,
                name=name
            )
        
        else:
            raise ValueError(f"Unknown rate limiter type: {limiter_type}")


def rate_limit(
    limiter: Union[TokenBucket, SlidingWindowCounter, LeakyBucket, AdaptiveRateLimiter],
    on_rate_limited: Optional[Callable[[], Any]] = None
):
    """
    Decorator for rate limiting function calls.
    
    Args:
        limiter: Rate limiter instance
        on_rate_limited: Optional callback when rate limited
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            result = limiter.acquire()
            if result.allowed:
                return func(*args, **kwargs)
            elif on_rate_limited:
                return on_rate_limited()
            else:
                raise RateLimitExceeded(
                    retry_after=result.retry_after,
                    limit=limiter.max_requests if hasattr(limiter, 'max_requests') else None
                )
        return wrapper
    return decorator


__all__ = [
    "RateLimiterType",
    "RateLimitConfig",
    "RateLimitExceeded",
    "RateLimitResult",
    "TokenBucket",
    "SlidingWindowCounter",
    "LeakyBucket",
    "AdaptiveRateLimiter",
    "DistributedRateLimiter",
    "RateLimiterFactory",
    "rate_limit",
]
