import asyncio
import logging
import time
import random
from enum import Enum
from typing import Callable, Any, Dict, Optional, TypeVar, Generic
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class ResiliencePattern:
    """Base class for resilience patterns."""
    pass

class CircuitBreaker(ResiliencePattern):
    """
    Implements the Circuit Breaker pattern to prevent cascading failures.
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit Breaker moving to HALF_OPEN")
            else:
                raise Exception("Circuit Breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit Breaker CLOSED")
            elif self.state == CircuitState.CLOSED and self.failure_count > 0:
                # Successful calls in CLOSED state clear prior transient failures.
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit Breaker OPEN after {self.failure_count} failures")
            raise e

class Bulkhead(ResiliencePattern):
    """
    Implements the Bulkhead pattern to isolate failures within components.
    """
    def __init__(self, max_concurrent_calls: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent_calls)

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        async with self.semaphore:
            return await func(*args, **kwargs)

async def retry_with_jitter(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    *args,
    **kwargs
) -> T:
    """
    Retry a function call with exponential backoff and jitter.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            # Apply jitter: delay = base_delay * (0.5 to 1.5)
            sleep_time = delay * (0.5 + random.random())
            sleep_time = min(sleep_time, max_delay)
            
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)
            delay *= 2  # Exponential backoff
