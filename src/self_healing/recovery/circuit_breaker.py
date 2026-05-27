"""
Recovery Actions for MAPE-K
"""
import logging
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

from .models import CircuitBreakerState

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Self-healing recovery action event only. It records local policy, safety, "
    "and execution decisions and does not prove production rollout or live "
    "operator-approved remediation by itself."
)



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
    ):
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
            if (
                self.state.opened_at
                and (datetime.now() - self.state.opened_at) < self.timeout
            ):
                raise Exception("Circuit breaker is OPEN - too many failures")
            else:
                # Transition to half-open
                self.state.state = "half_open"
                logger.info("Circuit breaker transitioning to HALF_OPEN")

        try:
            result = func(*args, **kwargs)
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
        self.state.failures += 1
        self.state.last_failure_time = datetime.now()

        if self.state.failures >= self.failure_threshold:
            self.state.state = "open"
            self.state.opened_at = datetime.now()
            logger.warning(
                f"Circuit breaker OPENED after {self.state.failures} failures"
            )
