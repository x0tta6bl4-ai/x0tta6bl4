"""
Recovery Actions for MAPE-K
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from .models import CircuitBreakerState

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern for recovery actions.

    Prevents cascading failures by stopping execution when failure threshold is reached.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: timedelta = timedelta(seconds=60),
        half_open_timeout: timedelta = timedelta(seconds=30),
        *,
        is_failure: Callable[[Any], bool] | None = None,
    ):
        if failure_threshold < 1 or success_threshold < 1:
            raise ValueError("Circuit breaker thresholds must be positive")
        self.is_failure = is_failure or (lambda result: False)
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout
        self.state = CircuitBreakerState()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state.state == "open":
            if self.state.opened_at and (datetime.now() - self.state.opened_at) < self.timeout:
                raise Exception("Circuit breaker is OPEN - too many failures")
            else:
                # Transition to half-open
                self.state.state = "half_open"
                self.state.successes = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")

        try:
            result = func(*args, **kwargs)
            if self.is_failure(result):
                self._on_failure()
            else:
                self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful execution"""
        if self.state.state == "half_open":
            self.state.successes += 1
            if self.state.successes >= self.success_threshold:
                self.state.state = "closed"
                self.state.failures = 0
                self.state.successes = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        else:
            self.state.successes += 1
            self.state.failures = 0

    def _on_failure(self):
        """Handle failed execution"""
        self.state.successes = 0
        self.state.failures += 1
        self.state.last_failure_time = datetime.now()

        if self.state.state == "half_open" or self.state.failures >= self.failure_threshold:
            self.state.state = "open"
            self.state.opened_at = datetime.now()
            logger.warning(f"Circuit breaker OPENED after {self.state.failures} failures")
