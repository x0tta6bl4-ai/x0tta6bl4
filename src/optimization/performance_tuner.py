import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque
import asyncio
import functools

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    name: str
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"


class LatencyTracker:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.lock = threading.Lock()
    
    def record(self, name: str, latency_ms: float, metadata: Dict = None) -> None:
        with self.lock:
            metric = PerformanceMetric(name, latency_ms, metadata=metadata or {})
            self.metrics[name].append(metric)
    
    def get_stats(self, name: str) -> Dict:
        with self.lock:
            if name not in self.metrics or not self.metrics[name]:
                return {"p50": 0, "p95": 0, "p99": 0, "count": 0, "avg": 0}
            
            values = sorted([m.latency_ms for m in self.metrics[name]])
            count = len(values)
            return {
                "count": count,
                "avg": sum(values) / count,
                "min": min(values),
                "max": max(values),
                "p50": values[int(count * 0.5)],
                "p95": values[int(count * 0.95)],
                "p99": values[int(count * 0.99)],
            }
    
    def get_all_stats(self) -> Dict:
        with self.lock:
            return {name: self.get_stats(name) for name in self.metrics.keys()}


class AsyncBottleneckDetector:
    def __init__(self, slowdown_threshold: float = 1.5):
        self.slowdown_threshold = slowdown_threshold
        self.baseline: Dict[str, float] = {}
        self.current: Dict[str, float] = {}
        self.slowdown_alerts: List[Dict] = []
        self.lock = threading.Lock()
    
    def record_baseline(self, operation: str, latency_ms: float) -> None:
        with self.lock:
            if operation not in self.baseline:
                self.baseline[operation] = latency_ms
            else:
                self.baseline[operation] = (self.baseline[operation] + latency_ms) / 2
    
    def record_current(self, operation: str, latency_ms: float) -> None:
        with self.lock:
            self.current[operation] = latency_ms
            
            if operation in self.baseline:
                ratio = latency_ms / self.baseline[operation]
                if ratio > self.slowdown_threshold:
                    self.slowdown_alerts.append({
                        "operation": operation,
                        "baseline_ms": self.baseline[operation],
                        "current_ms": latency_ms,
                        "slowdown_ratio": ratio,
                        "timestamp": datetime.utcnow().isoformat()
                    })
    
    def get_slowdowns(self) -> List[Dict]:
        with self.lock:
            return self.slowdown_alerts[-100:]
    
    def get_top_slowdowns(self, limit: int = 10) -> List[Dict]:
        with self.lock:
            sorted_alerts = sorted(
                self.slowdown_alerts,
                key=lambda x: x["slowdown_ratio"],
                reverse=True
            )
            return sorted_alerts[:limit]
    
    def clear_alerts(self) -> None:
        with self.lock:
            self.slowdown_alerts = []


class MemoryOptimizer:
    def __init__(self, max_cache_size_mb: int = 100):
        self.max_cache_size = max_cache_size_mb * 1024 * 1024
        self.cache: Dict[str, tuple] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.lock = threading.Lock()
    
    def get_cached(self, key: str, compute_fn: Callable, ttl_seconds: int = 3600) -> Any:
        with self.lock:
            now = time.time()
            if key in self.cache:
                value, timestamp, size = self.cache[key]
                if now - timestamp < ttl_seconds:
                    self.cache_hits += 1
                    return value
                else:
                    del self.cache[key]
            
            self.cache_misses += 1
        
        value = compute_fn()
        
        with self.lock:
            estimated_size = len(str(value))
            if estimated_size > self.max_cache_size:
                logger.warning(f"Single cache entry {key} exceeds max size")
                return value
            
            total_size = sum(size for _, _, size in self.cache.values())
            if total_size + estimated_size > self.max_cache_size:
                self._evict_lru()
            
            self.cache[key] = (value, time.time(), estimated_size)
        
        return value
    
    def _evict_lru(self) -> None:
        if not self.cache:
            return
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k][1]
        )
        del self.cache[oldest_key]
    
    def get_stats(self) -> Dict:
        with self.lock:
            total_size = sum(size for _, _, size in self.cache.values())
            total = self.cache_hits + self.cache_misses
            hit_rate = self.cache_hits / total if total > 0 else 0
            return {
                "cache_size_bytes": total_size,
                "cache_entries": len(self.cache),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate": hit_rate
            }


class ConnectionPoolOptimizer:
    def __init__(self, min_connections: int = 5, max_connections: int = 50):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.active_connections = 0
        self.total_created = 0
        self.wait_times: deque = deque(maxlen=1000)
        self.lock = threading.Lock()
    
    def acquire_connection(self, timeout_ms: int = 5000) -> Dict:
        start = time.time()
        with self.lock:
            if self.active_connections >= self.max_connections:
                logger.warning("Connection pool at max capacity")
                wait_ms = (time.time() - start) * 1000
                self.wait_times.append(wait_ms)
                return {"acquired": False, "reason": "max_connections_reached"}
            
            self.active_connections += 1
            self.total_created += 1
        
        wait_ms = (time.time() - start) * 1000
        with self.lock:
            self.wait_times.append(wait_ms)
        
        return {"acquired": True, "connection_id": self.total_created}
    
    def release_connection(self) -> None:
        with self.lock:
            if self.active_connections > 0:
                self.active_connections -= 1
    
    def get_stats(self) -> Dict:
        with self.lock:
            wait_times = list(self.wait_times)
            if not wait_times:
                return {
                    "active": self.active_connections,
                    "total_created": self.total_created,
                    "avg_wait_ms": 0,
                    "max_wait_ms": 0
                }
            
            return {
                "active": self.active_connections,
                "total_created": self.total_created,
                "available": self.max_connections - self.active_connections,
                "utilization": self.active_connections / self.max_connections,
                "avg_wait_ms": sum(wait_times) / len(wait_times),
                "max_wait_ms": max(wait_times),
                "queue_wait_p95": sorted(wait_times)[int(len(wait_times) * 0.95)]
            }


class EdgeCaseHandler:
    def __init__(self):
        self.edge_case_log: List[Dict] = []
        self.lock = threading.Lock()
    
    def handle_large_payload(self, size_bytes: int, threshold_bytes: int = 10_000_000) -> bool:
        if size_bytes > threshold_bytes:
            with self.lock:
                self.edge_case_log.append({
                    "type": "large_payload",
                    "size_bytes": size_bytes,
                    "timestamp": datetime.utcnow().isoformat()
                })
            logger.warning(f"Large payload detected: {size_bytes} bytes")
            return False
        return True
    
    def handle_high_concurrency(self, concurrent_requests: int, threshold: int = 1000) -> bool:
        if concurrent_requests > threshold:
            with self.lock:
                self.edge_case_log.append({
                    "type": "high_concurrency",
                    "requests": concurrent_requests,
                    "timestamp": datetime.utcnow().isoformat()
                })
            logger.warning(f"High concurrency: {concurrent_requests} requests")
            return False
        return True
    
    def handle_slow_query(self, query_time_ms: float, threshold_ms: float = 5000) -> bool:
        if query_time_ms > threshold_ms:
            with self.lock:
                self.edge_case_log.append({
                    "type": "slow_query",
                    "duration_ms": query_time_ms,
                    "timestamp": datetime.utcnow().isoformat()
                })
            logger.warning(f"Slow query: {query_time_ms}ms")
            return False
        return True
    
    def get_recent_edge_cases(self, limit: int = 50) -> List[Dict]:
        with self.lock:
            return self.edge_case_log[-limit:]


class PerformanceTuner:
    def __init__(self):
        self.latency_tracker = LatencyTracker()
        self.bottleneck_detector = AsyncBottleneckDetector()
        self.memory_optimizer = MemoryOptimizer()
        self.connection_pool = ConnectionPoolOptimizer()
        self.edge_case_handler = EdgeCaseHandler()
        self.recommendations: List[str] = []
        self.lock = threading.Lock()
    
    def analyze_performance(self) -> Dict:
        analysis = {
            "latency_stats": self.latency_tracker.get_all_stats(),
            "slowdowns": self.bottleneck_detector.get_top_slowdowns(5),
            "memory": self.memory_optimizer.get_stats(),
            "connections": self.connection_pool.get_stats(),
            "edge_cases": self.edge_case_handler.get_recent_edge_cases(10),
            "recommendations": self._generate_recommendations()
        }
        return analysis
    
    def _generate_recommendations(self) -> List[str]:
        recommendations = []
        
        memory_stats = self.memory_optimizer.get_stats()
        if memory_stats["hit_rate"] < 0.5:
            recommendations.append("Consider warming up cache or adjusting TTL")
        
        conn_stats = self.connection_pool.get_stats()
        if conn_stats.get("utilization", 0) > 0.9:
            recommendations.append("Connection pool near max capacity - consider scaling")
        
        slowdowns = self.bottleneck_detector.get_top_slowdowns(1)
        if slowdowns and slowdowns[0]["slowdown_ratio"] > 2.0:
            recommendations.append(f"Critical slowdown in {slowdowns[0]['operation']}")
        
        return recommendations
    
    def profile_function(self, func_name: str):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    latency_ms = (time.time() - start) * 1000
                    self.latency_tracker.record(func_name, latency_ms)
                    self.bottleneck_detector.record_current(func_name, latency_ms)
                    return result
                except Exception as e:
                    latency_ms = (time.time() - start) * 1000
                    self.latency_tracker.record(func_name, latency_ms, metadata={"error": str(e)})
                    raise
            return wrapper
        return decorator
    
    def profile_async_function(self, func_name: str):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    latency_ms = (time.time() - start) * 1000
                    self.latency_tracker.record(func_name, latency_ms)
                    self.bottleneck_detector.record_current(func_name, latency_ms)
                    return result
                except Exception as e:
                    latency_ms = (time.time() - start) * 1000
                    self.latency_tracker.record(func_name, latency_ms, metadata={"error": str(e)})
                    raise
            return wrapper
        return decorator


_tuner = None

def get_performance_tuner() -> PerformanceTuner:
    global _tuner
    if _tuner is None:
        _tuner = PerformanceTuner()
    return _tuner


__all__ = [
    "PerformanceMetric",
    "LatencyTracker",
    "AsyncBottleneckDetector",
    "MemoryOptimizer",
    "ConnectionPoolOptimizer",
    "EdgeCaseHandler",
    "PerformanceTuner",
    "get_performance_tuner",
]
