#!/usr/bin/env python3
"""
x0tta6bl4 Thread-Safe Statistics
============================================

Thread-safe statistics collection for concurrent operations.
Eliminates race conditions in metrics updates across mesh components.

Features:
- Atomic counters
- Thread-safe metrics collection
- Lock-free data structures where possible
- Performance optimized for high-frequency updates
"""

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AtomicCounter:
    """Thread-safe atomic counter."""

    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(self, delta: int = 1) -> int:
        """Increment counter and return new value."""
        with self._lock:
            self._value += delta
            return self._value

    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value

    def set(self, value: int) -> None:
        """Set counter value."""
        with self._lock:
            self._value = value

    def reset(self) -> int:
        """Reset counter and return old value."""
        with self._lock:
            old = self._value
            self._value = 0
            return old


@dataclass
class AtomicFloat:
    """Thread-safe atomic float."""

    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, value: float) -> float:
        """Update value and return new value."""
        with self._lock:
            self._value = value
            return self._value

    def add(self, delta: float) -> float:
        """Add delta and return new value."""
        with self._lock:
            self._value += delta
            return self._value

    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value


class ThreadSafeMetrics:
    """
    Thread-safe metrics collection for mesh components.

    Provides atomic operations for common metrics patterns:
    - Counters (packets, connections, errors)
    - Gauges (latency, throughput, active connections)
    - Histograms (latency distributions)
    - Sets (unique items)
    """

    def __init__(self, component_name: str):
        self.component_name = component_name

        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)

        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)

        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

        # Last update timestamp
        self._last_update = AtomicFloat()

        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")

    def increment_counter(self, name: str, delta: int = 1) -> int:
        """Increment a counter atomically."""
        result = self._counters[name].increment(delta)
        self._last_update.update(time.time())
        return result

    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self._counters[name].get()

    def set_gauge(self, name: str, value: float) -> float:
        """Set gauge value atomically."""
        result = self._gauges[name].update(value)
        self._last_update.update(time.time())
        return result

    def get_gauge(self, name: str) -> float:
        """Get gauge value."""
        return self._gauges[name].get()

    def add_to_set(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].add(item)
            self._last_update.update(time.time())
            return True

    def remove_from_set(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].remove(item)
            self._last_update.update(time.time())
            return True

    def get_set_size(self, set_name: str) -> int:
        """Get set size."""
        with self._set_locks[set_name]:
            return len(self._sets[set_name])

    def get_set_items(self, set_name: str) -> set:
        """Get copy of set items."""
        with self._set_locks[set_name]:
            return set(self._sets[set_name])

    def add_recent(self, series_name: str, value: Any) -> None:
        """Add value to recent series thread-safely."""
        with self._recent_locks[series_name]:
            self._recent[series_name].append((time.time(), value))
            self._last_update.update(time.time())

    def get_recent(self, series_name: str, limit: Optional[int] = None) -> List[tuple]:
        """Get recent values from series."""
        with self._recent_locks[series_name]:
            recent = list(self._recent[series_name])
            if limit:
                return recent[-limit:]
            return recent

    def get_stats_snapshot(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            "component": self.component_name,
            "last_update": self._last_update.get(),
            "counters": {},
            "gauges": {},
            "sets": {},
            "recent_series": {},
        }

        # Get counters
        for name, counter in self._counters.items():
            snapshot["counters"][name] = counter.get()

        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot["gauges"][name] = gauge.get()

        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot["sets"][name] = len(self._sets[name])

        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot["recent_series"][name] = len(self._recent[name])

        return snapshot

    def reset_all(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()

        for gauge in self._gauges.values():
            gauge.update(0.0)

        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()

        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()

        self._last_update.update(time.time())
        logger.info(f"Reset all metrics for {self.component_name}")


class MeshRouterStats:
    """Thread-safe statistics for MeshRouter."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")

        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)

    def update_peer_count(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("alive_peers", float(alive))

    def update_route_cache(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("routes_cached", float(cached_routes))

    def record_connection_established(self) -> None:
        """Record successful connection."""
        self.metrics.increment_counter("connections_established")

    def record_connection_failed(self) -> None:
        """Record failed connection."""
        self.metrics.increment_counter("connections_failed")

    def record_packet_routed(self) -> None:
        """Record packet routed successfully."""
        self.metrics.increment_counter("packets_routed")

    def record_packet_dropped(self) -> None:
        """Record packet dropped."""
        self.metrics.increment_counter("packets_dropped")

    def update_peer_latency(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("peer_latencies", (peer_id, latency_ms))

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()

        # Add computed metrics
        stats["success_rate"] = 0.0
        total_attempts = stats["counters"].get("connections_established", 0) + stats[
            "counters"
        ].get("connections_failed", 0)
        if total_attempts > 0:
            stats["success_rate"] = (
                stats["counters"].get("connections_established", 0) / total_attempts
            )

        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats["avg_latency"] = sum(latencies) / len(latencies)
            stats["min_latency"] = min(latencies)
            stats["max_latency"] = max(latencies)
        else:
            stats["avg_latency"] = 0.0
            stats["min_latency"] = 0.0
            stats["max_latency"] = 0.0

        return stats


class MeshTopologyStats:
    """Thread-safe statistics for MeshTopology."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")

        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)

    def update_topology_counts(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("total_links", float(links))

    def update_cache_size(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("cache_size", float(size))

    def record_path_computation(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("path_computations")
        self.metrics.increment_counter("cache_misses")

    def record_cache_hit(self) -> None:
        """Record cache hit."""
        self.metrics.increment_counter("cache_hits")

    def record_failover(self) -> None:
        """Record failover event."""
        self.metrics.increment_counter("failover_events")

    def get_stats(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()

        # Add computed metrics
        total_requests = stats["counters"].get("cache_hits", 0) + stats["counters"].get(
            "cache_misses", 0
        )
        if total_requests > 0:
            stats["cache_hit_rate"] = (
                stats["counters"].get("cache_hits", 0) / total_requests
            )
        else:
            stats["cache_hit_rate"] = 0.0

        return stats


# Global registry for component stats
_component_stats: Dict[str, Any] = {}
_registry_lock = threading.Lock()


def get_component_stats(component_id: str) -> Optional[ThreadSafeMetrics]:
    """Get component statistics from registry."""
    with _registry_lock:
        return _component_stats.get(component_id)


def register_component_stats(component_id: str, stats: ThreadSafeMetrics) -> None:
    """Register component statistics in registry."""
    with _registry_lock:
        _component_stats[component_id] = stats


def get_all_stats() -> Dict[str, Dict[str, Any]]:
    """Get all registered component statistics."""
    with _registry_lock:
        return {
            component_id: stats.get_stats_snapshot()
            for component_id, stats in _component_stats.items()
        }
