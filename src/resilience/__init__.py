"""
Enhanced Resilience Patterns Module
====================================

Comprehensive resilience patterns for distributed systems:
- Circuit Breaker with configurable thresholds
- Bulkhead Pattern for component isolation
- Retry with exponential backoff and jitter
- Timeout Pattern with cascade protection
- Health Check endpoints with graceful degradation
- Rate Limiting with multiple algorithms
- Fallback patterns for graceful degradation

Version: 2.0.0
"""

from src.resilience.advanced_patterns import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    RetryStrategy,
    BulkheadIsolation,
    Bulkhead,
    FallbackHandler,
    ResilientExecutor,
    get_resilient_executor,
)
from src.resilience.timeout import (
    TimeoutConfig,
    TimeoutPattern,
    TimeoutError,
    CascadeTimeout,
)
from src.resilience.health_check import (
    HealthCheckConfig,
    HealthStatus,
    HealthCheckEndpoint,
    HealthCheckResult,
    GracefulDegradation,
)
from src.resilience.retry import (
    RetryConfig,
    RetryPolicy,
    ExponentialBackoff,
    JitterType,
)
from src.resilience.rate_limiter import (
    RateLimiterType,
    RateLimitConfig,
    RateLimitExceeded,
    RateLimitResult,
    TokenBucket,
    SlidingWindowCounter,
    LeakyBucket,
    AdaptiveRateLimiter,
    DistributedRateLimiter,
    RateLimiterFactory,
    rate_limit,
)
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
    bulkhead as bulkhead_decorator,
)
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

__all__ = [
    # Circuit Breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    # Retry
    "RetryStrategy",
    "RetryConfig",
    "RetryPolicy",
    "ExponentialBackoff",
    "JitterType",
    # Bulkhead (Legacy)
    "BulkheadIsolation",
    "Bulkhead",
    # Bulkhead (Advanced)
    "BulkheadType",
    "BulkheadConfig",
    "BulkheadStats",
    "BulkheadFullException",
    "SemaphoreBulkhead",
    "QueueBulkhead",
    "PartitionedBulkhead",
    "AdaptiveBulkhead",
    "BulkheadRegistry",
    "bulkhead_decorator",
    # Fallback (Legacy)
    "FallbackHandler",
    # Fallback (Advanced)
    "FallbackType",
    "FallbackResult",
    "FallbackConfig",
    "FallbackMetrics",
    "DefaultValueFallback",
    "CacheFallback",
    "ChainFallback",
    "CircuitFallback",
    "AsyncFallback",
    "FallbackChainBuilder",
    "FallbackExecutor",
    "with_fallback",
    "with_fallback_chain",
    # Rate Limiter
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
    # Timeout
    "TimeoutConfig",
    "TimeoutPattern",
    "TimeoutError",
    "CascadeTimeout",
    # Health Check
    "HealthCheckConfig",
    "HealthStatus",
    "HealthCheckEndpoint",
    "HealthCheckResult",
    "GracefulDegradation",
    # Executor
    "ResilientExecutor",
    "get_resilient_executor",
]
