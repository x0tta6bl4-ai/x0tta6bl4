"""Retry, degradation, and shutdown utilities."""

from __future__ import annotations

import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def with_retry(
    config: Optional[RetryConfig] = None,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        config: Retry configuration
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Callback function called on each retry
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base**attempt),
                        config.max_delay,
                    )

                    # Add jitter if enabled
                    if config.jitter:
                        import random

                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s due to: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e),
                        },
                    )

                    if on_retry:
                        on_retry(attempt, e, delay)

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


# ==================== Graceful Degradation ====================


class DegradationLevel(Enum):
    """Levels of graceful degradation"""

    FULL = "full"  # All features available
    DEGRADED = "degraded"  # Some features unavailable
    MINIMAL = "minimal"  # Only basic features
    OFFLINE = "offline"  # No external connections


@dataclass
class DegradationState:
    """Current degradation state"""

    level: DegradationLevel = DegradationLevel.FULL
    prometheus_available: bool = True
    bpftool_available: bool = True
    last_check: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0

    def update_prometheus_status(self, available: bool):
        """Update Prometheus availability status"""
        if available:
            self.consecutive_failures = 0
            if not self.prometheus_available:
                logger.info("Prometheus endpoint recovered")
        else:
            self.consecutive_failures += 1
            self.error_count += 1

        self.prometheus_available = available
        self._recalculate_level()

    def _recalculate_level(self):
        """Recalculate degradation level based on current state"""
        if self.prometheus_available and self.bpftool_available:
            self.level = DegradationLevel.FULL
        elif self.bpftool_available:
            self.level = DegradationLevel.DEGRADED
        elif self.prometheus_available:
            self.level = DegradationLevel.MINIMAL
        else:
            self.level = DegradationLevel.OFFLINE


# ==================== Signal Handling ====================


class GracefulShutdown:
    """Handler for graceful shutdown on signals"""

    def __init__(self):
        self.shutdown_requested = False
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        with self._lock:
            self.shutdown_requested = True

            # Execute callbacks
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in shutdown callback: {e}")

    def register_callback(self, callback: Callable):
        """Register a callback to be called on shutdown"""
        with self._lock:
            self._callbacks.append(callback)

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self.shutdown_requested


# ==================== Structured Logging ====================
