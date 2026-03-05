"""
Shared reliability policies and degraded-dependency markers.

Centralizes timeout/retry/circuit-breaker defaults and response metadata
for graceful degradation across API handlers.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, TypeVar

from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerOpen,
                                      create_circuit_breaker,
                                      get_circuit_breaker)
from src.core.connection_retry import RetryExhausted, RetryPolicy, with_retry

logger = logging.getLogger(__name__)

T = TypeVar("T")
_DEGRADED_DEPS_ATTR = "degraded_dependencies"
_DEGRADED_HEADER = "X-Degraded-Dependencies"


@dataclass(frozen=True)
class ReliabilityPolicy:
    """Timeout/retry/circuit policy for a dependency."""

    timeout_seconds: float = 8.0
    max_retries: int = 2
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    retryable_exceptions: tuple[type[BaseException], ...] = (
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
        OSError,
    )


def _env_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default=%s", name, raw, default)
        return default
    return max(minimum, parsed)


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r, using default=%s", name, raw, default)
        return default
    return max(minimum, parsed)


def policy_for_dependency(dependency: str) -> ReliabilityPolicy:
    """
    Build policy from env vars with dependency-specific prefix.

    Example for dependency "stripe":
    - RELIABILITY_STRIPE_TIMEOUT_SECONDS
    - RELIABILITY_STRIPE_MAX_RETRIES
    - RELIABILITY_STRIPE_BASE_DELAY_SECONDS
    - RELIABILITY_STRIPE_MAX_DELAY_SECONDS
    - RELIABILITY_STRIPE_FAILURE_THRESHOLD
    - RELIABILITY_STRIPE_RECOVERY_TIMEOUT_SECONDS
    """
    dep = dependency.upper().replace("-", "_")
    base = f"RELIABILITY_{dep}"
    return ReliabilityPolicy(
        timeout_seconds=_env_float(f"{base}_TIMEOUT_SECONDS", 8.0, 0.05),
        max_retries=_env_int(f"{base}_MAX_RETRIES", 2, 0),
        base_delay_seconds=_env_float(f"{base}_BASE_DELAY_SECONDS", 0.25, 0.0),
        max_delay_seconds=_env_float(f"{base}_MAX_DELAY_SECONDS", 2.0, 0.0),
        failure_threshold=_env_int(f"{base}_FAILURE_THRESHOLD", 3, 1),
        recovery_timeout_seconds=_env_float(
            f"{base}_RECOVERY_TIMEOUT_SECONDS", 30.0, 0.1
        ),
    )


def build_retry_policy(policy: ReliabilityPolicy) -> RetryPolicy:
    """Convert reliability policy to connection retry policy."""
    return RetryPolicy(
        max_retries=policy.max_retries,
        base_delay=policy.base_delay_seconds,
        max_delay=policy.max_delay_seconds,
        jitter=True,
        retryable_exceptions=policy.retryable_exceptions,
    )


def get_or_create_dependency_circuit(
    dependency: str,
    policy: ReliabilityPolicy,
    *,
    circuit_name: Optional[str] = None,
) -> CircuitBreaker:
    """Resolve named circuit breaker or create one with dependency defaults."""
    name = circuit_name or f"{dependency}_dependency"
    existing = get_circuit_breaker(name)
    if existing is not None:
        return existing
    return create_circuit_breaker(
        name=name,
        failure_threshold=policy.failure_threshold,
        recovery_timeout=policy.recovery_timeout_seconds,
    )


async def call_with_reliability(
    operation: Callable[[], Awaitable[T]],
    *,
    dependency: str,
    policy: Optional[ReliabilityPolicy] = None,
    circuit_name: Optional[str] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> T:
    """
    Execute async operation with timeout + retry + circuit breaker.

    Raises:
        RetryExhausted: when retry budget is exhausted
        CircuitBreakerOpen: when circuit is open
        Any exception from the operation if not retryable or no retries left
    """
    active_policy = policy or policy_for_dependency(dependency)
    active_circuit = circuit_breaker or get_or_create_dependency_circuit(
        dependency, active_policy, circuit_name=circuit_name
    )
    retry_policy = build_retry_policy(active_policy)

    async def _timed_operation() -> T:
        return await asyncio.wait_for(
            operation(),
            timeout=active_policy.timeout_seconds,
        )

    return await with_retry(
        _timed_operation,
        policy=retry_policy,
        circuit_breaker=active_circuit,
    )


def mark_degraded_dependency(target: Any, dependency: str) -> None:
    """Mark dependency as degraded on request.state-like object."""
    if not dependency:
        return
    state = target.state if hasattr(target, "state") else target
    current = getattr(state, _DEGRADED_DEPS_ATTR, None)
    if current is None or not isinstance(current, set):
        current = set()
        setattr(state, _DEGRADED_DEPS_ATTR, current)
    current.add(str(dependency).strip().lower())


def get_degraded_dependencies(target: Any) -> list[str]:
    """Get sorted degraded dependency names from request.state-like object."""
    state = target.state if hasattr(target, "state") else target
    current = getattr(state, _DEGRADED_DEPS_ATTR, None)
    if not current:
        return []
    return sorted(str(dep).strip().lower() for dep in current if str(dep).strip())


def set_degraded_dependencies_header(response: Any, target: Any) -> None:
    """
    Attach degraded-dependency header to response when present.

    Header format:
        X-Degraded-Dependencies: dependency-a,dependency-b
    """
    if response is None:
        return
    degraded = get_degraded_dependencies(target)
    if degraded:
        response.headers[_DEGRADED_HEADER] = ",".join(degraded)


__all__ = [
    "CircuitBreakerOpen",
    "ReliabilityPolicy",
    "RetryExhausted",
    "build_retry_policy",
    "call_with_reliability",
    "get_degraded_dependencies",
    "get_or_create_dependency_circuit",
    "mark_degraded_dependency",
    "policy_for_dependency",
    "set_degraded_dependencies_header",
]
