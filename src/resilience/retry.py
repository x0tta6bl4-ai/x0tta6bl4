"""
Enhanced Retry Pattern Implementation
=====================================

Retry patterns with exponential backoff, jitter, and configurable policies.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class JitterType(Enum):
    """Types of jitter for retry delays."""
    NONE = "none"
    FULL = "full"  # Random between 0 and delay
    EQUAL = "equal"  # Random between delay/2 and delay
    DECORRELATED = "decorrelated"  # AWS-style decorrelated jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay_ms: float = 100.0
    max_delay_ms: float = 60000.0  # 1 minute max
    exponential_base: float = 2.0
    
    # Jitter configuration
    jitter_type: JitterType = JitterType.FULL
    jitter_factor: float = 0.5  # For equal jitter
    
    # Retry conditions
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
    
    # Retry on specific status codes (for HTTP)
    retryable_status_codes: Set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )
    
    # Callbacks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_success: Optional[Callable[[int, float], None]] = None
    on_failure: Optional[Callable[[Exception], None]] = None


class ExponentialBackoff:
    """
    Exponential backoff with jitter calculator.
    
    Implements various backoff strategies:
    - Simple exponential
    - Full jitter
    - Equal jitter
    - Decorrelated jitter (AWS-style)
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._last_delay: Optional[float] = None
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in milliseconds
        """
        # Calculate base exponential delay
        base_delay = self.config.base_delay_ms * (
            self.config.exponential_base ** attempt
        )
        
        # Cap at max delay
        base_delay = min(base_delay, self.config.max_delay_ms)
        
        # Apply jitter
        jittered_delay = self._apply_jitter(base_delay)
        
        # Store for decorrelated jitter
        self._last_delay = jittered_delay
        
        return jittered_delay
    
    def _apply_jitter(self, delay: float) -> float:
        """Apply jitter to delay based on configuration."""
        jitter_type = self.config.jitter_type
        
        if jitter_type == JitterType.NONE:
            return delay
        
        elif jitter_type == JitterType.FULL:
            # Random between 0 and delay
            return random.uniform(0, delay)
        
        elif jitter_type == JitterType.EQUAL:
            # Random between delay/2 and delay
            min_delay = delay * (1 - self.config.jitter_factor)
            return random.uniform(min_delay, delay)
        
        elif jitter_type == JitterType.DECORRELATED:
            # AWS-style: sleep = min(cap, random_between(base, sleep * 3))
            if self._last_delay is None:
                return delay
            return min(
                self.config.max_delay_ms,
                random.uniform(self.config.base_delay_ms, self._last_delay * 3),
            )
        
        return delay
    
    def reset(self) -> None:
        """Reset backoff state."""
        self._last_delay = None


class RetryPolicy:
    """
    Comprehensive retry policy with configurable behavior.
    
    Features:
    - Exponential backoff with jitter
    - Configurable retry conditions
    - Retry budgets
    - Circuit breaker integration
    - Async support
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.backoff = ExponentialBackoff(self.config)
        
        # Statistics
        self._stats = {
            "total_attempts": 0,
            "total_retries": 0,
            "successful_retries": 0,
            "failed_after_retries": 0,
            "total_delay_ms": 0.0,
        }
    
    def _should_retry(
        self,
        exception: Exception,
        attempt: int,
    ) -> bool:
        """Determine if operation should be retried."""
        # Check max retries
        if attempt >= self.config.max_retries:
            return False
        
        # Check non-retryable exceptions
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # Check retryable exceptions
        if isinstance(exception, self.config.retryable_exceptions):
            return True
        
        return False
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with retry policy.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: Last exception after all retries exhausted
        """
        self.backoff.reset()
        last_exception: Optional[Exception] = None
        start_time = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            self._stats["total_attempts"] += 1
            
            try:
                result = func(*args, **kwargs)
                
                # Success
                if attempt > 0:
                    self._stats["successful_retries"] += 1
                
                if self.config.on_success:
                    self.config.on_success(attempt, time.time() - start_time)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    raise
                
                # Calculate delay
                delay_ms = self.backoff.calculate_delay(attempt)
                self._stats["total_delay_ms"] += delay_ms
                self._stats["total_retries"] += 1
                
                # Callback
                if self.config.on_retry:
                    self.config.on_retry(attempt, e, delay_ms)
                
                logger.debug(
                    f"Retry {attempt + 1}/{self.config.max_retries} "
                    f"after {delay_ms:.0f}ms due to: {e}"
                )
                
                # Wait before retry
                time.sleep(delay_ms / 1000.0)
        
        # All retries exhausted
        self._stats["failed_after_retries"] += 1
        
        if self.config.on_failure and last_exception:
            self.config.on_failure(last_exception)
        
        raise last_exception
    
    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute async function with retry policy.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        self.backoff.reset()
        last_exception: Optional[Exception] = None
        start_time = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            self._stats["total_attempts"] += 1
            
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self._stats["successful_retries"] += 1
                
                if self.config.on_success:
                    self.config.on_success(attempt, time.time() - start_time)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e, attempt):
                    raise
                
                delay_ms = self.backoff.calculate_delay(attempt)
                self._stats["total_delay_ms"] += delay_ms
                self._stats["total_retries"] += 1
                
                if self.config.on_retry:
                    self.config.on_retry(attempt, e, delay_ms)
                
                logger.debug(
                    f"Async retry {attempt + 1}/{self.config.max_retries} "
                    f"after {delay_ms:.0f}ms due to: {e}"
                )
                
                await asyncio.sleep(delay_ms / 1000.0)
        
        self._stats["failed_after_retries"] += 1
        
        if self.config.on_failure and last_exception:
            self.config.on_failure(last_exception)
        
        raise last_exception
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        return {
            **self._stats,
            "retry_rate": (
                self._stats["total_retries"] / self._stats["total_attempts"]
                if self._stats["total_attempts"] > 0 else 0
            ),
            "success_rate": (
                self._stats["successful_retries"] / self._stats["total_retries"]
                if self._stats["total_retries"] > 0 else 1.0
            ),
        }
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_attempts": 0,
            "total_retries": 0,
            "successful_retries": 0,
            "failed_after_retries": 0,
            "total_delay_ms": 0.0,
        }


def retry(
    max_retries: int = 3,
    base_delay_ms: float = 100.0,
    jitter_type: JitterType = JitterType.FULL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for adding retry behavior to functions.
    
    Args:
        max_retries: Maximum number of retries
        base_delay_ms: Base delay in milliseconds
        jitter_type: Type of jitter to apply
        retryable_exceptions: Exceptions that trigger retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = RetryConfig(
            max_retries=max_retries,
            base_delay_ms=base_delay_ms,
            jitter_type=jitter_type,
            retryable_exceptions=retryable_exceptions,
        )
        policy = RetryPolicy(config)
        
        def wrapper(*args, **kwargs):
            return policy.execute(func, *args, **kwargs)
        
        async def async_wrapper(*args, **kwargs):
            return await policy.execute_async(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    
    return decorator


__all__ = [
    "JitterType",
    "RetryConfig",
    "ExponentialBackoff",
    "RetryPolicy",
    "retry",
]
