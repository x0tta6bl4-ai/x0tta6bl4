"""
Edge Cache - Distributed caching for edge computing.

Provides intelligent caching with multiple eviction policies,
cache invalidation strategies, and distributed cache synchronization.
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar('K')
V = TypeVar('V')


class CachePolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"           # Least Recently Used
    LFU = "lfu"           # Least Frequently Used
    FIFO = "fifo"         # First In First Out
    TTL = "ttl"           # Time To Live only
    ADAPTIVE = "adaptive"  # Adaptive based on access patterns


class CacheState(Enum):
    """State of a cache entry."""
    ACTIVE = "active"
    EXPIRED = "expired"
    EVICTING = "evicting"
    PENDING = "pending"


@dataclass
class CacheEntry(Generic[V]):
    """A single cache entry."""
    key: str
    value: V
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    @property
    def idle_seconds(self) -> float:
        """Get idle time since last access."""
        return (datetime.utcnow() - self.last_accessed).total_seconds()
    
    def touch(self) -> None:
        """Update last accessed time and increment count."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheConfig:
    """Configuration for edge cache."""
    max_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    max_entries: int = 10000
    default_ttl_seconds: float = 3600.0  # 1 hour
    policy: CachePolicy = CachePolicy.ADAPTIVE
    
    # Eviction settings
    eviction_batch_size: int = 100
    eviction_threshold_percent: float = 90.0
    
    # Invalidation settings
    enable_background_cleanup: bool = True
    cleanup_interval_seconds: float = 60.0
    
    # Statistics
    enable_statistics: bool = True
    statistics_window_seconds: float = 300.0
    
    # Distributed cache
    enable_replication: bool = False
    replication_factor: int = 2
    sync_interval_seconds: float = 10.0


@dataclass
class CacheStatistics:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    
    # Timing statistics
    total_get_time_ns: int = 0
    total_set_time_ns: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_get_time_ns(self) -> float:
        """Average get operation time."""
        return self.total_get_time_ns / self.hits if self.hits > 0 else 0
    
    @property
    def avg_set_time_ns(self) -> float:
        """Average set operation time."""
        return self.total_set_time_ns / self.entry_count if self.entry_count > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_size_bytes": self.total_size_bytes,
            "entry_count": self.entry_count,
            "avg_get_time_ns": self.avg_get_time_ns,
            "avg_set_time_ns": self.avg_set_time_ns,
        }


class EvictionStrategy(ABC):
    """Abstract base class for eviction strategies."""
    
    @abstractmethod
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        """Select entries for eviction."""
        pass


class LRUStrategy(EvictionStrategy):
    """Least Recently Used eviction."""
    
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].last_accessed
        )
        return [k for k, _ in sorted_entries[:count]]


class LFUStrategy(EvictionStrategy):
    """Least Frequently Used eviction."""
    
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        # Sort by access count (lowest first)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].access_count
        )
        return [k for k, _ in sorted_entries[:count]]


class FIFOStrategy(EvictionStrategy):
    """First In First Out eviction."""
    
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        # Sort by creation time (oldest first)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].created_at
        )
        return [k for k, _ in sorted_entries[:count]]


class TTLStrategy(EvictionStrategy):
    """Time To Live based eviction."""
    
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        # Select expired entries first
        expired = [k for k, v in entries.items() if v.is_expired]
        
        if len(expired) >= count:
            return expired[:count]
        
        # Then select by age
        remaining = count - len(expired)
        non_expired = {k: v for k, v in entries.items() if not v.is_expired}
        sorted_entries = sorted(
            non_expired.items(),
            key=lambda x: x[1].created_at
        )
        
        return expired + [k for k, _ in sorted_entries[:remaining]]


class AdaptiveStrategy(EvictionStrategy):
    """
    Adaptive eviction combining multiple factors.
    
    Considers:
    - Recency (LRU)
    - Frequency (LFU)
    - Size (prefer evicting large items)
    - TTL remaining
    """
    
    def __init__(self):
        self._lru_strategy = LRUStrategy()
        self._lfu_strategy = LFUStrategy()
    
    def select_for_eviction(
        self,
        entries: Dict[str, CacheEntry],
        count: int
    ) -> List[str]:
        # Score each entry
        scores: List[Tuple[str, float]] = []
        
        for key, entry in entries.items():
            score = self._compute_eviction_score(entry)
            scores.append((key, score))
        
        # Sort by score (highest eviction score first)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [k for k, _ in scores[:count]]
    
    def _compute_eviction_score(self, entry: CacheEntry) -> float:
        """
        Compute eviction score (higher = more likely to evict).
        
        Factors:
        - Idle time (longer idle = higher score)
        - Low access count = higher score
        - Large size = higher score
        - Near expiration = higher score
        """
        # Normalize factors to 0-1 range
        idle_score = min(1.0, entry.idle_seconds / 3600)  # 1 hour max
        
        access_score = 1.0 / (1.0 + entry.access_count)
        
        size_score = min(1.0, entry.size_bytes / (1024 * 1024))  # 1 MB max
        
        ttl_score = 0.0
        if entry.ttl_seconds:
            remaining = entry.ttl_seconds - entry.age_seconds
            if remaining < 0:
                ttl_score = 1.0
            else:
                ttl_score = 1.0 - (remaining / entry.ttl_seconds)
        
        # Weighted combination
        return (
            idle_score * 0.3 +
            access_score * 0.3 +
            size_score * 0.2 +
            ttl_score * 0.2
        )


class EdgeCache(Generic[V]):
    """
    Distributed edge cache with intelligent eviction.
    
    Features:
    - Multiple eviction policies
    - TTL-based expiration
    - Tag-based invalidation
    - Statistics tracking
    - Background cleanup
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        
        # Storage
        self._entries: Dict[str, CacheEntry[V]] = {}
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> keys
        
        # Eviction strategies
        self._strategies: Dict[CachePolicy, EvictionStrategy] = {
            CachePolicy.LRU: LRUStrategy(),
            CachePolicy.LFU: LFUStrategy(),
            CachePolicy.FIFO: FIFOStrategy(),
            CachePolicy.TTL: TTLStrategy(),
            CachePolicy.ADAPTIVE: AdaptiveStrategy(),
        }
        
        # Statistics
        self._stats = CacheStatistics()
        
        # Callbacks
        self._eviction_callbacks: List[Callable[[str, V], None]] = []
        self._expiration_callbacks: List[Callable[[str, V], None]] = []
        
        # Background task
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start background cleanup task."""
        if self.config.enable_background_cleanup:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Edge cache started with background cleanup")
    
    async def stop(self) -> None:
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Edge cache stopped")
    
    def get(self, key: str) -> Optional[V]:
        """Get value from cache."""
        start_time = time.time_ns()
        
        entry = self._entries.get(key)
        
        if entry is None:
            self._stats.misses += 1
            return None
        
        if entry.is_expired:
            self._remove_entry(key)
            self._stats.misses += 1
            self._stats.expirations += 1
            return None
        
        # Update access info
        entry.touch()
        
        # Update stats
        self._stats.hits += 1
        self._stats.total_get_time_ns += time.time_ns() - start_time
        
        return entry.value
    
    def set(
        self,
        key: str,
        value: V,
        ttl_seconds: Optional[float] = None,
        tags: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Set value in cache."""
        start_time = time.time_ns()
        
        # Calculate size
        try:
            size_bytes = len(pickle.dumps(value))
        except Exception:
            size_bytes = 0
        
        # Check if we need eviction
        self._ensure_capacity(size_bytes)
        
        # Create entry
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
            size_bytes=size_bytes,
            tags=tags or set(),
            metadata=metadata or {},
        )
        
        # Remove old entry if exists
        if key in self._entries:
            self._remove_entry(key)
        
        # Add entry
        self._entries[key] = entry
        
        # Update tag index
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(key)
        
        # Update stats
        self._stats.entry_count = len(self._entries)
        self._stats.total_size_bytes += size_bytes
        self._stats.total_set_time_ns += time.time_ns() - start_time
        
        return True
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        if key in self._entries:
            self._remove_entry(key)
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        entry = self._entries.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            self._remove_entry(key)
            return False
        return True
    
    def get_or_set(
        self,
        key: str,
        factory: Callable[[], V],
        ttl_seconds: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> V:
        """Get value or compute and set if missing."""
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl_seconds, tags)
        return value
    
    async def get_or_set_async(
        self,
        key: str,
        factory: Callable[[], V],
        ttl_seconds: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> V:
        """Async version of get_or_set."""
        value = self.get(key)
        if value is not None:
            return value
        
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        self.set(key, value, ttl_seconds, tags)
        return value
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        keys = self._tag_index.get(tag, set())
        count = 0
        
        for key in list(keys):
            if self.delete(key):
                count += 1
        
        return count
    
    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all entries with key prefix."""
        count = 0
        for key in list(self._entries.keys()):
            if key.startswith(prefix):
                if self.delete(key):
                    count += 1
        return count

    def invalidate(
        self,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Compatibility invalidation API used by edge endpoints."""
        count = 0
        if pattern:
            # Best-effort mapping: treat pattern as prefix when it endswith '*'.
            if pattern.endswith("*"):
                count += self.invalidate_by_prefix(pattern[:-1])
            else:
                count += self.invalidate_by_prefix(pattern)

        if tags:
            for tag in tags:
                count += self.invalidate_by_tag(tag)

        if not pattern and not tags:
            count = len(self._entries)
            self.clear()

        return count
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries.clear()
        self._tag_index.clear()
        self._stats = CacheStatistics()
    
    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        self._stats.entry_count = len(self._entries)
        return self._stats
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary of cache statistics."""
        return {
            **self._stats.to_dict(),
            "config": {
                "max_size_bytes": self.config.max_size_bytes,
                "max_entries": self.config.max_entries,
                "policy": self.config.policy.value,
            },
        }
    
    def add_eviction_callback(self, callback: Callable[[str, V], None]) -> None:
        """Add callback for eviction events."""
        self._eviction_callbacks.append(callback)
    
    def add_expiration_callback(self, callback: Callable[[str, V], None]) -> None:
        """Add callback for expiration events."""
        self._expiration_callbacks.append(callback)
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry and update indexes."""
        entry = self._entries.pop(key, None)
        if entry:
            # Update tag index
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)
                    if not self._tag_index[tag]:
                        del self._tag_index[tag]
            
            # Update stats
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.entry_count = len(self._entries)
    
    def _ensure_capacity(self, additional_bytes: int) -> None:
        """Ensure there's capacity for new entry."""
        current_size = self._stats.total_size_bytes
        max_size = self.config.max_size_bytes
        
        # Check if we need eviction
        if (
            current_size + additional_bytes > max_size * (self.config.eviction_threshold_percent / 100) or
            len(self._entries) >= self.config.max_entries
        ):
            self._evict(self.config.eviction_batch_size)
    
    def _evict(self, count: int) -> int:
        """Evict entries using configured policy."""
        if not self._entries:
            return 0
        
        strategy = self._strategies.get(self.config.policy, self._strategies[CachePolicy.ADAPTIVE])
        keys_to_evict = strategy.select_for_eviction(self._entries, count)
        
        evicted = 0
        for key in keys_to_evict:
            entry = self._entries.get(key)
            if entry:
                # Notify callbacks
                for callback in self._eviction_callbacks:
                    try:
                        callback(key, entry.value)
                    except Exception as e:
                        logger.warning(f"Eviction callback error: {e}")
                
                self._remove_entry(key)
                evicted += 1
        
        self._stats.evictions += evicted
        return evicted
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired_keys = [
            key for key, entry in self._entries.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            entry = self._entries.get(key)
            if entry:
                # Notify callbacks
                for callback in self._expiration_callbacks:
                    try:
                        callback(key, entry.value)
                    except Exception as e:
                        logger.warning(f"Expiration callback error: {e}")
                
                self._remove_entry(key)
                self._stats.expirations += 1
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
        
        return len(expired_keys)
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a cache entry."""
        entry = self._entries.get(key)
        if not entry:
            return None
        
        return {
            "key": entry.key,
            "created_at": entry.created_at.isoformat(),
            "last_accessed": entry.last_accessed.isoformat(),
            "access_count": entry.access_count,
            "age_seconds": entry.age_seconds,
            "idle_seconds": entry.idle_seconds,
            "ttl_seconds": entry.ttl_seconds,
            "is_expired": entry.is_expired,
            "size_bytes": entry.size_bytes,
            "tags": list(entry.tags),
        }
    
    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all keys, optionally filtered by pattern."""
        keys = list(self._entries.keys())
        
        if pattern:
            import fnmatch
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        
        return keys
    
    def get_size_info(self) -> Dict[str, Any]:
        """Get size information."""
        return {
            "total_size_bytes": self._stats.total_size_bytes,
            "max_size_bytes": self.config.max_size_bytes,
            "usage_percent": (
                self._stats.total_size_bytes / self.config.max_size_bytes * 100
                if self.config.max_size_bytes > 0 else 0
            ),
            "entry_count": len(self._entries),
            "max_entries": self.config.max_entries,
            "entry_usage_percent": (
                len(self._entries) / self.config.max_entries * 100
                if self.config.max_entries > 0 else 0
            ),
        }


class DistributedEdgeCache(EdgeCache[V]):
    """
    Distributed cache with replication across edge nodes.
    
    Features:
    - Cache replication
    - Invalidation propagation
    - Consistency management
    """
    
    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        node_id: str = "local",
    ):
        super().__init__(config)
        self.node_id = node_id
        self._peers: Dict[str, "DistributedEdgeCache"] = {}
        self._pending_invalidations: Set[str] = set()
    
    def add_peer(self, peer_id: str, peer_cache: "DistributedEdgeCache") -> None:
        """Add a peer cache for replication."""
        self._peers[peer_id] = peer_cache
    
    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer cache."""
        self._peers.pop(peer_id, None)
    
    def set(
        self,
        key: str,
        value: V,
        ttl_seconds: Optional[float] = None,
        tags: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        replicate: bool = True,
    ) -> bool:
        """Set value with optional replication."""
        result = super().set(key, value, ttl_seconds, tags, metadata)
        
        if result and replicate and self.config.enable_replication:
            self._replicate_set(key, value, ttl_seconds, tags, metadata)
        
        return result
    
    def delete(self, key: str, propagate: bool = True) -> bool:
        """Delete with optional propagation."""
        result = super().delete(key)
        
        if result and propagate:
            self._propagate_invalidation(key)
        
        return result
    
    def invalidate_by_tag(self, tag: str, propagate: bool = True) -> int:
        """Invalidate by tag with optional propagation."""
        count = super().invalidate_by_tag(tag)
        
        if count > 0 and propagate:
            self._propagate_tag_invalidation(tag)
        
        return count
    
    def _replicate_set(
        self,
        key: str,
        value: V,
        ttl_seconds: Optional[float],
        tags: Optional[Set[str]],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Replicate set operation to peers."""
        # Select peers for replication
        peers = list(self._peers.values())
        if len(peers) > self.config.replication_factor:
            # Use consistent hashing to select peers
            peers = peers[:self.config.replication_factor]
        
        for peer in peers:
            try:
                peer.set(key, value, ttl_seconds, tags, metadata, replicate=False)
            except Exception as e:
                logger.warning(f"Replication to peer failed: {e}")
    
    def _propagate_invalidation(self, key: str) -> None:
        """Propagate invalidation to peers."""
        for peer_id, peer in self._peers.items():
            try:
                peer.delete(key, propagate=False)
            except Exception as e:
                logger.warning(f"Invalidation propagation to {peer_id} failed: {e}")
    
    def _propagate_tag_invalidation(self, tag: str) -> None:
        """Propagate tag invalidation to peers."""
        for peer_id, peer in self._peers.items():
            try:
                peer.invalidate_by_tag(tag, propagate=False)
            except Exception as e:
                logger.warning(f"Tag invalidation propagation to {peer_id} failed: {e}")
