"""
Timeout Pattern Implementation
==============================

Timeout patterns with cascade protection for distributed systems.
Prevents resource exhaustion and cascading failures.
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import TimeoutError as ConcurrentTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Custom timeout exception."""
    def __init__(self, message: str, timeout_seconds: float, operation: str = ""):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class CascadeTimeout(Exception):
    """Exception for cascading timeout failures."""
    def __init__(self, message: str, cascade_chain: List[str]):
        super().__init__(message)
        self.cascade_chain = cascade_chain


@dataclass
class TimeoutConfig:
    """Configuration for timeout pattern."""
    default_timeout: float = 30.0
    connection_timeout: float = 10.0
    read_timeout: float = 30.0
    write_timeout: float = 30.0
    
    # Cascade protection
    max_cascade_depth: int = 5
    cascade_timeout_multiplier: float = 0.8  # Each level gets 80% of parent
    
    # Retry on timeout
    retry_on_timeout: bool = False
    max_timeout_retries: int = 1
    
    # Graceful degradation
    fallback_value: Optional[Any] = None
    fallback_on_timeout: bool = False


class TimeoutPattern:
    """
    Timeout pattern with cascade protection.
    
    Features:
    - Configurable timeouts for different operations
    - Cascade protection (nested timeouts)
    - Async and sync support
    - Fallback values
    """
    
    def __init__(self, config: Optional[TimeoutConfig] = None):
        self.config = config or TimeoutConfig()
        self._timeout_stats: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cascade_depth = threading.local()
    
    def _get_cascade_depth(self) -> int:
        """Get current cascade depth for this thread."""
        return getattr(self._cascade_depth, 'depth', 0)
    
    def _set_cascade_depth(self, depth: int) -> None:
        """Set cascade depth for this thread."""
        self._cascade_depth.depth = depth
    
    def _calculate_timeout(self, base_timeout: float) -> float:
        """Calculate timeout with cascade protection."""
        depth = self._get_cascade_depth()
        
        if depth >= self.config.max_cascade_depth:
            raise CascadeTimeout(
                f"Maximum cascade depth ({self.config.max_cascade_depth}) exceeded",
                cascade_chain=[f"depth_{depth}"],
            )
        
        # Apply cascade multiplier
        timeout = base_timeout * (
            self.config.cascade_timeout_multiplier ** depth
        )
        
        return max(timeout, 1.0)  # Minimum 1 second
    
    def _record_timeout(self, operation: str, timeout_seconds: float) -> None:
        """Record timeout statistics."""
        with self._lock:
            if operation not in self._timeout_stats:
                self._timeout_stats[operation] = {
                    "total_calls": 0,
                    "timeouts": 0,
                    "total_time": 0.0,
                }
            self._timeout_stats[operation]["timeouts"] += 1
    
    def _record_success(
        self,
        operation: str,
        elapsed_seconds: float
    ) -> None:
        """Record successful execution."""
        with self._lock:
            if operation not in self._timeout_stats:
                self._timeout_stats[operation] = {
                    "total_calls": 0,
                    "timeouts": 0,
                    "total_time": 0.0,
                }
            self._timeout_stats[operation]["total_calls"] += 1
            self._timeout_stats[operation]["total_time"] += elapsed_seconds
    
    def execute(
        self,
        func: Callable[..., T],
        timeout: Optional[float] = None,
        operation: str = "",
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with timeout.
        
        Args:
            func: Function to execute
            timeout: Timeout in seconds (uses default if not specified)
            operation: Operation name for logging
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            TimeoutError: If execution times out
        """
        base_timeout = timeout or self.config.default_timeout
        calculated_timeout = self._calculate_timeout(base_timeout)
        
        # Increment cascade depth
        self._set_cascade_depth(self._get_cascade_depth() + 1)
        
        start_time = time.time()
        
        try:
            # Use threading for sync timeout
            result = self._execute_with_timeout(
                func,
                calculated_timeout,
                *args,
                **kwargs
            )
            
            elapsed = time.time() - start_time
            self._record_success(operation, elapsed)
            
            return result
            
        except (TimeoutError, ConcurrentTimeoutError) as e:
            self._record_timeout(operation, calculated_timeout)
            
            if self.config.fallback_on_timeout and self.config.fallback_value is not None:
                logger.warning(
                    f"Timeout for {operation}, using fallback: {calculated_timeout:.2f}s"
                )
                return self.config.fallback_value
            
            raise TimeoutError(
                f"Operation '{operation}' timed out after {calculated_timeout:.2f}s",
                calculated_timeout,
                operation,
            )
        finally:
            # Decrement cascade depth
            self._set_cascade_depth(self._get_cascade_depth() - 1)
    
    def _execute_with_timeout(
        self,
        func: Callable[..., T],
        timeout: float,
        *args,
        **kwargs
    ) -> T:
        """Execute function with threading timeout."""
        result_container: Dict[str, Any] = {}
        exception_container: Dict[str, Exception] = {}
        
        def wrapper():
            try:
                result_container['result'] = func(*args, **kwargs)
            except Exception as e:
                exception_container['exception'] = e
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # Thread is still running - timeout occurred
            raise TimeoutError("Thread timeout", timeout)
        
        if 'exception' in exception_container:
            raise exception_container['exception']
        
        return result_container.get('result')
    
    async def execute_async(
        self,
        func: Callable[..., T],
        timeout: Optional[float] = None,
        operation: str = "",
        *args,
        **kwargs
    ) -> T:
        """
        Execute async function with timeout.
        
        Args:
            func: Async function to execute
            timeout: Timeout in seconds
            operation: Operation name for logging
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        base_timeout = timeout or self.config.default_timeout
        calculated_timeout = self._calculate_timeout(base_timeout)
        
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=calculated_timeout,
            )
            
            elapsed = time.time() - start_time
            self._record_success(operation, elapsed)
            
            return result
            
        except asyncio.TimeoutError:
            self._record_timeout(operation, calculated_timeout)
            
            if self.config.fallback_on_timeout and self.config.fallback_value is not None:
                return self.config.fallback_value
            
            raise TimeoutError(
                f"Async operation '{operation}' timed out after {calculated_timeout:.2f}s",
                calculated_timeout,
                operation,
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timeout statistics."""
        with self._lock:
            stats = {}
            for op, data in self._timeout_stats.items():
                total = data["total_calls"] + data["timeouts"]
                avg_time = (
                    data["total_time"] / data["total_calls"]
                    if data["total_calls"] > 0 else 0
                )
                stats[op] = {
                    "total_calls": total,
                    "timeouts": data["timeouts"],
                    "timeout_rate": data["timeouts"] / total if total > 0 else 0,
                    "avg_time": avg_time,
                }
            return stats


class TimeoutContext:
    """Context manager for timeout."""
    
    def __init__(
        self,
        timeout: float,
        operation: str = "",
        on_timeout: Optional[Callable[[], None]] = None,
    ):
        self.timeout = timeout
        self.operation = operation
        self.on_timeout = on_timeout
        self.start_time: Optional[float] = None
        self.elapsed: float = 0.0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time if self.start_time else 0
        
        if self.elapsed > self.timeout:
            if self.on_timeout:
                self.on_timeout()
        
        return False
    
    @property
    def remaining(self) -> float:
        """Get remaining time before timeout."""
        if self.start_time is None:
            return self.timeout
        elapsed = time.time() - self.start_time
        return max(0, self.timeout - elapsed)
    
    @property
    def is_expired(self) -> bool:
        """Check if timeout has expired."""
        return self.remaining <= 0


__all__ = [
    "TimeoutError",
    "CascadeTimeout",
    "TimeoutConfig",
    "TimeoutPattern",
    "TimeoutContext",
]
