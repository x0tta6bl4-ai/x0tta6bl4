"""
src.core.resilience — Circuit breaker, retry, reliability patterns.
"""
from __future__ import annotations

from src.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from src.core.resilience.connection_retry import RetryExhausted, RetryPolicy, with_retry
from src.core.resilience.reliability_policy import (
    mark_degraded_dependency,
    set_degraded_dependencies_header,
)
from src.core.resilience.resilience_patterns import ResiliencePattern

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "RetryExhausted",
    "RetryPolicy",
    "with_retry",
    "ResiliencePattern",
    "mark_degraded_dependency",
    "set_degraded_dependencies_header",
]

