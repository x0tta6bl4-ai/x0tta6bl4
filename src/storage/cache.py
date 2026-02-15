"""
Caching Layer

Provides distributed caching, cache invalidation, cache warming,
and cache metrics.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry"""

    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self):
        """Update access time and count"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class LRUCache:
    """
    LRU (Least Recently Used) cache implementation.

    Provides:
    - Size-limited cache
    - LRU eviction
    - TTL support
    - Access tracking
    """

    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum cache size
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()

        logger.info(f"LRUCache initialized (max_size: {max_size}, ttl: {default_ttl})")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            # Check expiration
            if entry.is_expired():
                del self.cache[key]
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.touch()

            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
            tags: Optional tags for invalidation
        """
        with self.lock:
            # Remove if exists
            if key in self.cache:
                del self.cache[key]

            # Evict if at capacity
            if len(self.cache) >= self.max_size:
                # Remove oldest (first item)
                self.cache.popitem(last=False)

            # Calculate expiration
            expires_at = None
            if ttl is not None:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            elif self.default_ttl is not None:
                expires_at = datetime.utcnow() + timedelta(seconds=self.default_ttl)

            # Create entry
            entry = CacheEntry(
                key=key, value=value, expires_at=expires_at, tags=tags or []
            )

            self.cache[key] = entry

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all entries with a tag.

        Args:
            tag: Tag to invalidate

        Returns:
            Number of entries invalidated
        """
        with self.lock:
            to_delete = [key for key, entry in self.cache.items() if tag in entry.tags]

            for key in to_delete:
                del self.cache[key]

            return len(to_delete)

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_entries = len(self.cache)
            expired_entries = sum(1 for e in self.cache.values() if e.is_expired())
            total_accesses = sum(e.access_count for e in self.cache.values())

            return {
                "size": total_entries,
                "max_size": self.max_size,
                "expired_entries": expired_entries,
                "total_accesses": total_accesses,
                "hit_rate": 0.0,  # Would need to track misses
            }


class DistributedCache:
    """
    Distributed caching layer.

    Provides:
    - Multi-level caching
    - Cache invalidation
    - Cache warming
    - Cache metrics
    """

    def __init__(
        self, local_cache: Optional[LRUCache] = None, enable_distributed: bool = False
    ):
        """
        Initialize distributed cache.

        Args:
            local_cache: Local cache instance
            enable_distributed: Enable distributed caching
        """
        self.local_cache = local_cache or LRUCache(max_size=1000)
        self.enable_distributed = enable_distributed
        self.distributed_backend: Optional[Any] = (
            None  # Would be Redis, Memcached, etc.
        )

        # Metrics
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0

        logger.info("DistributedCache initialized")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache (local first, then distributed).

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        # Try local cache first
        value = self.local_cache.get(key)
        if value is not None:
            self.hits += 1
            return value

        # Try distributed cache
        if self.enable_distributed and self.distributed_backend:
            try:
                value = self.distributed_backend.get(key)
                if value is not None:
                    # Populate local cache
                    self.local_cache.set(key, value)
                    self.hits += 1
                    return value
            except Exception as e:
                logger.warning(f"Distributed cache get failed: {e}")

        self.misses += 1
        return default

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Set value in cache (local and distributed).

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds
            tags: Optional tags
        """
        # Set in local cache
        self.local_cache.set(key, value, ttl=ttl, tags=tags)
        self.sets += 1

        # Set in distributed cache
        if self.enable_distributed and self.distributed_backend:
            try:
                self.distributed_backend.set(key, value, ttl=ttl)
            except Exception as e:
                logger.warning(f"Distributed cache set failed: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        deleted = self.local_cache.delete(key)
        self.deletes += 1

        if self.enable_distributed and self.distributed_backend:
            try:
                self.distributed_backend.delete(key)
            except Exception as e:
                logger.warning(f"Distributed cache delete failed: {e}")

        return deleted

    def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate entries by tag.

        Args:
            tag: Tag to invalidate

        Returns:
            Number of entries invalidated
        """
        count = self.local_cache.invalidate_by_tag(tag)

        if self.enable_distributed and self.distributed_backend:
            try:
                # Would need tag indexing in distributed backend
                pass
            except Exception as e:
                logger.warning(f"Distributed cache tag invalidation failed: {e}")

        return count

    def warm_cache(self, keys_and_values: Dict[str, Any], ttl: Optional[int] = None):
        """
        Warm cache with pre-computed values.

        Args:
            keys_and_values: Dictionary of key-value pairs
            ttl: Optional TTL for all entries
        """
        for key, value in keys_and_values.items():
            self.set(key, value, ttl=ttl)

        logger.info(f"Cache warmed with {len(keys_and_values)} entries")

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0

        local_stats = self.local_cache.get_stats()

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "sets": self.sets,
            "deletes": self.deletes,
            "local_cache": local_stats,
            "distributed_enabled": self.enable_distributed,
        }


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    key_data = {"args": args, "kwargs": sorted(kwargs.items())}
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def cached(
    cache: DistributedCache, ttl: Optional[int] = None, tags: Optional[List[str]] = None
):
    """
    Decorator for caching function results.

    Args:
        cache: Cache instance
        ttl: TTL in seconds
        tags: Optional tags

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result

            # Compute result
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(key, result, ttl=ttl, tags=tags)

            return result

        return wrapper

    return decorator
