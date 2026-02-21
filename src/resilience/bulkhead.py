"""
Advanced Bulkhead Patterns
==========================

Resource isolation patterns for preventing cascade failures:
- Semaphore Bulkhead: Limit concurrent executions
- Queue-Based Bulkhead: Queue requests with bounded size
- Partitioned Bulkhead: Isolate different workload types
- Adaptive Bulkhead: ML-based capacity adjustment
"""

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Generic, Union
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BulkheadType(Enum):
    """Types of bulkhead implementations."""
    SEMAPHORE = "semaphore"
    QUEUE = "queue"
    PARTITIONED = "partitioned"
    ADAPTIVE = "adaptive"


class BulkheadFullException(Exception):
    """Exception raised when bulkhead is at capacity."""
    
    def __init__(
        self,
        message: str = "Bulkhead is at capacity",
        max_concurrent: Optional[int] = None,
        current_count: Optional[int] = None,
        queue_size: Optional[int] = None
    ):
        super().__init__(message)
        self.max_concurrent = max_concurrent
        self.current_count = current_count
        self.queue_size = queue_size


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead patterns."""
    max_concurrent: int = 10
    max_wait_ms: int = 0  # 0 = no wait
    queue_size: int = 0  # 0 = no queue
    partition_count: int = 1
    adaptive_min: int = 5
    adaptive_max: int = 50
    adaptive_window: int = 100


@dataclass
class BulkheadStats:
    """Statistics for bulkhead monitoring."""
    name: str
    max_concurrent: int
    current_count: int
    queue_size: int
    total_calls: int
    accepted_calls: int
    rejected_calls: int
    timeout_calls: int
    avg_wait_time_ms: float
    avg_execution_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "current_count": self.current_count,
            "queue_size": self.queue_size,
            "total_calls": self.total_calls,
            "accepted_calls": self.accepted_calls,
            "rejected_calls": self.rejected_calls,
            "timeout_calls": self.timeout_calls,
            "avg_wait_time_ms": self.avg_wait_time_ms,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "utilization": self.current_count / self.max_concurrent if self.max_concurrent > 0 else 0,
            "accept_rate": self.accepted_calls / self.total_calls if self.total_calls > 0 else 1.0
        }


class SemaphoreBulkhead:
    """
    Semaphore-based bulkhead implementation.
    
    Limits concurrent executions using a semaphore.
    Simple and efficient for most use cases.
    
    Features:
    - Configurable concurrent limit
    - Optional wait timeout
    - Metrics collection
    """
    
    def __init__(
        self,
        max_concurrent: int,
        name: str = "semaphore_bulkhead",
        max_wait_ms: int = 0
    ):
        self.max_concurrent = max_concurrent
        self.name = name
        self.max_wait_ms = max_wait_ms
        
        self._semaphore = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self._current_count = 0
        
        # Metrics
        self._total_calls = 0
        self._accepted_calls = 0
        self._rejected_calls = 0
        self._timeout_calls = 0
        self._wait_times: deque = deque(maxlen=1000)
        self._execution_times: deque = deque(maxlen=1000)
    
    def try_enter(self) -> bool:
        """Try to enter the bulkhead without waiting."""
        with self._lock:
            self._total_calls += 1
            
        acquired = self._semaphore.acquire(blocking=False)
        
        with self._lock:
            if acquired:
                self._current_count += 1
                self._accepted_calls += 1
            else:
                self._rejected_calls += 1
        
        return acquired
    
    def enter(self, timeout_ms: Optional[int] = None) -> bool:
        """
        Enter the bulkhead with optional timeout.
        
        Args:
            timeout_ms: Maximum time to wait (None = use default)
            
        Returns:
            True if entered, False if timeout
        """
        timeout_ms = timeout_ms if timeout_ms is not None else self.max_wait_ms
        timeout = timeout_ms / 1000.0 if timeout_ms > 0 else None
        
        with self._lock:
            self._total_calls += 1
        
        start_time = time.time()
        acquired = self._semaphore.acquire(blocking=timeout is not None, timeout=timeout)
        wait_time = (time.time() - start_time) * 1000
        
        with self._lock:
            if acquired:
                self._current_count += 1
                self._accepted_calls += 1
                self._wait_times.append(wait_time)
            else:
                self._timeout_calls += 1
        
        return acquired
    
    def exit(self) -> None:
        """Exit the bulkhead, releasing the permit."""
        with self._lock:
            self._current_count -= 1
        self._semaphore.release()
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        timeout_ms: Optional[int] = None,
        **kwargs
    ) -> T:
        """
        Execute a function within the bulkhead.
        
        Args:
            func: Function to execute
            timeout_ms: Maximum wait time to enter bulkhead
            
        Returns:
            Function result
            
        Raises:
            BulkheadFullException: If bulkhead is at capacity
        """
        if not self.enter(timeout_ms):
            raise BulkheadFullException(
                max_concurrent=self.max_concurrent,
                current_count=self._current_count
            )
        
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            exec_time = (time.time() - start_time) * 1000
            with self._lock:
                self._execution_times.append(exec_time)
            self.exit()
    
    def get_stats(self) -> BulkheadStats:
        """Get bulkhead statistics."""
        with self._lock:
            avg_wait = (
                sum(self._wait_times) / len(self._wait_times)
                if self._wait_times else 0
            )
            avg_exec = (
                sum(self._execution_times) / len(self._execution_times)
                if self._execution_times else 0
            )
            
            return BulkheadStats(
                name=self.name,
                max_concurrent=self.max_concurrent,
                current_count=self._current_count,
                queue_size=0,
                total_calls=self._total_calls,
                accepted_calls=self._accepted_calls,
                rejected_calls=self._rejected_calls,
                timeout_calls=self._timeout_calls,
                avg_wait_time_ms=avg_wait,
                avg_execution_time_ms=avg_exec
            )


class QueueBulkhead:
    """
    Queue-based bulkhead implementation.
    
    Queues requests when at capacity, with configurable queue size.
    Provides better request handling under load.
    
    Features:
    - Bounded queue for waiting requests
    - FIFO ordering
    - Configurable queue timeout
    """
    
    def __init__(
        self,
        max_concurrent: int,
        queue_size: int = 10,
        name: str = "queue_bulkhead",
        max_wait_ms: int = 5000
    ):
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self.name = name
        self.max_wait_ms = max_wait_ms
        
        self._semaphore = threading.Semaphore(max_concurrent)
        self._queue_lock = threading.Lock()
        self._current_queue_size = 0
        self._current_count = 0
        
        # Metrics
        self._total_calls = 0
        self._accepted_calls = 0
        self._rejected_calls = 0
        self._timeout_calls = 0
        self._wait_times: deque = deque(maxlen=1000)
        self._execution_times: deque = deque(maxlen=1000)
    
    def try_enter(self) -> bool:
        """Try to enter without queuing."""
        with self._queue_lock:
            self._total_calls += 1
            
        acquired = self._semaphore.acquire(blocking=False)
        
        with self._queue_lock:
            if acquired:
                self._current_count += 1
                self._accepted_calls += 1
            else:
                self._rejected_calls += 1
        
        return acquired
    
    def enter(self, timeout_ms: Optional[int] = None) -> bool:
        """
        Enter with queuing support.
        
        Args:
            timeout_ms: Maximum time to wait in queue
            
        Returns:
            True if entered, False if timeout or queue full
        """
        timeout_ms = timeout_ms if timeout_ms is not None else self.max_wait_ms
        timeout = timeout_ms / 1000.0
        
        with self._queue_lock:
            self._total_calls += 1
            
            # Check if queue is full
            if self._current_queue_size >= self.queue_size:
                self._rejected_calls += 1
                return False
            
            self._current_queue_size += 1
        
        start_time = time.time()
        
        try:
            acquired = self._semaphore.acquire(blocking=True, timeout=timeout)
            wait_time = (time.time() - start_time) * 1000
            
            with self._queue_lock:
                self._current_queue_size -= 1
                
                if acquired:
                    self._current_count += 1
                    self._accepted_calls += 1
                    self._wait_times.append(wait_time)
                else:
                    self._timeout_calls += 1
            
            return acquired
            
        except Exception:
            with self._queue_lock:
                self._current_queue_size -= 1
            raise
    
    def exit(self) -> None:
        """Exit the bulkhead."""
        with self._queue_lock:
            self._current_count -= 1
        self._semaphore.release()
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        timeout_ms: Optional[int] = None,
        **kwargs
    ) -> T:
        """Execute function with queue-based bulkhead."""
        if not self.enter(timeout_ms):
            raise BulkheadFullException(
                max_concurrent=self.max_concurrent,
                current_count=self._current_count,
                queue_size=self._current_queue_size
            )
        
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            exec_time = (time.time() - start_time) * 1000
            with self._queue_lock:
                self._execution_times.append(exec_time)
            self.exit()
    
    def get_stats(self) -> BulkheadStats:
        """Get bulkhead statistics."""
        with self._queue_lock:
            avg_wait = (
                sum(self._wait_times) / len(self._wait_times)
                if self._wait_times else 0
            )
            avg_exec = (
                sum(self._execution_times) / len(self._execution_times)
                if self._execution_times else 0
            )
            
            return BulkheadStats(
                name=self.name,
                max_concurrent=self.max_concurrent,
                current_count=self._current_count,
                queue_size=self._current_queue_size,
                total_calls=self._total_calls,
                accepted_calls=self._accepted_calls,
                rejected_calls=self._rejected_calls,
                timeout_calls=self._timeout_calls,
                avg_wait_time_ms=avg_wait,
                avg_execution_time_ms=avg_exec
            )


class PartitionedBulkhead:
    """
    Partitioned bulkhead for workload isolation.
    
    Separates different types of workloads into isolated partitions,
    preventing one workload type from affecting others.
    
    Features:
    - Multiple isolated partitions
    - Per-partition limits
    - Workload type routing
    """
    
    def __init__(
        self,
        partitions: Dict[str, int],
        name: str = "partitioned_bulkhead"
    ):
        """
        Initialize partitioned bulkhead.
        
        Args:
            partitions: Dict mapping partition name to max concurrent
        """
        self.name = name
        self.partitions: Dict[str, SemaphoreBulkhead] = {}
        
        for partition_name, max_concurrent in partitions.items():
            self.partitions[partition_name] = SemaphoreBulkhead(
                max_concurrent=max_concurrent,
                name=f"{name}_{partition_name}"
            )
        
        self._default_partition = list(partitions.keys())[0] if partitions else None
    
    def enter(
        self,
        partition: Optional[str] = None,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """Enter a specific partition."""
        partition = partition or self._default_partition
        
        if partition not in self.partitions:
            raise ValueError(f"Unknown partition: {partition}")
        
        return self.partitions[partition].enter(timeout_ms)

    def try_enter(self, partition: Optional[str] = None) -> bool:
        """Try to enter a specific partition without waiting."""
        partition = partition or self._default_partition

        if partition not in self.partitions:
            raise ValueError(f"Unknown partition: {partition}")

        return self.partitions[partition].try_enter()
    
    def exit(self, partition: Optional[str] = None) -> None:
        """Exit a partition."""
        partition = partition or self._default_partition
        
        if partition in self.partitions:
            self.partitions[partition].exit()
    
    def execute(
        self,
        func: Callable[..., T],
        partition: Optional[str] = None,
        *args,
        **kwargs
    ) -> T:
        """Execute function in specific partition."""
        partition = partition or self._default_partition
        
        if partition not in self.partitions:
            raise ValueError(f"Unknown partition: {partition}")
        
        return self.partitions[partition].execute(func, *args, **kwargs)
    
    def get_partition_stats(self, partition: str) -> Optional[BulkheadStats]:
        """Get stats for a specific partition."""
        if partition in self.partitions:
            return self.partitions[partition].get_stats()
        return None
    
    def get_all_stats(self) -> Dict[str, BulkheadStats]:
        """Get stats for all partitions."""
        return {
            name: bulkhead.get_stats()
            for name, bulkhead in self.partitions.items()
        }
    
    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all partitions."""
        all_stats = self.get_all_stats()
        
        total_calls = sum(s.total_calls for s in all_stats.values())
        accepted_calls = sum(s.accepted_calls for s in all_stats.values())
        rejected_calls = sum(s.rejected_calls for s in all_stats.values())
        
        return {
            "name": self.name,
            "type": "partitioned",
            "partition_count": len(self.partitions),
            "total_calls": total_calls,
            "accepted_calls": accepted_calls,
            "rejected_calls": rejected_calls,
            "accept_rate": accepted_calls / total_calls if total_calls > 0 else 1.0,
            "partitions": {k: v.to_dict() for k, v in all_stats.items()}
        }


class AdaptiveBulkhead:
    """
    Adaptive bulkhead with ML-based capacity adjustment.
    
    Automatically adjusts concurrent limit based on:
    - Response times
    - Error rates
    - System load
    
    Uses EWMA for smooth adjustments.
    """
    
    def __init__(
        self,
        initial_capacity: int,
        min_capacity: int,
        max_capacity: int,
        name: str = "adaptive_bulkhead",
        adjustment_window: int = 100
    ):
        self.current_capacity = initial_capacity
        self.min_capacity = min_capacity
        self.max_capacity = max_capacity
        self.name = name
        self.adjustment_window = adjustment_window
        
        # Internal bulkhead
        self._bulkhead = SemaphoreBulkhead(
            max_concurrent=initial_capacity,
            name=f"{name}_internal"
        )
        
        self._lock = threading.Lock()
        
        # Metrics for adaptation
        self._response_times: deque = deque(maxlen=adjustment_window)
        self._error_count = 0
        self._success_count = 0
        
        # EWMA parameters
        self.ewma_response_time = 0.0
        self.ewma_error_rate = 0.0
        self.alpha = 0.1
        
        # Target response time (ms)
        self.target_response_time = 100.0
    
    def _update_ewma(self, response_time: float, is_error: bool) -> None:
        """Update EWMA metrics."""
        self.ewma_response_time = (
            self.alpha * response_time + 
            (1 - self.alpha) * self.ewma_response_time
        )
        
        error_value = 1.0 if is_error else 0.0
        self.ewma_error_rate = (
            self.alpha * error_value + 
            (1 - self.alpha) * self.ewma_error_rate
        )
    
    def _adjust_capacity(self) -> None:
        """Adjust capacity based on metrics."""
        # Calculate adjustment factor
        if self.ewma_error_rate > 0.1:
            # High error rate - reduce capacity
            adjustment = 0.9 - (self.ewma_error_rate * 0.3)
        elif self.ewma_response_time > self.target_response_time * 2:
            # Very slow - reduce capacity
            adjustment = 0.85
        elif self.ewma_response_time > self.target_response_time:
            # Slow - reduce capacity slightly
            adjustment = 0.95
        elif self.ewma_response_time < self.target_response_time * 0.5:
            # Fast - increase capacity
            adjustment = 1.1
        else:
            # Normal - no adjustment
            adjustment = 1.0
        
        # Apply adjustment
        new_capacity = int(self.current_capacity * adjustment)
        new_capacity = max(self.min_capacity, min(self.max_capacity, new_capacity))
        
        if new_capacity != self.current_capacity:
            self.current_capacity = new_capacity
            self._bulkhead = SemaphoreBulkhead(
                max_concurrent=new_capacity,
                name=f"{self.name}_internal"
            )
            logger.info(
                f"Adaptive bulkhead '{self.name}' adjusted capacity to {new_capacity}"
            )
    
    def enter(self, timeout_ms: Optional[int] = None) -> bool:
        """Enter the adaptive bulkhead."""
        return self._bulkhead.enter(timeout_ms)
    
    def exit(self) -> None:
        """Exit the bulkhead."""
        self._bulkhead.exit()
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with adaptive bulkhead."""
        if not self.enter():
            raise BulkheadFullException(
                max_concurrent=self.current_capacity,
                current_count=self._bulkhead._current_count
            )
        
        start_time = time.time()
        is_error = False
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception:
            is_error = True
            raise
        finally:
            response_time = (time.time() - start_time) * 1000
            
            with self._lock:
                self._response_times.append(response_time)
                if is_error:
                    self._error_count += 1
                else:
                    self._success_count += 1
                
                self._update_ewma(response_time, is_error)
                
                # Periodic adjustment
                total = self._error_count + self._success_count
                if total % self.adjustment_window == 0:
                    self._adjust_capacity()
            
            self.exit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adaptive bulkhead statistics."""
        with self._lock:
            return {
                "name": self.name,
                "type": "adaptive",
                "current_capacity": self.current_capacity,
                "min_capacity": self.min_capacity,
                "max_capacity": self.max_capacity,
                "ewma_response_time": self.ewma_response_time,
                "ewma_error_rate": self.ewma_error_rate,
                "target_response_time": self.target_response_time,
                "internal_bulkhead": self._bulkhead.get_stats().to_dict()
            }


class BulkheadRegistry:
    """
    Registry for managing multiple bulkheads.
    
    Provides centralized management and monitoring.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._bulkheads: Dict[str, Any] = {}
                    cls._instance._registry_lock = threading.Lock()
        return cls._instance
    
    def register(
        self,
        name: str,
        bulkhead: Union[
            SemaphoreBulkhead,
            QueueBulkhead,
            PartitionedBulkhead,
            AdaptiveBulkhead
        ]
    ) -> None:
        """Register a bulkhead."""
        with self._registry_lock:
            self._bulkheads[name] = bulkhead
    
    def get(self, name: str) -> Optional[Any]:
        """Get a bulkhead by name."""
        with self._registry_lock:
            return self._bulkheads.get(name)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all registered bulkheads."""
        with self._registry_lock:
            result = {}
            for name, bulkhead in self._bulkheads.items():
                stats = bulkhead.get_stats()
                if isinstance(stats, BulkheadStats):
                    result[name] = stats.to_dict()
                else:
                    result[name] = stats
            return result
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all bulkheads."""
        stats = self.get_all_stats()
        
        issues = []
        for name, stat in stats.items():
            if isinstance(stat, dict):
                utilization = stat.get("utilization", 0)
                if utilization > 0.9:
                    issues.append({
                        "bulkhead": name,
                        "issue": "high_utilization",
                        "value": utilization
                    })
                
                reject_rate = (
                    stat.get("rejected_calls", 0) /
                    max(1, stat.get("total_calls", 0))
                )
                if reject_rate > 0.1:
                    issues.append({
                        "bulkhead": name,
                        "issue": "high_reject_rate",
                        "value": reject_rate
                    })
        
        return {
            "healthy": len(issues) == 0,
            "bulkhead_count": len(self._bulkheads),
            "issues": issues
        }


def bulkhead(
    max_concurrent: int,
    name: Optional[str] = None,
    bulkhead_type: BulkheadType = BulkheadType.SEMAPHORE,
    **kwargs
):
    """
    Decorator for applying bulkhead to functions.
    
    Args:
        max_concurrent: Maximum concurrent executions
        name: Bulkhead name
        bulkhead_type: Type of bulkhead to use
        **kwargs: Additional bulkhead configuration
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        _name = name or f"bulkhead_{func.__name__}"
        
        if bulkhead_type == BulkheadType.SEMAPHORE:
            bh = SemaphoreBulkhead(
                max_concurrent=max_concurrent,
                name=_name,
                max_wait_ms=kwargs.get("max_wait_ms", 0)
            )
        elif bulkhead_type == BulkheadType.QUEUE:
            bh = QueueBulkhead(
                max_concurrent=max_concurrent,
                queue_size=kwargs.get("queue_size", 10),
                name=_name,
                max_wait_ms=kwargs.get("max_wait_ms", 5000)
            )
        else:
            bh = SemaphoreBulkhead(
                max_concurrent=max_concurrent,
                name=_name
            )
        
        # Register in global registry
        BulkheadRegistry().register(_name, bh)
        
        def wrapper(*args, **kwargs_inner) -> T:
            return bh.execute(func, *args, **kwargs_inner)
        
        wrapper.bulkhead = bh
        return wrapper
    
    return decorator


# Alias for backwards-compat with tests that import `bulkhead_decorator`
bulkhead_decorator = bulkhead

__all__ = [
    "BulkheadType",
    "BulkheadConfig",
    "BulkheadStats",
    "BulkheadFullException",
    "SemaphoreBulkhead",
    "QueueBulkhead",
    "PartitionedBulkhead",
    "AdaptiveBulkhead",
    "BulkheadRegistry",
    "bulkhead",
    "bulkhead_decorator",
]
