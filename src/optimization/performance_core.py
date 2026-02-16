"""
Performance Optimization Core

Caching strategies, quantization, and concurrency improvements
for x0tta6bl4 v3.4.0 → v3.5.0
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheStats:
    """Cache statistics"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    items_cached: int = 0
    hit_rate: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def update(self) -> None:
        """Update hit rate"""
        total = self.hits + self.misses
        self.hit_rate = self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        self.update()
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate_percent": self.hit_rate * 100,
            "items_cached": self.items_cached,
            "total_size_mb": self.total_size_bytes / (1024 * 1024),
        }


class LRUCache:
    """Least-Recently-Used cache with configurable size"""

    def __init__(self, max_size: int = 1000, ttl_seconds: Optional[int] = None):
        """
        Initialize LRU cache

        Args:
            max_size: Maximum number of items
            ttl_seconds: Time-to-live for cached items (None = infinite)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.stats = CacheStats()

    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments"""
        key_str = f"{args}:{sorted(kwargs.items())}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _is_expired(self, timestamp: float) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (time.time() - timestamp) > self.ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            self.stats.misses += 1
            return None

        value, timestamp = self.cache[key]

        if self._is_expired(timestamp):
            del self.cache[key]
            self.stats.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.stats.hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        # If key exists, remove it
        if key in self.cache:
            del self.cache[key]

        # Add new entry
        self.cache[key] = (value, time.time())
        self.cache.move_to_end(key)

        # Evict if over size
        while len(self.cache) > self.max_size:
            evicted_key, _ = self.cache.popitem(last=False)
            self.stats.evictions += 1
            logger.debug(f"Evicted cache entry: {evicted_key}")

        # Update stats
        self.stats.items_cached = len(self.cache)
        self.stats.total_size_bytes = sum(
            len(str(v).encode()) for v, _ in self.cache.values()
        )

    def clear(self) -> None:
        """Clear cache"""
        self.cache.clear()
        self.stats.items_cached = 0
        self.stats.total_size_bytes = 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        self.stats.update()
        return self.stats


class AsyncCache:
    """Async-aware cache with rate limiting"""

    def __init__(self, max_size: int = 1000):
        """Initialize async cache"""
        self.lru = LRUCache(max_size=max_size, ttl_seconds=3600)
        self.locks: Dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value asynchronously"""
        return self.lru.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Set value asynchronously"""
        self.lru.set(key, value)

    async def get_or_compute(
        self, key: str, compute_fn: Callable, *args, **kwargs
    ) -> Any:
        """
        Get from cache or compute asynchronously

        Prevents thundering herd by using locks
        """
        # Check cache
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Acquire lock for this key
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

        async with self.locks[key]:
            # Double-check cache
            cached = await self.get(key)
            if cached is not None:
                return cached

            # Compute value
            if asyncio.iscoroutinefunction(compute_fn):
                value = await compute_fn(*args, **kwargs)
            else:
                value = compute_fn(*args, **kwargs)

            # Store in cache
            await self.set(key, value)
            return value


class RateLimiter:
    """Token-bucket rate limiter"""

    def __init__(self, rate: float, burst: int):
        """
        Initialize rate limiter

        Args:
            rate: Tokens per second
            burst: Maximum burst size
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens (wait if necessary)

        Returns:
            Wait time in seconds
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Replenish tokens
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Wait if necessary
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                self.tokens = 0
                return wait_time

            self.tokens -= tokens
            return 0.0

    async def wait_if_needed(self, tokens: int = 1) -> None:
        """Wait if rate limit exceeded"""
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)


class PerformanceOptimizer:
    """Performance optimization manager"""

    def __init__(self):
        """Initialize optimizer"""
        self.ml_cache = AsyncCache(max_size=5000)
        self.rag_cache = AsyncCache(max_size=10000)
        self.pqc_cache = AsyncCache(max_size=2000)

        # Rate limiters for expensive operations
        self.ml_limiter = RateLimiter(rate=100.0, burst=500)  # 100 ops/sec
        self.rag_limiter = RateLimiter(rate=50.0, burst=200)  # 50 queries/sec
        self.pqc_limiter = RateLimiter(rate=30.0, burst=100)  # 30 ops/sec

    async def cached_ml_operation(
        self, operation_name: str, compute_fn: Callable, *args, **kwargs
    ) -> Any:
        """
        Execute ML operation with caching

        Args:
            operation_name: Name of operation for key generation
            compute_fn: Async function to execute
            *args, **kwargs: Arguments to pass

        Returns:
            Operation result
        """
        # Rate limit
        await self.ml_limiter.wait_if_needed()

        # Generate cache key
        cache_key = f"ml:{operation_name}:{hash((args, frozenset(kwargs.items())))}"

        # Get or compute
        return await self.ml_cache.get_or_compute(
            cache_key, compute_fn, *args, **kwargs
        )

    async def cached_rag_retrieval(
        self, query: str, retrieve_fn: Callable, k: int = 5
    ) -> Any:
        """
        Cached RAG retrieval

        Args:
            query: Search query
            retrieve_fn: Async retrieval function
            k: Number of results

        Returns:
            Retrieval results
        """
        # Rate limit
        await self.rag_limiter.wait_if_needed()

        # Generate cache key
        cache_key = f"rag:{query}:k{k}"

        # Get or compute
        return await self.rag_cache.get_or_compute(cache_key, retrieve_fn, query, k=k)

    async def cached_pqc_operation(
        self, operation_type: str, compute_fn: Callable, *args, **kwargs
    ) -> Any:
        """
        Cached PQC operation

        Args:
            operation_type: Type of PQC operation
            compute_fn: Async function to execute

        Returns:
            Operation result
        """
        # Rate limit
        await self.pqc_limiter.wait_if_needed()

        # Generate cache key (don't cache sensitive operations like signing)
        if operation_type in ["keygen", "verify"]:
            # Cache verification results
            cache_key = (
                f"pqc:{operation_type}:{hash((args, frozenset(kwargs.items())))}"
            )
            return await self.pqc_cache.get_or_compute(
                cache_key, compute_fn, *args, **kwargs
            )
        else:
            # Don't cache signing operations
            if asyncio.iscoroutinefunction(compute_fn):
                return await compute_fn(*args, **kwargs)
            else:
                return compute_fn(*args, **kwargs)

    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report"""
        return {
            "ml_cache": self.ml_cache.lru.get_stats().to_dict(),
            "rag_cache": self.rag_cache.lru.get_stats().to_dict(),
            "pqc_cache": self.pqc_cache.lru.get_stats().to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass
class QuantizationConfig:
    """Quantization configuration"""

    bit_width: int = 8  # 8-bit, 16-bit, etc.
    use_symmetric: bool = True  # Symmetric vs asymmetric
    quantize_weights: bool = True
    quantize_activations: bool = False
    clipping_value: float = 2.0


class LoRAQuantizer:
    """LoRA quantization for memory efficiency"""

    def __init__(self, config: QuantizationConfig = None):
        """
        Initialize quantizer

        Args:
            config: Quantization configuration
        """
        self.config = config or QuantizationConfig()

    def quantize_weights(self, weights: Any) -> Dict[str, Any]:
        """
        Quantize LoRA weights

        Args:
            weights: Weight matrix

        Returns:
            Quantized weights metadata
        """
        try:
            import numpy as np

            # Convert to numpy if needed
            if hasattr(weights, "numpy"):
                w = weights.numpy()
            else:
                w = np.array(weights)

            # Calculate quantization parameters
            w_min = np.min(w)
            w_max = np.max(w)
            w_scale = (w_max - w_min) / (2**self.config.bit_width - 1)
            w_zero_point = -w_min / w_scale if not self.config.use_symmetric else 0

            # Quantize
            w_quantized = np.round((w - w_min) / w_scale).astype(np.uint8)

            # Calculate memory savings
            original_bytes = w.nbytes
            quantized_bytes = w_quantized.nbytes
            compression_ratio = original_bytes / quantized_bytes

            return {
                "quantized": True,
                "bit_width": self.config.bit_width,
                "scale": float(w_scale),
                "zero_point": float(w_zero_point),
                "original_size_bytes": int(original_bytes),
                "quantized_size_bytes": int(quantized_bytes),
                "compression_ratio": float(compression_ratio),
                "memory_saved_percent": float(
                    (1 - quantized_bytes / original_bytes) * 100
                ),
            }

        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return {"quantized": False, "error": str(e)}

    def estimate_speedup(self) -> Dict[str, float]:
        """Estimate performance speedup from quantization"""
        # Typical speedups from quantization
        base_speedup = {
            8: 2.0,  # 8-bit: ~2x speedup
            16: 1.5,  # 16-bit: ~1.5x speedup
            32: 1.0,  # 32-bit: baseline
        }

        speedup = base_speedup.get(self.config.bit_width, 1.0)

        # Additional speedup if quantizing activations
        if self.config.quantize_activations:
            speedup *= 1.2

        return {
            "estimated_speedup": speedup,
            "bit_width": self.config.bit_width,
            "estimated_latency_reduction_percent": (1 - 1 / speedup) * 100,
        }


class ConcurrencyOptimizer:
    """Concurrency optimization for async operations"""

    def __init__(self, max_concurrent: int = 10):
        """
        Initialize concurrency optimizer

        Args:
            max_concurrent: Maximum concurrent operations
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def run_concurrent(
        self, tasks: List[Any], timeout: Optional[float] = None
    ) -> List[Any]:
        """
        Run tasks concurrently with semaphore

        Args:
            tasks: List of coroutines
            timeout: Operation timeout

        Returns:
            Results from all tasks
        """

        async def wrapped_task(task):
            async with self.semaphore:
                try:
                    if timeout:
                        return await asyncio.wait_for(task, timeout=timeout)
                    else:
                        return await task
                except asyncio.TimeoutError:
                    logger.error(f"Task timeout after {timeout}s")
                    return None

        return await asyncio.gather(
            *[wrapped_task(task) for task in tasks], return_exceptions=True
        )


# Global instance
_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get or create performance optimizer"""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer


async def test_performance_optimization() -> Dict[str, Any]:
    """Test performance optimization"""
    optimizer = get_performance_optimizer()

    # Simulate some cache hits
    async def dummy_compute(x):
        await asyncio.sleep(0.01)
        return x * 2

    # Run operations
    for i in range(100):
        await optimizer.cached_ml_operation(
            "test_op", dummy_compute, i % 10  # Only 10 unique values
        )

    return {
        "status": "success",
        "performance": optimizer.get_performance_report(),
    }
