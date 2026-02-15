"""
Connection retry logic with exponential backoff.

Provides resilient network connections with:
- Exponential backoff
- Circuit breaker integration
- Jitter to prevent thundering herd
- Configurable retry policies
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from functools import wraps
from typing import Callable, List, Optional, Type, TypeVar

from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_max: float = 0.5
    retryable_exceptions: tuple = (Exception,)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt with exponential backoff."""
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add random jitter to prevent thundering herd
            jitter_amount = random.uniform(0, self.jitter_max)
            delay += jitter_amount

        return delay


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


async def with_retry(
    func: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    **kwargs,
) -> T:
    """
    Execute a function with retry logic.

    Args:
        func: Async function to execute
        args: Positional arguments for func
        policy: RetryPolicy configuration
        circuit_breaker: Optional circuit breaker for protection
        kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        RetryExhausted: If all retries fail
        CircuitBreakerOpen: If circuit breaker is open
    """
    if policy is None:
        policy = RetryPolicy()

    last_exception = None

    for attempt in range(policy.max_retries + 1):
        try:
            # Check circuit breaker if provided
            if circuit_breaker:
                return await circuit_breaker.call(func, *args, **kwargs)
            else:
                return await func(*args, **kwargs)

        except CircuitBreakerOpen:
            # Don't retry if circuit is open
            raise

        except policy.retryable_exceptions as e:
            last_exception = e

            if attempt < policy.max_retries:
                delay = policy.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{policy.max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {policy.max_retries + 1} attempts failed")
                break

    raise RetryExhausted(
        f"Function failed after {policy.max_retries + 1} attempts",
        last_exception=last_exception,
    )


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (Exception,),
    circuit_breaker_name: Optional[str] = None,
):
    """
    Decorator for adding retry logic to async functions.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exceptions to retry on
        circuit_breaker_name: Optional name of circuit breaker to use

    Example:
        @retry(max_retries=5, base_delay=2.0)
        async def fetch_data():
            return await http_client.get('/api/data')
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions,
        )

        cb = None
        if circuit_breaker_name:
            from src.core.circuit_breaker import (create_circuit_breaker,
                                                  get_circuit_breaker)

            cb = get_circuit_breaker(circuit_breaker_name)
            if cb is None:
                cb = create_circuit_breaker(circuit_breaker_name)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await with_retry(
                func, *args, policy=policy, circuit_breaker=cb, **kwargs
            )

        return wrapper

    return decorator


class ConnectionPool:
    """Managed connection pool with retry logic."""

    def __init__(
        self,
        factory: Callable[..., T],
        max_size: int = 10,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.factory = factory
        self.max_size = max_size
        self.retry_policy = retry_policy or RetryPolicy()
        self._pool: List[T] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> T:
        """Acquire a connection from the pool."""
        async with self._lock:
            if self._pool:
                return self._pool.pop()

        # Create new connection with retry
        return await with_retry(self.factory, policy=self.retry_policy)

    async def release(self, connection: T) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            if len(self._pool) < self.max_size:
                self._pool.append(connection)

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for conn in self._pool:
                if hasattr(conn, "close"):
                    await conn.close()
            self._pool.clear()


# Pre-configured retry policies

# For idempotent operations (safe to retry)
IDEMPOTENT_RETRY_POLICY = RetryPolicy(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

# For network operations
NETWORK_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

# For database operations
DATABASE_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

# For external API calls
API_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)
