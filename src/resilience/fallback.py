"""
Advanced Fallback Patterns
==========================

Graceful degradation patterns for resilient systems:
- Chain Fallback: Multiple fallback options in priority order
- Cache Fallback: Return cached data on failure
- Default Fallback: Return safe default values
- Circuit Fallback: Integrate with circuit breaker
- Async Fallback: Asynchronous fallback execution
"""

import asyncio
import functools
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
    Awaitable,
    Protocol,
    runtime_checkable
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class FallbackType(Enum):
    """Types of fallback strategies."""
    DEFAULT = "default"
    CACHE = "cache"
    CHAIN = "chain"
    CIRCUIT = "circuit"
    ASYNC = "async"


@dataclass
class FallbackResult(Generic[T]):
    """Result of a fallback operation."""
    value: T
    from_fallback: bool
    fallback_name: Optional[str] = None
    original_error: Optional[Exception] = None
    execution_time_ms: float = 0.0
    cache_hit: bool = False


@dataclass
class FallbackConfig:
    """Configuration for fallback patterns."""
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    log_fallbacks: bool = True
    metrics_enabled: bool = True
    async_timeout_ms: int = 5000


@dataclass
class FallbackMetrics:
    """Metrics for fallback operations."""
    total_calls: int = 0
    primary_successes: int = 0
    primary_failures: int = 0
    fallback_successes: int = 0
    fallback_failures: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_fallback_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "primary_successes": self.primary_successes,
            "primary_failures": self.primary_failures,
            "fallback_successes": self.fallback_successes,
            "fallback_failures": self.fallback_failures,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "avg_fallback_time_ms": (
                self.total_fallback_time_ms / self.fallback_successes
                if self.fallback_successes > 0 else 0
            ),
            "primary_success_rate": (
                self.primary_successes / self.total_calls
                if self.total_calls > 0 else 1.0
            ),
            "fallback_rate": (
                self.fallback_successes / self.total_calls
                if self.total_calls > 0 else 0
            )
        }


@runtime_checkable
class FallbackHandler(Protocol[T]):
    """Protocol for fallback handlers."""
    
    def handle(self, error: Exception, *args, **kwargs) -> T:
        """Handle the fallback."""
        ...


class DefaultValueFallback(Generic[T]):
    """
    Simple fallback that returns a default value.
    
    Use when you have a safe default that can be returned
    when the primary operation fails.
    """
    
    def __init__(
        self,
        default_value: T,
        name: str = "default_fallback"
    ):
        self.default_value = default_value
        self.name = name
    
    def handle(self, error: Exception, *args, **kwargs) -> T:
        """Return the default value."""
        logger.info(
            f"Fallback '{self.name}' returning default value due to: {error}"
        )
        return self.default_value


class CacheFallback(Generic[T]):
    """
    Fallback that returns cached data on failure.
    
    Maintains a cache of successful results and returns
    cached data when the primary operation fails.
    
    Features:
    - TTL-based cache expiration
    - LRU eviction
    - Cache statistics
    """
    
    def __init__(
        self,
        ttl_seconds: int = 300,
        max_size: int = 1000,
        name: str = "cache_fallback"
    ):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.name = name
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: deque = deque()
        self._lock = threading.Lock()
        
        # Metrics
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "|".join(key_parts)
    
    def _evict_if_needed(self) -> None:
        """Evict old entries if cache is full."""
        while len(self._cache) >= self.max_size and self._access_order:
            oldest_key = self._access_order.popleft()
            if oldest_key in self._cache:
                del self._cache[oldest_key]
    
    def get(self, key: str) -> Optional[T]:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            if datetime.utcnow() > entry["expires_at"]:
                del self._cache[key]
                self._misses += 1
                return None
            
            self._hits += 1
            return entry["value"]
    
    def set(self, key: str, value: T) -> None:
        """Store value in cache."""
        with self._lock:
            self._evict_if_needed()
            
            self._cache[key] = {
                "value": value,
                "expires_at": datetime.utcnow() + timedelta(seconds=self.ttl_seconds),
                "created_at": datetime.utcnow()
            }
            self._access_order.append(key)
    
    def handle(self, error: Exception, *args, **kwargs) -> Optional[T]:
        """Return cached value if available."""
        key = self._make_key(*args, **kwargs)
        cached = self.get(key)
        
        if cached is not None:
            logger.info(
                f"Fallback '{self.name}' returning cached value for key: {key[:50]}"
            )
            return cached
        
        logger.warning(
            f"Fallback '{self.name}' cache miss for key: {key[:50]}"
        )
        raise error  # Re-raise if no cached value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "name": self.name,
                "type": "cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
            }


class ChainFallback(Generic[T]):
    """
    Fallback chain with multiple fallback options.
    
    Tries each fallback in order until one succeeds.
    Useful when you have multiple degradation levels.
    
    Example:
        chain = ChainFallback([
            CacheFallback(),
            DefaultValueFallback({"status": "degraded"}),
            DefaultValueFallback({"status": "unavailable"})
        ])
    """
    
    def __init__(
        self,
        fallbacks: List[Callable[[Exception, ...], T]],
        name: str = "chain_fallback"
    ):
        self.fallbacks = fallbacks
        self.name = name
        
        # Metrics per fallback
        self._fallback_metrics: Dict[int, Dict[str, int]] = {
            i: {"successes": 0, "failures": 0}
            for i in range(len(fallbacks))
        }
        self._lock = threading.Lock()
    
    def handle(self, error: Exception, *args, **kwargs) -> T:
        """Try each fallback in order."""
        last_error = error
        
        for i, fallback in enumerate(self.fallbacks):
            try:
                result = fallback(error, *args, **kwargs)
                
                with self._lock:
                    self._fallback_metrics[i]["successes"] += 1
                
                logger.info(
                    f"Fallback chain '{self.name}' succeeded at index {i}"
                )
                return result
                
            except Exception as e:
                last_error = e
                with self._lock:
                    self._fallback_metrics[i]["failures"] += 1
                
                logger.warning(
                    f"Fallback chain '{self.name}' failed at index {i}: {e}"
                )
        
        # All fallbacks failed
        raise last_error
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chain statistics."""
        with self._lock:
            return {
                "name": self.name,
                "type": "chain",
                "fallback_count": len(self.fallbacks),
                "fallback_metrics": self._fallback_metrics
            }


class CircuitFallback(Generic[T]):
    """
    Fallback integrated with circuit breaker.
    
    When circuit is open, immediately returns fallback value
    without attempting the primary operation.
    
    Features:
    - Fast fail when circuit is open
    - Automatic circuit state management
    - Metrics integration
    """
    
    def __init__(
        self,
        circuit_breaker: Any,  # CircuitBreaker from advanced_patterns
        fallback: Callable[[Exception, ...], T],
        name: str = "circuit_fallback"
    ):
        self.circuit_breaker = circuit_breaker
        self.fallback = fallback
        self.name = name
        
        self._circuit_fallbacks = 0
        self._lock = threading.Lock()
    
    def handle(self, error: Exception, *args, **kwargs) -> T:
        """Handle with circuit breaker awareness."""
        # Check if circuit is open
        if hasattr(self.circuit_breaker, 'is_open') and self.circuit_breaker.is_open():
            with self._lock:
                self._circuit_fallbacks += 1
            
            logger.info(
                f"Fallback '{self.name}' executing due to open circuit"
            )
            return self.fallback(error, *args, **kwargs)
        
        # Circuit is closed, re-raise to let normal flow continue
        raise error
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit fallback statistics."""
        with self._lock:
            return {
                "name": self.name,
                "type": "circuit",
                "circuit_fallbacks": self._circuit_fallbacks,
                "circuit_state": (
                    self.circuit_breaker.get_state()
                    if hasattr(self.circuit_breaker, 'get_state')
                    else "unknown"
                )
            }


class AsyncFallback(Generic[T]):
    """
    Asynchronous fallback execution.
    
    Executes fallback in background while returning
    a quick response. Useful for non-critical operations.
    
    Features:
    - Non-blocking fallback execution
    - Background task management
    - Timeout handling
    """
    
    def __init__(
        self,
        fallback: Callable[..., Awaitable[T]],
        immediate_value: T,
        timeout_ms: int = 5000,
        name: str = "async_fallback"
    ):
        self.fallback = fallback
        self.immediate_value = immediate_value
        self.timeout_ms = timeout_ms
        self.name = name
        
        self._pending_tasks: Dict[str, asyncio.Task] = {}
        self._completed_results: Dict[str, T] = {}
        self._lock = threading.Lock()
        
        # Metrics
        self._immediate_returns = 0
        self._async_completions = 0
        self._async_timeouts = 0
    
    async def execute_async(
        self,
        key: str,
        *args,
        **kwargs
    ) -> T:
        """Execute fallback asynchronously."""
        try:
            result = await asyncio.wait_for(
                self.fallback(*args, **kwargs),
                timeout=self.timeout_ms / 1000.0
            )
            
            with self._lock:
                self._completed_results[key] = result
                self._async_completions += 1
            
            return result
            
        except asyncio.TimeoutError:
            with self._lock:
                self._async_timeouts += 1
            logger.warning(f"Async fallback '{self.name}' timed out for key: {key}")
            raise
    
    def handle(self, error: Exception, *args, **kwargs) -> T:
        """
        Return immediate value and start async fallback.
        
        Note: This is a sync method that starts async work.
        Use execute_async for pure async operation.
        """
        key = f"{time.time()}_{id(error)}"
        
        # Start async fallback in background
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.execute_async(key, *args, **kwargs))
            else:
                loop.run_until_complete(self.execute_async(key, *args, **kwargs))
        except RuntimeError:
            pass  # No event loop available
        
        with self._lock:
            self._immediate_returns += 1
        
        logger.info(
            f"Fallback '{self.name}' returning immediate value, async fallback started"
        )
        return self.immediate_value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get async fallback statistics."""
        with self._lock:
            return {
                "name": self.name,
                "type": "async",
                "immediate_returns": self._immediate_returns,
                "async_completions": self._async_completions,
                "async_timeouts": self._async_timeouts,
                "pending_tasks": len(self._pending_tasks),
                "completed_results": len(self._completed_results)
            }


class FallbackChainBuilder(Generic[T]):
    """
    Builder for creating fallback chains fluently.
    
    Example:
        fallback = (FallbackChainBuilder()
            .with_cache(ttl_seconds=60)
            .with_default({"status": "degraded"})
            .with_retry(max_retries=2)
            .build())
    """
    
    def __init__(self):
        self._fallbacks: List[Callable] = []
        self._name = "custom_chain"
        self._config = FallbackConfig()
    
    def with_name(self, name: str) -> "FallbackChainBuilder[T]":
        """Set the chain name."""
        self._name = name
        return self
    
    def with_config(self, config: FallbackConfig) -> "FallbackChainBuilder[T]":
        """Set configuration."""
        self._config = config
        return self
    
    def with_default(
        self,
        default_value: T
    ) -> "FallbackChainBuilder[T]":
        """Add a default value fallback."""
        self._fallbacks.append(
            DefaultValueFallback(default_value).handle
        )
        return self
    
    def with_cache(
        self,
        ttl_seconds: int = 300,
        max_size: int = 1000
    ) -> "FallbackChainBuilder[T]":
        """Add a cache fallback."""
        self._fallbacks.append(
            CacheFallback(ttl_seconds, max_size).handle
        )
        return self
    
    def with_custom(
        self,
        handler: Callable[[Exception, ...], T]
    ) -> "FallbackChainBuilder[T]":
        """Add a custom fallback handler."""
        self._fallbacks.append(handler)
        return self
    
    def with_circuit(
        self,
        circuit_breaker: Any
    ) -> "FallbackChainBuilder[T]":
        """Add circuit breaker awareness."""
        if self._fallbacks:
            last_fallback = self._fallbacks[-1]
            self._fallbacks[-1] = CircuitFallback(
                circuit_breaker,
                last_fallback
            ).handle
        return self
    
    def build(self) -> ChainFallback[T]:
        """Build the fallback chain."""
        if not self._fallbacks:
            raise ValueError("At least one fallback must be added")
        
        return ChainFallback(self._fallbacks, self._name)


class FallbackExecutor(Generic[T]):
    """
    Executor that wraps operations with fallback handling.
    
    Provides a unified interface for executing operations
    with automatic fallback on failure.
    """
    
    def __init__(
        self,
        fallback: Callable[[Exception, ...], T],
        config: Optional[FallbackConfig] = None
    ):
        self.fallback = fallback
        self.config = config or FallbackConfig()
        self._metrics = FallbackMetrics()
        self._lock = threading.Lock()
        
        # Optional cache for successful results
        self._cache: Optional[CacheFallback[T]] = None
        if self.config.enable_cache:
            self._cache = CacheFallback(
                ttl_seconds=self.config.cache_ttl_seconds,
                max_size=self.config.max_cache_size
            )
    
    def execute(
        self,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> FallbackResult[T]:
        """
        Execute operation with fallback.
        
        Args:
            operation: Primary operation to execute
            *args, **kwargs: Arguments for operation
            
        Returns:
            FallbackResult with value and metadata
        """
        start_time = time.time()
        
        with self._lock:
            self._metrics.total_calls += 1
        
        # Try primary operation
        try:
            result = operation(*args, **kwargs)
            
            with self._lock:
                self._metrics.primary_successes += 1
            
            # Cache successful result
            if self._cache:
                key = str(args) + str(sorted(kwargs.items()))
                self._cache.set(key, result)
            
            return FallbackResult(
                value=result,
                from_fallback=False,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            with self._lock:
                self._metrics.primary_failures += 1
            
            # Try fallback
            try:
                fallback_start = time.time()
                result = self.fallback(e, *args, **kwargs)
                fallback_time = (time.time() - fallback_start) * 1000
                
                with self._lock:
                    self._metrics.fallback_successes += 1
                    self._metrics.total_fallback_time_ms += fallback_time
                
                if self.config.log_fallbacks:
                    logger.info(
                        f"Fallback succeeded after primary failure: {e}"
                    )
                
                return FallbackResult(
                    value=result,
                    from_fallback=True,
                    original_error=e,
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
            except Exception as fallback_error:
                with self._lock:
                    self._metrics.fallback_failures += 1
                
                logger.error(
                    f"Both primary and fallback failed: "
                    f"primary={e}, fallback={fallback_error}"
                )
                raise
    
    async def execute_async(
        self,
        operation: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> FallbackResult[T]:
        """Async version of execute."""
        start_time = time.time()
        
        with self._lock:
            self._metrics.total_calls += 1
        
        try:
            result = await operation(*args, **kwargs)
            
            with self._lock:
                self._metrics.primary_successes += 1
            
            return FallbackResult(
                value=result,
                from_fallback=False,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            with self._lock:
                self._metrics.primary_failures += 1
            
            # Check if fallback is async
            try:
                fallback_start = time.time()
                
                if asyncio.iscoroutinefunction(self.fallback):
                    result = await self.fallback(e, *args, **kwargs)
                else:
                    result = self.fallback(e, *args, **kwargs)
                
                fallback_time = (time.time() - fallback_start) * 1000
                
                with self._lock:
                    self._metrics.fallback_successes += 1
                    self._metrics.total_fallback_time_ms += fallback_time
                
                return FallbackResult(
                    value=result,
                    from_fallback=True,
                    original_error=e,
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
            except Exception as fallback_error:
                with self._lock:
                    self._metrics.fallback_failures += 1
                raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics."""
        with self._lock:
            metrics = self._metrics.to_dict()
            if self._cache:
                metrics["cache"] = self._cache.get_stats()
            return metrics


def with_fallback(
    fallback: Union[T, Callable[[Exception, ...], T]],
    log_fallbacks: bool = True
):
    """
    Decorator for adding fallback to functions.
    
    Args:
        fallback: Either a default value or a callable that takes the exception
        log_fallbacks: Whether to log fallback invocations
        
    Returns:
        Decorated function
        
    Example:
        @with_fallback({"status": "degraded"})
        def get_status():
            return external_api.get_status()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_fallbacks:
                    logger.info(
                        f"Fallback triggered for {func.__name__}: {e}"
                    )
                
                if callable(fallback):
                    return fallback(e, *args, **kwargs)
                else:
                    return fallback
        
        return wrapper
    
    return decorator


def with_fallback_chain(
    *fallbacks: Callable[[Exception, ...], T],
    name: Optional[str] = None
):
    """
    Decorator with multiple fallback options.
    
    Args:
        *fallbacks: Multiple fallback handlers in priority order
        name: Optional name for the chain
        
    Returns:
        Decorated function
        
    Example:
        @with_fallback_chain(
            lambda e: cache.get("key"),
            lambda e: {"default": True}
        )
        def get_data():
            return api.fetch()
    """
    chain = ChainFallback(
        list(fallbacks),
        name or f"chain_{id(fallbacks)}"
    )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return chain.handle(e, *args, **kwargs)
        
        wrapper.fallback_chain = chain
        return wrapper
    
    return decorator


__all__ = [
    "FallbackType",
    "FallbackResult",
    "FallbackConfig",
    "FallbackMetrics",
    "FallbackHandler",
    "DefaultValueFallback",
    "CacheFallback",
    "ChainFallback",
    "CircuitFallback",
    "AsyncFallback",
    "FallbackChainBuilder",
    "FallbackExecutor",
    "with_fallback",
    "with_fallback_chain",
]
