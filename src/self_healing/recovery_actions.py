"""
Production-ready Recovery Actions for MAPE-K

DEPRECATED: Use src.self_healing.recovery instead.
"""
from __future__ import annotations
import warnings

from .recovery import (
    CircuitBreaker,
    CircuitBreakerState,
    RateLimiter,
    RecoveryActionExecutor,
    RecoveryActionType,
    RecoveryResult,
)

warnings.warn(
    "recovery_actions.py is deprecated. Use src.self_healing.recovery instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState",
    "RateLimiter",
    "RecoveryActionExecutor",
    "RecoveryActionType",
    "RecoveryResult",
]

