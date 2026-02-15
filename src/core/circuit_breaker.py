"""
Circuit Breaker Pattern Implementation

Provides fault tolerance for external API calls with:
- CLOSED/OPEN/HALF_OPEN states
- Exponential backoff
- Fallback mechanisms
- Metrics exposure
- Prometheus integration
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

# Prometheus metrics (optional - graceful degradation if not available)
PROMETHEUS_AVAILABLE = False
CIRCUIT_STATE_GAUGE = None
CIRCUIT_REQUESTS_TOTAL = None
CIRCUIT_FAILURES_TOTAL = None
CIRCUIT_STATE_CHANGES_TOTAL = None
CIRCUIT_CALL_DURATION = None

try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram

    def _get_or_create_gauge(name, description, labels):
        """Get existing metric or create new one."""
        try:
            return Gauge(name, description, labels)
        except ValueError:
            # Already registered, get from registry
            for collector in REGISTRY._names_to_collectors.values():
                if hasattr(collector, "_name") and collector._name == name:
                    return collector
            return None

    def _get_or_create_counter(name, description, labels):
        """Get existing metric or create new one."""
        try:
            return Counter(name, description, labels)
        except ValueError:
            for collector in REGISTRY._names_to_collectors.values():
                if hasattr(collector, "_name") and collector._name == name:
                    return collector
            return None

    def _get_or_create_histogram(name, description, labels, buckets):
        """Get existing metric or create new one."""
        try:
            return Histogram(name, description, labels, buckets=buckets)
        except ValueError:
            for collector in REGISTRY._names_to_collectors.values():
                if hasattr(collector, "_name") and collector._name == name:
                    return collector
            return None

    CIRCUIT_STATE_GAUGE = _get_or_create_gauge(
        "circuit_breaker_state",
        "Current state of circuit breaker (0=closed, 1=open, 2=half_open)",
        ["circuit_name"],
    )
    CIRCUIT_REQUESTS_TOTAL = _get_or_create_counter(
        "circuit_breaker_requests_total",
        "Total requests through circuit breaker",
        ["circuit_name", "result"],
    )
    CIRCUIT_FAILURES_TOTAL = _get_or_create_counter(
        "circuit_breaker_failures_total",
        "Total failures recorded by circuit breaker",
        ["circuit_name"],
    )
    CIRCUIT_STATE_CHANGES_TOTAL = _get_or_create_counter(
        "circuit_breaker_state_changes_total",
        "Total state changes of circuit breaker",
        ["circuit_name", "from_state", "to_state"],
    )
    CIRCUIT_CALL_DURATION = _get_or_create_histogram(
        "circuit_breaker_call_duration_seconds",
        "Duration of calls through circuit breaker",
        ["circuit_name"],
        [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    PROMETHEUS_AVAILABLE = all(
        [
            CIRCUIT_STATE_GAUGE,
            CIRCUIT_REQUESTS_TOTAL,
            CIRCUIT_FAILURES_TOTAL,
            CIRCUIT_STATE_CHANGES_TOTAL,
            CIRCUIT_CALL_DURATION,
        ]
    )
    if PROMETHEUS_AVAILABLE:
        logger.debug("Prometheus metrics enabled for circuit breaker")
except ImportError:
    logger.debug("Prometheus not available - circuit breaker metrics disabled")

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
        }


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing recovery with limited requests

    Configuration:
    - failure_threshold: Number of failures before opening
    - recovery_timeout: Time before attempting recovery
    - half_open_max_calls: Max calls in half-open state
    - success_threshold: Successes needed to close
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        fallback: Optional[Callable[..., T]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

        # Metrics
        self.metrics = CircuitBreakerMetrics()
        self._total_requests = 0
        self._total_failures = 0
        self._total_successes = 0

        # Initialize Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            CIRCUIT_STATE_GAUGE.labels(circuit_name=name).set(0)  # CLOSED

        logger.info(f"🔌 Circuit breaker '{name}' initialized (CLOSED)")

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args, **kwargs: Arguments for function

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerOpen: If circuit is open and no fallback
        """
        async with self._lock:
            self._total_requests += 1
            self.metrics.total_requests = self._total_requests

            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(f"🔌 Circuit '{self.name}' entering HALF_OPEN state")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._failure_count = 0
                    self._success_count = 0
                else:
                    # Circuit is open, use fallback or raise
                    if self.fallback:
                        logger.warning(f"🔌 Circuit '{self.name}' OPEN, using fallback")
                        return await self._execute_fallback(*args, **kwargs)
                    else:
                        raise CircuitBreakerOpen(f"Circuit '{self.name}' is OPEN")

            # In HALF_OPEN, limit concurrent calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    if self.fallback:
                        return await self._execute_fallback(*args, **kwargs)
                    else:
                        raise CircuitBreakerOpen(
                            f"Circuit '{self.name}' HALF_OPEN limit reached"
                        )
                self._half_open_calls += 1

        # Execute the function with timing
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            await self._on_success()

            # Record Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                CIRCUIT_REQUESTS_TOTAL.labels(
                    circuit_name=self.name, result="success"
                ).inc()
                CIRCUIT_CALL_DURATION.labels(circuit_name=self.name).observe(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            await self._on_failure()

            # Record Prometheus failure metrics
            if PROMETHEUS_AVAILABLE:
                CIRCUIT_REQUESTS_TOTAL.labels(
                    circuit_name=self.name, result="failure"
                ).inc()
                CIRCUIT_FAILURES_TOTAL.labels(circuit_name=self.name).inc()
                CIRCUIT_CALL_DURATION.labels(circuit_name=self.name).observe(duration)

            # Note: Fallback is already called in OPEN state check above
            # Only call fallback here if circuit is not OPEN (i.e., HALF_OPEN or CLOSED)
            if self._state != CircuitState.OPEN and self.fallback:
                return await self._execute_fallback(*args, **kwargs)
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self._total_successes += 1
            self.metrics.total_successes = self._total_successes
            self.metrics.last_success_time = time.time()

            # Reset failure count on any successful call
            self._failure_count = 0
            self.metrics.failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(f"🔌 Circuit '{self.name}' CLOSED (recovered)")
                    old_state = self._state
                    self._state = CircuitState.CLOSED
                    self._success_count = 0

                    # Record state change in Prometheus
                    if PROMETHEUS_AVAILABLE:
                        CIRCUIT_STATE_GAUGE.labels(circuit_name=self.name).set(0)
                        CIRCUIT_STATE_CHANGES_TOTAL.labels(
                            circuit_name=self.name,
                            from_state=old_state.value,
                            to_state=self._state.value,
                        ).inc()

            self.metrics.state = self._state
            self.metrics.success_count = self._success_count

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self._total_failures += 1
            self.metrics.total_failures = self._total_failures
            self.metrics.last_failure_time = time.time()

            self._failure_count += 1
            old_state = self._state

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open, go back to open
                logger.warning(f"🔌 Circuit '{self.name}' OPEN (recovery failed)")
                self._state = CircuitState.OPEN
                self._last_failure_time = time.time()
            elif self._failure_count >= self.failure_threshold:
                # Too many failures, open circuit
                logger.warning(f"🔌 Circuit '{self.name}' OPEN (threshold reached)")
                self._state = CircuitState.OPEN
                self._last_failure_time = time.time()

            # Record state change in Prometheus
            if PROMETHEUS_AVAILABLE and self._state != old_state:
                CIRCUIT_STATE_GAUGE.labels(circuit_name=self.name).set(1)  # OPEN
                CIRCUIT_STATE_CHANGES_TOTAL.labels(
                    circuit_name=self.name,
                    from_state=old_state.value,
                    to_state=self._state.value,
                ).inc()

            self.metrics.state = self._state
            self.metrics.failure_count = self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    async def _execute_fallback(self, *args, **kwargs) -> T:
        """Execute fallback function."""
        if self.fallback:
            logger.info(f"🔌 Circuit '{self.name}' executing fallback")
            return await self.fallback(*args, **kwargs)
        raise CircuitBreakerOpen(f"No fallback for circuit '{self.name}'")

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return {"name": self.name, **self.metrics.to_dict()}

    async def reset(self):
        """Manually reset circuit breaker to CLOSED."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self.metrics.state = CircuitState.CLOSED
            self.metrics.failure_count = 0
            self.metrics.success_count = 0
            logger.info(f"🔌 Circuit '{self.name}' manually reset to CLOSED")


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    pass


# Global circuit breakers registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get circuit breaker by name."""
    return _circuit_breakers.get(name)


def create_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Optional[Callable[..., T]] = None,
) -> CircuitBreaker:
    """Create and register a circuit breaker."""
    if name in _circuit_breakers:
        return _circuit_breakers[name]

    cb = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        fallback=fallback,
    )
    _circuit_breakers[name] = cb
    return cb


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Optional[Callable[..., T]] = None,
):
    """
    Decorator for circuit breaker pattern.

    Usage:
        @circuit_breaker("stripe_api", failure_threshold=3)
        async def call_stripe_api(data: dict):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cb = create_circuit_breaker(name, failure_threshold, recovery_timeout, fallback)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await cb.call(func, *args, **kwargs)

        # Expose circuit breaker on function
        wrapper.circuit_breaker = cb

        return wrapper

    return decorator


# Pre-configured circuit breakers for common services
stripe_circuit = create_circuit_breaker(
    name="stripe_api", failure_threshold=3, recovery_timeout=30.0
)

vpn_provisioning_circuit = create_circuit_breaker(
    name="vpn_provisioning", failure_threshold=5, recovery_timeout=60.0
)

auth_provider_circuit = create_circuit_breaker(
    name="auth_provider", failure_threshold=3, recovery_timeout=30.0
)
