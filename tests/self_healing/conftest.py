"""
Shared fixtures for self_healing module tests.

Provides:
- Circuit breaker fixtures
- Recovery action executor fixtures
- Auto-isolation manager fixtures
- Mock services and infrastructure
- Time manipulation helpers
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Mock optional dependencies before importing src modules
_mocked_modules = {
    "hvac": MagicMock(),
    "hvac.exceptions": MagicMock(),
    "hvac.api": MagicMock(),
    "hvac.api.auth_methods": MagicMock(),
    "prometheus_client": MagicMock(),
}

for mod_name, mock_obj in _mocked_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

# Import modules under test
from src.core.circuit_breaker import (CircuitBreaker, CircuitBreakerMetrics,
                                      CircuitBreakerOpen, CircuitState,
                                      _circuit_breakers,
                                      create_circuit_breaker,
                                      get_circuit_breaker)
from src.security.auto_isolation import AutoIsolationManager
from src.security.auto_isolation import \
    CircuitBreaker as IsolationCircuitBreaker
from src.security.auto_isolation import (IsolationLevel, IsolationPolicy,
                                         IsolationReason, IsolationRecord,
                                         QuarantineZone)
from src.self_healing.recovery_actions import \
    CircuitBreaker as RecoveryCircuitBreaker
from src.self_healing.recovery_actions import (RateLimiter,
                                               RecoveryActionExecutor,
                                               RecoveryActionType,
                                               RecoveryResult)

# ============================================================================
# CIRCUIT BREAKER FIXTURES
# ============================================================================


@pytest.fixture
def circuit_breaker() -> Generator[CircuitBreaker, None, None]:
    """Fresh circuit breaker for each test."""
    cb = CircuitBreaker(
        name="test_circuit",
        failure_threshold=3,
        recovery_timeout=5.0,
        half_open_max_calls=2,
        success_threshold=2,
    )
    yield cb
    # Cleanup from global registry
    if "test_circuit" in _circuit_breakers:
        del _circuit_breakers["test_circuit"]


@pytest.fixture
def circuit_breaker_with_fallback() -> Generator[CircuitBreaker, None, None]:
    """Circuit breaker with fallback function."""

    async def fallback(*args, **kwargs):
        return {"fallback": True, "args": args}

    cb = CircuitBreaker(
        name="test_circuit_fallback",
        failure_threshold=2,
        recovery_timeout=1.0,
        fallback=fallback,
    )
    yield cb
    if "test_circuit_fallback" in _circuit_breakers:
        del _circuit_breakers["test_circuit_fallback"]


@pytest.fixture
def fast_circuit_breaker() -> Generator[CircuitBreaker, None, None]:
    """Circuit breaker with fast recovery for timing tests."""
    cb = CircuitBreaker(
        name="fast_circuit",
        failure_threshold=2,
        recovery_timeout=0.1,  # 100ms for fast tests
        half_open_max_calls=1,
        success_threshold=1,
    )
    yield cb
    if "fast_circuit" in _circuit_breakers:
        del _circuit_breakers["fast_circuit"]


# ============================================================================
# RECOVERY ACTION EXECUTOR FIXTURES
# ============================================================================


@pytest.fixture
def recovery_executor() -> RecoveryActionExecutor:
    """Fresh recovery action executor."""
    return RecoveryActionExecutor(
        node_id="test-node-001",
        enable_circuit_breaker=True,
        enable_rate_limiting=True,
        max_retries=3,
        retry_delay=0.01,  # Fast retries for testing
    )


@pytest.fixture
def recovery_executor_no_protection() -> RecoveryActionExecutor:
    """Recovery executor without circuit breaker or rate limiting."""
    return RecoveryActionExecutor(
        node_id="test-node-002",
        enable_circuit_breaker=False,
        enable_rate_limiting=False,
        max_retries=1,
    )


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """Fresh rate limiter for testing."""
    return RateLimiter(max_actions=5, window_seconds=1)


@pytest.fixture
def recovery_circuit_breaker() -> RecoveryCircuitBreaker:
    """Circuit breaker from recovery_actions module."""
    return RecoveryCircuitBreaker(
        failure_threshold=3,
        success_threshold=2,
        timeout=timedelta(seconds=1),
        half_open_timeout=timedelta(seconds=0.5),
    )


# ============================================================================
# AUTO-ISOLATION FIXTURES
# ============================================================================


@pytest.fixture
def isolation_manager() -> AutoIsolationManager:
    """Fresh auto-isolation manager."""
    return AutoIsolationManager(node_id="manager-node-001")


@pytest.fixture
def isolation_circuit_breaker() -> IsolationCircuitBreaker:
    """Circuit breaker from auto_isolation module."""
    return IsolationCircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1,  # 1 second for fast tests
        half_open_requests=2,
    )


@pytest.fixture
def quarantine_zone() -> QuarantineZone:
    """Fresh quarantine zone."""
    return QuarantineZone(zone_id="test-quarantine-zone")


@pytest.fixture
def isolation_policy() -> IsolationPolicy:
    """Test isolation policy."""
    return IsolationPolicy(
        name="test_policy",
        trigger_reason=IsolationReason.THREAT_DETECTED,
        initial_level=IsolationLevel.RATE_LIMIT,
        escalation_levels=[
            IsolationLevel.RATE_LIMIT,
            IsolationLevel.RESTRICTED,
            IsolationLevel.QUARANTINE,
            IsolationLevel.BLOCKED,
        ],
        escalation_threshold=2,
        initial_duration=60,
        escalation_multiplier=2.0,
        max_duration=3600,
        auto_recover=True,
    )


# ============================================================================
# MOCK SERVICES
# ============================================================================


@pytest.fixture
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Mock subprocess for recovery actions."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_kubernetes() -> Generator[MagicMock, None, None]:
    """Mock kubernetes operations."""
    with patch("subprocess.run") as mock_run:

        def kubectl_handler(args, **kwargs):
            if "kubectl" in args:
                return Mock(returncode=0, stdout="deployment scaled", stderr="")
            return Mock(returncode=1, stdout="", stderr="command not found")

        mock_run.side_effect = kubectl_handler
        yield mock_run


@pytest.fixture
def mock_docker() -> Generator[MagicMock, None, None]:
    """Mock docker operations."""
    with patch("subprocess.run") as mock_run:

        def docker_handler(args, **kwargs):
            if "docker" in args:
                return Mock(returncode=0, stdout="container restarted", stderr="")
            return Mock(returncode=1, stdout="", stderr="command not found")

        mock_run.side_effect = docker_handler
        yield mock_run


# ============================================================================
# TIME MANIPULATION HELPERS
# ============================================================================


@pytest.fixture
def time_freezer():
    """Context manager to freeze time for testing."""

    class TimeFreezer:
        def __init__(self):
            self._original_time = None
            self._frozen_time = None

        def freeze(self, timestamp: float = None):
            """Freeze time at given timestamp or current time."""
            if timestamp is None:
                timestamp = time.time()
            self._frozen_time = timestamp
            self._original_time = time.time

            def frozen_time():
                return self._frozen_time

            time.time = frozen_time
            return self

        def advance(self, seconds: float):
            """Advance frozen time by seconds."""
            if self._frozen_time is not None:
                self._frozen_time += seconds

        def unfreeze(self):
            """Restore original time function."""
            if self._original_time is not None:
                time.time = self._original_time
                self._original_time = None
                self._frozen_time = None

    freezer = TimeFreezer()
    yield freezer
    freezer.unfreeze()


# ============================================================================
# ASYNC HELPERS
# ============================================================================


@pytest.fixture
def async_failing_func():
    """Factory for async functions that fail N times then succeed."""

    def create_func(failures_before_success: int):
        call_count = [0]

        async def func(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= failures_before_success:
                raise Exception(f"Simulated failure {call_count[0]}")
            return {"success": True, "call_count": call_count[0]}

        func.call_count = call_count
        return func

    return create_func


@pytest.fixture
def async_always_fail():
    """Async function that always fails."""

    async def func(*args, **kwargs):
        raise Exception("Always fails")

    return func


@pytest.fixture
def async_always_succeed():
    """Async function that always succeeds."""

    async def func(*args, **kwargs):
        return {"success": True}

    return func


# ============================================================================
# METRICS HELPERS
# ============================================================================


@pytest.fixture
def mock_prometheus():
    """Mock Prometheus metrics."""
    with patch("src.core.circuit_breaker.PROMETHEUS_AVAILABLE", True):
        with patch("src.core.circuit_breaker.CIRCUIT_STATE_GAUGE") as gauge:
            with patch("src.core.circuit_breaker.CIRCUIT_REQUESTS_TOTAL") as requests:
                with patch(
                    "src.core.circuit_breaker.CIRCUIT_FAILURES_TOTAL"
                ) as failures:
                    with patch(
                        "src.core.circuit_breaker.CIRCUIT_STATE_CHANGES_TOTAL"
                    ) as changes:
                        with patch(
                            "src.core.circuit_breaker.CIRCUIT_CALL_DURATION"
                        ) as duration:
                            yield {
                                "gauge": gauge,
                                "requests": requests,
                                "failures": failures,
                                "changes": changes,
                                "duration": duration,
                            }


# ============================================================================
# EVENT TRACKING
# ============================================================================


@pytest.fixture
def event_tracker():
    """Track events for assertion."""

    class EventTracker:
        def __init__(self):
            self.events = []

        def record(self, event_type: str, **kwargs):
            self.events.append({"type": event_type, "timestamp": time.time(), **kwargs})

        def get_events(self, event_type: str = None):
            if event_type:
                return [e for e in self.events if e["type"] == event_type]
            return self.events

        def count(self, event_type: str = None):
            return len(self.get_events(event_type))

        def clear(self):
            self.events.clear()

    return EventTracker()
