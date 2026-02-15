"""
Redis Cache Module for x0tta6bl4

Provides:
- Async Redis client with connection pooling
- Cache-aside pattern with TTL
- Background cache warming
- Thundering herd protection
- Dependency injection support for testability
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Optional, ParamSpec, Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class CacheBackend(Protocol):
    """Protocol for cache backend implementations."""

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        ...

    async def set(
        self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False
    ) -> bool:
        """Set value in cache."""
        ...

    async def delete(self, key: str) -> int:
        """Delete key from cache."""
        ...

    async def ping(self) -> bool:
        """Test connection."""
        ...

    async def close(self) -> None:
        """Close connection."""
        ...


class InMemoryCacheBackend:
    """In-memory cache backend for testing."""

    def __init__(self):
        self._data: dict[str, tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._data:
                return None
            value, expiry = self._data[key]
            if expiry is not None and expiry < time.time():
                del self._data[key]
                return None
            return value

    async def set(
        self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False
    ) -> bool:
        async with self._lock:
            if nx and key in self._data:
                return False
            expiry = time.time() + ex if ex else None
            self._data[key] = (value, expiry)
            return True

    async def delete(self, key: str) -> int:
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return 1
            return 0

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()

    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._data.clear()


class RedisCache:
    """
    Async Redis cache with connection pooling and dependency injection support.

    Features:
    - Connection pooling for high concurrency
    - Automatic reconnection
    - JSON serialization
    - TTL support
    - Injectable backend for testing
    """

    _instance: Optional["RedisCache"] = None
    _lock = asyncio.Lock()

    def __new__(cls, backend: Optional[CacheBackend] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._backend = None
        return cls._instance

    def __init__(self, backend: Optional[CacheBackend] = None):
        # Only initialize if not already initialized or if new backend provided
        if not self._initialized or backend is not None:
            self._backend = backend
            self._initialized = False

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    @classmethod
    def create_for_testing(cls, backend: Optional[CacheBackend] = None) -> "RedisCache":
        """Create cache instance with test backend."""
        cls._instance = None
        instance = cls.__new__(cls)
        instance._initialized = True
        instance._backend = backend or InMemoryCacheBackend()
        cls._instance = instance
        return instance

    async def _initialize(self):
        """Initialize Redis connection pool with Sentinel support."""
        if self._initialized:
            return

        # If backend was injected, mark as initialized
        if self._backend is not None:
            self._initialized = True
            return

        try:
            import redis.asyncio as redis
            from redis.asyncio.connection import ConnectionPool

            # Check if Sentinel mode is enabled
            sentinel_hosts = os.getenv("REDIS_SENTINEL_HOSTS", "")
            sentinel_master = os.getenv("REDIS_SENTINEL_MASTER", "mymaster")

            if sentinel_hosts:
                # Redis Sentinel mode for HA
                await self._initialize_sentinel(sentinel_hosts, sentinel_master)
            else:
                # Standalone Redis mode
                await self._initialize_standalone()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            self._backend = None

    async def _initialize_sentinel(self, sentinel_hosts: str, master_name: str):
        """Initialize Redis with Sentinel for HA."""
        import redis.asyncio as redis
        from redis.asyncio.sentinel import Sentinel

        # Parse sentinel hosts: "host1:port1,host2:port2,host3:port3"
        sentinels = []
        for host_port in sentinel_hosts.split(","):
            host_port = host_port.strip()
            if ":" in host_port:
                host, port = host_port.split(":")
                sentinels.append((host, int(port)))
            else:
                sentinels.append((host_port, 26379))  # Default Sentinel port

        logger.info(f"🔄 Connecting to Redis via Sentinel: {sentinels}")

        # Create Sentinel instance
        sentinel = Sentinel(
            sentinels,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )

        # Get master connection with automatic failover
        self._sentinel = sentinel
        self._backend = sentinel.master_for(
            master_name,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True,
        )

        # Test connection
        await self._backend.ping()
        self._initialized = True

        # Log master info
        master_addr = await sentinel.discover_master(master_name)
        logger.info(
            f"✅ Redis Sentinel initialized - Master: {master_addr[0]}:{master_addr[1]}"
        )

    async def _initialize_standalone(self):
        """Initialize standalone Redis connection."""
        import redis.asyncio as redis
        from redis.asyncio.connection import ConnectionPool

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        self._pool = ConnectionPool.from_url(
            redis_url,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        self._backend = redis.Redis(connection_pool=self._pool)

        # Test connection
        await self._backend.ping()
        self._initialized = True
        logger.info(f"✅ Redis cache initialized (standalone): {redis_url}")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._initialized:
            await self._initialize()

        backend = self._backend
        if backend is None:
            return None

        try:
            data = await backend.get(key)
            if data:
                if isinstance(data, bytes):
                    return json.loads(data.decode("utf-8"))
                return data  # Already deserialized (from InMemoryCache)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 60, nx: bool = False) -> bool:
        """
        Set value in cache.
        """
        if not self._initialized:
            await self._initialize()

        backend = self._backend
        if backend is None:
            return False

        try:
            # For InMemoryCache, store as-is; for Redis, serialize
            if isinstance(backend, InMemoryCacheBackend):
                result = await backend.set(key, value, ex=ttl, nx=nx)
            else:
                data = json.dumps(value, default=str)
                result = await backend.set(key, data, ex=ttl, nx=nx)
            return bool(result)
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._initialized:
            await self._initialize()

        backend = self._backend
        if backend is None:
            return False

        try:
            result = await backend.delete(key)
            return bool(result and result > 0)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    async def close(self):
        """Close Redis connection."""
        if self._backend:
            await self._backend.close()
            self._initialized = False

    async def health_check(self) -> dict:
        """
        Get Redis health status including Sentinel info.

        Returns:
            dict with status, mode, and connection details
        """
        if not self._initialized:
            await self._initialize()

        if not self._backend:
            return {
                "status": "unhealthy",
                "error": "Redis not initialized",
                "mode": "none",
            }

        try:
            # Basic ping test
            await self._backend.ping()

            result = {
                "status": "healthy",
                "mode": "sentinel" if hasattr(self, "_sentinel") else "standalone",
            }

            # Add Sentinel-specific info
            if hasattr(self, "_sentinel") and self._sentinel:
                sentinel_master = os.getenv("REDIS_SENTINEL_MASTER", "mymaster")
                try:
                    master_addr = await self._sentinel.discover_master(sentinel_master)
                    slaves = await self._sentinel.discover_slaves(sentinel_master)
                    result["master"] = f"{master_addr[0]}:{master_addr[1]}"
                    result["replicas"] = len(slaves)
                    result["replica_addresses"] = [f"{s[0]}:{s[1]}" for s in slaves]
                except Exception as e:
                    result["sentinel_error"] = str(e)

            # Get Redis info
            try:
                info = await self._backend.info("replication")
                result["role"] = info.get("role", "unknown")
                result["connected_slaves"] = info.get("connected_slaves", 0)
            except Exception:
                pass

            return result

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "mode": "sentinel" if hasattr(self, "_sentinel") else "standalone",
            }

    async def get_stats(self) -> dict:
        """Get Redis statistics."""
        if not self._initialized or not self._backend:
            return {"error": "Not initialized"}

        try:
            info = await self._backend.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            return {"error": str(e)}


# Global cache instance (lazy initialization)
_cache_instance: Optional[RedisCache] = None


def get_cache(backend: Optional[CacheBackend] = None) -> RedisCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache(backend)
    return _cache_instance


def reset_cache() -> None:
    """Reset global cache instance (for testing)."""
    global _cache_instance
    _cache_instance = None
    RedisCache.reset_instance()


# Backward compatibility - global cache instance
cache = get_cache()


def cached(
    ttl: int = 60,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None,
    cache_instance: Optional[RedisCache] = None,
):
    """
    Decorator for caching function results.

    Args:
        ttl: Cache time-to-live in seconds
        key_prefix: Prefix for cache key
        key_builder: Custom function to build cache key from arguments
        cache_instance: Optional cache instance (for testing)
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Use provided cache instance or global
            cache_obj = cache_instance or cache

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key: prefix:function_name:args_hash
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hash(args_str) % 10000000
                cache_key = f"{key_prefix}:{func.__name__}:{args_hash}"

            # Try to get from cache
            cached_value = await cache_obj.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Cache miss - execute function
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)

            # Store in cache
            await cache_obj.set(cache_key, result, ttl=ttl)

            return result

        # Add cache invalidation helper
        async def invalidate(*a, **kw) -> bool:
            cache_obj = cache_instance or cache
            key = (
                key_builder(*a, **kw)
                if key_builder
                else f"{key_prefix}:{func.__name__}:{hash(str(a) + str(sorted(kw.items()))) % 10000000}"
            )
            return await cache_obj.delete(key)

        wrapper.invalidate = invalidate

        return wrapper

    return decorator


class CacheWarming:
    """
    Background cache warming to prevent thundering herd.
    """

    def __init__(self, cache_instance: Optional[RedisCache] = None):
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._cache = cache_instance or cache

    async def warm_cache(
        self, key: str, func: Callable[..., T], ttl: int = 60, *args, **kwargs
    ) -> T:
        """
        Warm cache with thundering herd protection.

        If multiple requests come for the same key while it's being
        computed, only one computation happens and others wait.
        """
        # Check cache first
        cached_value = await self._cache.get(key)
        if cached_value is not None:
            return cached_value

        async with self._lock:
            # Double-check after acquiring lock
            cached_value = await self._cache.get(key)
            if cached_value is not None:
                return cached_value

            # Check if warming is already in progress
            if key in self._tasks:
                task = self._tasks[key]
            else:
                # Start warming
                task = asyncio.create_task(
                    self._do_warm(key, func, ttl, *args, **kwargs)
                )
                self._tasks[key] = task

        try:
            result = await task
            return result
        finally:
            async with self._lock:
                self._tasks.pop(key, None)

    async def _do_warm(
        self, key: str, func: Callable[..., T], ttl: int, *args, **kwargs
    ) -> T:
        """Execute function and cache result."""
        try:
            result = await func(*args, **kwargs)
            await self._cache.set(key, result, ttl=ttl)
            return result
        except Exception as e:
            logger.error(f"Cache warming failed for {key}: {e}")
            raise


# Global cache warming instance
cache_warmer = CacheWarming()


# Convenience function for cache warming
async def get_or_warm(
    key: str, func: Callable[..., T], ttl: int = 60, *args, **kwargs
) -> T:
    """
    Get from cache or warm if missing.

    Uses thundering herd protection.
    """
    return await cache_warmer.warm_cache(key, func, ttl, *args, **kwargs)


# Import time for InMemoryCacheBackend
import time
