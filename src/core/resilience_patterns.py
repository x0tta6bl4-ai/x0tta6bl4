"""Resilience patterns — async stub matching test expectations."""

from __future__ import annotations

import asyncio
import random
import time
from enum import Enum, auto
from typing import Any, Callable


class CircuitBreakerState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


CircuitState = CircuitBreakerState


class CircuitBreaker:
    """Circuit breaker pattern."""

    def __init__(self, name: str = "", failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @state.setter
    def state(self, value: CircuitBreakerState) -> None:
        self._state = value

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @failure_count.setter
    def failure_count(self, value: int) -> None:
        self._failure_count = value

    @property
    def last_failure_time(self) -> float:
        return self._last_failure_time

    @last_failure_time.setter
    def last_failure_time(self, value: float) -> None:
        self._last_failure_time = value

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call a function through the circuit breaker (async)."""
        if self._state == CircuitBreakerState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count = 0
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
            raise

    def reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0


class Bulkhead:
    """Bulkhead pattern with concurrency limiting."""
    def __init__(self, name: str = "", max_concurrent_calls: int = 10):
        self.name = name
        self.max_concurrent_calls = max_concurrent_calls
        self._semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call a function under the bulkhead semaphore."""
        async with self._semaphore:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            return fn(*args, **kwargs)


class RetryWithBackoff:
    """Retry pattern stub."""
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay


class Timeout:
    """Timeout pattern stub."""
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout


async def retry_with_jitter(
    fn: Callable,
    max_retries: int = 3,
    base_delay: float | None = None,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
) -> Any:
    """Retry a function with exponential backoff and jitter (async)."""
    delay_base = base_delay if base_delay is not None else initial_delay
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn()
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries - 1:
                raise
            delay = min(delay_base * (backoff**attempt) / 2, max_delay)
            delay += jitter * delay * random.random()
            await asyncio.sleep(max(0.0, delay))
