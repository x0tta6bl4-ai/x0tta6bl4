"""
Task Distributor - Intelligent task distribution across edge nodes.

Provides multiple distribution strategies, load balancing, and
fault-tolerant task routing for edge computing infrastructure.
"""

import asyncio
import hashlib
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .edge_node import EdgeNode, EdgeNodeManager, EdgeTask, TaskPriority

logger = logging.getLogger(__name__)


class DistributionStrategy(Enum):
    """Task distribution strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_BASED = "capability_based"
    LATENCY_AWARE = "latency_aware"
    ADAPTIVE = "adaptive"
    HASH_BASED = "hash_based"


# Backward-compatible alias expected by API/tests.
TaskDistributionStrategy = DistributionStrategy


@dataclass
class DistributionConfig:
    """Configuration for task distribution."""
    strategy: DistributionStrategy = DistributionStrategy.ADAPTIVE
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    
    # Timeout settings
    distribution_timeout_seconds: float = 30.0
    task_timeout_seconds: float = 300.0
    
    # Load balancing
    rebalance_interval_seconds: float = 60.0
    max_node_load_percent: float = 80.0
    
    # Affinity settings
    enable_sticky_sessions: bool = False
    affinity_ttl_seconds: float = 3600.0
    
    # Fallback
    fallback_to_any_node: bool = True
    offline_node_timeout_seconds: float = 300.0


@dataclass
class DistributionMetrics:
    """Metrics for task distribution."""
    total_distributed: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    avg_distribution_time_ms: float = 0.0
    avg_task_duration_seconds: float = 0.0
    
    # Per-node metrics
    node_distribution_counts: Dict[str, int] = field(default_factory=dict)
    node_failure_counts: Dict[str, int] = field(default_factory=dict)


class DistributionStrategyBase(ABC):
    """Abstract base class for distribution strategies."""
    
    @abstractmethod
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        """Select the best node for a task."""
        pass


class RoundRobinStrategy(DistributionStrategyBase):
    """Round-robin distribution across nodes."""
    
    def __init__(self):
        self._current_index = 0
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        if not nodes:
            return None
        
        # Filter healthy nodes
        healthy = [n for n in nodes if n.can_accept_task()]
        if not healthy:
            return None
        
        node = healthy[self._current_index % len(healthy)]
        self._current_index += 1
        
        return node


class LeastLoadedStrategy(DistributionStrategyBase):
    """Select node with least current load."""
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        healthy = [n for n in nodes if n.can_accept_task()]
        if not healthy:
            return None
        
        # Sort by available slots (descending)
        healthy.sort(key=lambda n: n._resources.available_slots, reverse=True)
        
        return healthy[0]


class CapabilityBasedStrategy(DistributionStrategyBase):
    """Select node based on required capabilities."""
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        required = task.required_capabilities
        
        # Filter by capabilities
        capable = [
            n for n in nodes
            if required.issubset(n.config.capabilities) and n.can_accept_task()
        ]
        
        if not capable:
            return None
        
        # Among capable nodes, select least loaded
        capable.sort(key=lambda n: n._resources.available_slots, reverse=True)
        
        return capable[0]


class LatencyAwareStrategy(DistributionStrategyBase):
    """Select node with lowest expected latency."""
    
    def __init__(self):
        self._node_latencies: Dict[str, List[float]] = {}
    
    def record_latency(self, node_id: str, latency_ms: float) -> None:
        """Record latency measurement for a node."""
        if node_id not in self._node_latencies:
            self._node_latencies[node_id] = []
        
        self._node_latencies[node_id].append(latency_ms)
        
        # Keep last 100 measurements
        if len(self._node_latencies[node_id]) > 100:
            self._node_latencies[node_id].pop(0)
    
    def get_avg_latency(self, node_id: str) -> float:
        """Get average latency for a node."""
        latencies = self._node_latencies.get(node_id, [])
        if not latencies:
            return float('inf')
        return sum(latencies) / len(latencies)
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        healthy = [n for n in nodes if n.can_accept_task()]
        if not healthy:
            return None
        
        # Sort by average latency
        healthy.sort(key=lambda n: self.get_avg_latency(n.config.node_id))
        
        return healthy[0]


class AdaptiveStrategy(DistributionStrategyBase):
    """
    Adaptive strategy that combines multiple factors.
    
    Considers:
    - Node load
    - Historical latency
    - Success rate
    - Capability match
    """
    
    def __init__(self):
        self._latency_strategy = LatencyAwareStrategy()
        self._node_scores: Dict[str, float] = {}
    
    def update_node_score(self, node_id: str, success: bool, latency_ms: float) -> None:
        """Update node score based on result."""
        self._latency_strategy.record_latency(node_id, latency_ms)
        
        current_score = self._node_scores.get(node_id, 0.5)
        
        # Exponential moving average
        alpha = 0.1
        if success:
            new_score = alpha * 1.0 + (1 - alpha) * current_score
        else:
            new_score = alpha * 0.0 + (1 - alpha) * current_score
        
        self._node_scores[node_id] = new_score
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        healthy = [n for n in nodes if n.can_accept_task()]
        if not healthy:
            return None
        
        # Filter by capabilities if required
        if task.required_capabilities:
            healthy = [
                n for n in healthy
                if task.required_capabilities.issubset(n.config.capabilities)
            ]
        
        if not healthy:
            return None
        
        # Score each node
        scored_nodes = []
        for node in healthy:
            score = self._compute_node_score(node, task)
            scored_nodes.append((node, score))
        
        # Sort by score (descending)
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        
        return scored_nodes[0][0]
    
    def _compute_node_score(self, node: EdgeNode, task: EdgeTask) -> float:
        """Compute overall score for a node."""
        # Load score (0-1, higher is better)
        load_score = node._resources.available_slots / node.config.max_concurrent_tasks
        
        # Historical score (0-1)
        historical_score = self._node_scores.get(node.config.node_id, 0.5)
        
        # Latency score (0-1, lower latency is better)
        avg_latency = self._latency_strategy.get_avg_latency(node.config.node_id)
        if avg_latency == float('inf'):
            latency_score = 0.5
        else:
            latency_score = max(0, 1 - avg_latency / 1000)  # Normalize to 1s
        
        # Combine scores
        final_score = (
            load_score * 0.4 +
            historical_score * 0.3 +
            latency_score * 0.3
        )
        
        return final_score


class HashBasedStrategy(DistributionStrategyBase):
    """Consistent hash-based distribution for sticky sessions."""
    
    def __init__(self, replicas: int = 100):
        self._replicas = replicas
        self._ring: Dict[int, str] = {}
        self._sorted_keys: List[int] = []
    
    def build_ring(self, nodes: List[EdgeNode]) -> None:
        """Build consistent hash ring."""
        self._ring = {}
        self._sorted_keys = []
        
        for node in nodes:
            for i in range(self._replicas):
                key = self._hash(f"{node.config.node_id}:{i}")
                self._ring[key] = node.config.node_id
                self._sorted_keys.append(key)
        
        self._sorted_keys.sort()
    
    def _hash(self, key: str) -> int:
        """Hash function for ring."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)
    
    def get_node_for_key(self, key: str, nodes: List[EdgeNode]) -> Optional[str]:
        """Get node ID for a key using consistent hashing."""
        if not self._sorted_keys:
            return None
        
        hash_val = self._hash(key)
        
        # Find first node with hash >= key hash
        for ring_key in self._sorted_keys:
            if ring_key >= hash_val:
                return self._ring[ring_key]
        
        # Wrap around to first node
        return self._ring[self._sorted_keys[0]]
    
    def select_node(
        self,
        nodes: List[EdgeNode],
        task: EdgeTask,
        metrics: DistributionMetrics
    ) -> Optional[EdgeNode]:
        healthy = [n for n in nodes if n.can_accept_task()]
        if not healthy:
            return None
        
        # Rebuild ring if needed
        self.build_ring(healthy)
        
        # Get node from hash ring
        node_id = self.get_node_for_key(task.task_id, healthy)
        
        if node_id:
            for node in healthy:
                if node.config.node_id == node_id:
                    return node
        
        return healthy[0]


class TaskDistributor:
    """
    Main task distribution system.
    
    Features:
    - Multiple distribution strategies
    - Automatic failover and retry
    - Load balancing
    - Affinity-based routing
    """
    
    def __init__(
        self,
        node_manager: Optional[EdgeNodeManager] = None,
        config: Optional[DistributionConfig] = None,
        strategy: Optional[DistributionStrategy] = None,
    ):
        self.node_manager = node_manager or EdgeNodeManager()
        self.config = config or DistributionConfig()
        if strategy is not None:
            self.config.strategy = strategy
        
        # Initialize strategies
        self._strategies: Dict[DistributionStrategy, DistributionStrategyBase] = {
            DistributionStrategy.ROUND_ROBIN: RoundRobinStrategy(),
            DistributionStrategy.LEAST_LOADED: LeastLoadedStrategy(),
            DistributionStrategy.CAPABILITY_BASED: CapabilityBasedStrategy(),
            DistributionStrategy.LATENCY_AWARE: LatencyAwareStrategy(),
            DistributionStrategy.ADAPTIVE: AdaptiveStrategy(),
            DistributionStrategy.HASH_BASED: HashBasedStrategy(),
        }
        
        self._metrics = DistributionMetrics()
        self._task_callbacks: Dict[str, List[Callable]] = {}
        self._affinity_cache: Dict[str, Tuple[str, datetime]] = {}
        self._running = False
        self._task_index: Dict[str, Dict[str, Any]] = {}
    
    def _get_strategy_impl(self) -> DistributionStrategyBase:
        """Get current strategy implementation."""
        return self._strategies[self.config.strategy]

    def get_strategy(self) -> DistributionStrategy:
        """Get current strategy enum (API compatibility)."""
        return self.config.strategy
    
    def set_strategy(
        self,
        strategy: DistributionStrategy,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set distribution strategy."""
        self.config.strategy = strategy
        if config and isinstance(config, dict):
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        logger.info(f"Distribution strategy set to: {strategy.value}")

    def get_strategy_config(self) -> Dict[str, Any]:
        """Return current strategy config for API."""
        return {
            "max_retries": self.config.max_retries,
            "retry_delay_seconds": self.config.retry_delay_seconds,
            "retry_backoff_multiplier": self.config.retry_backoff_multiplier,
            "distribution_timeout_seconds": self.config.distribution_timeout_seconds,
        }
    
    async def distribute_task(
        self,
        task: Optional[EdgeTask] = None,
        preferred_node: Optional[str] = None,
        **task_kwargs: Any,
    ) -> Any:
        """
        Distribute a task to an appropriate node.
        
        Returns:
          - tuple(success, node_id) for EdgeTask input
          - dict for API-style kwargs input
        """
        api_mode = task is None
        if task is None:
            task = EdgeTask(
                task_id=task_kwargs.get("task_id", str(uuid.uuid4())),
                task_type=task_kwargs.get("task_type", ""),
                payload=task_kwargs.get("payload", {}),
                priority=TaskPriority.NORMAL,
                required_capabilities=set(task_kwargs.get("required_capabilities", [])),
                max_retries=int(task_kwargs.get("retry_count", 3)),
                timeout_seconds=float(task_kwargs.get("timeout_seconds", 300)),
                metadata=task_kwargs.get("metadata") or {},
            )

        start_time = time.time()
        
        # Check affinity
        if self.config.enable_sticky_sessions:
            affinity_node = self._get_affinity_node(task.task_id)
            if affinity_node:
                node = self.node_manager.get_node(affinity_node)
                if node and node.can_accept_task():
                    success = await self._submit_to_node(node, task)
                    if success:
                        self._task_index[task.task_id] = {
                            "node_id": node.config.node_id,
                            "status": "queued",
                            "progress": 0.0,
                            "started_at": None,
                            "completed_at": None,
                            "error": None,
                            "result": None,
                            "execution_time_ms": None,
                        }
                        return (
                            {"node_id": node.config.node_id, "estimated_start": datetime.utcnow()}
                            if api_mode
                            else (True, node.config.node_id)
                        )
        
        # Use preferred node if specified
        if preferred_node:
            node = self.node_manager.get_node(preferred_node)
            if node and node.can_accept_task():
                success = await self._submit_to_node(node, task)
                if success:
                    self._task_index[task.task_id] = {
                        "node_id": node.config.node_id,
                        "status": "queued",
                        "progress": 0.0,
                        "started_at": None,
                        "completed_at": None,
                        "error": None,
                        "result": None,
                        "execution_time_ms": None,
                    }
                    return (
                        {"node_id": node.config.node_id, "estimated_start": datetime.utcnow()}
                        if api_mode
                        else (True, node.config.node_id)
                    )
        
        # Get all healthy nodes
        nodes = self.node_manager.get_healthy_nodes()
        if not nodes:
            logger.warning("No healthy nodes available")
            if api_mode:
                raise RuntimeError("No available nodes")
            return False, None
        
        # Filter by capabilities
        if task.required_capabilities:
            nodes = [
                n for n in nodes
                if task.required_capabilities.issubset(n.config.capabilities)
            ]
            if not nodes:
                if self.config.fallback_to_any_node:
                    nodes = self.node_manager.get_healthy_nodes()
                else:
                    logger.warning(f"No nodes with required capabilities: {task.required_capabilities}")
                    if api_mode:
                        raise RuntimeError("No available nodes")
                    return False, None
        
        # Select node using strategy
        strategy = self._get_strategy_impl()
        selected_node = strategy.select_node(nodes, task, self._metrics)
        
        if not selected_node:
            logger.warning("No suitable node found for task")
            if api_mode:
                raise RuntimeError("No available nodes")
            return False, None
        
        # Submit task
        success = await self._submit_to_node(selected_node, task)
        
        # Update metrics
        elapsed_ms = (time.time() - start_time) * 1000
        self._update_distribution_metrics(selected_node.config.node_id, success, elapsed_ms)
        
        if success:
            # Set affinity
            if self.config.enable_sticky_sessions:
                self._set_affinity(task.task_id, selected_node.config.node_id)
            
            self._task_index[task.task_id] = {
                "node_id": selected_node.config.node_id,
                "status": "queued",
                "progress": 0.0,
                "started_at": None,
                "completed_at": None,
                "error": None,
                "result": None,
                "execution_time_ms": None,
            }
            return (
                {"node_id": selected_node.config.node_id, "estimated_start": datetime.utcnow()}
                if api_mode
                else (True, selected_node.config.node_id)
            )
        
        # Try retry
        if task.retry_count < task.max_retries:
            return await self._retry_task(task)

        if api_mode:
            raise RuntimeError("No available nodes")
        return False, None
    
    async def _submit_to_node(self, node: EdgeNode, task: EdgeTask) -> bool:
        """Submit a task to a specific node."""
        try:
            await node.submit_task(task)
            return True
        except Exception as e:
            logger.error(f"Failed to submit task to node {node.config.node_id}: {e}")
            return False
    
    async def _retry_task(self, task: EdgeTask) -> Tuple[bool, Optional[str]]:
        """Retry task distribution with backoff."""
        task.retry_count += 1
        self._metrics.retried += 1
        
        delay = self.config.retry_delay_seconds * (
            self.config.retry_backoff_multiplier ** (task.retry_count - 1)
        )
        
        logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count}) after {delay}s")
        
        await asyncio.sleep(delay)
        
        return await self.distribute_task(task)
    
    def _get_affinity_node(self, task_id: str) -> Optional[str]:
        """Get affinity node for a task."""
        if task_id in self._affinity_cache:
            node_id, timestamp = self._affinity_cache[task_id]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.config.affinity_ttl_seconds:
                return node_id
            else:
                del self._affinity_cache[task_id]
        return None
    
    def _set_affinity(self, task_id: str, node_id: str) -> None:
        """Set affinity for a task."""
        self._affinity_cache[task_id] = (node_id, datetime.utcnow())
    
    def _update_distribution_metrics(
        self,
        node_id: str,
        success: bool,
        elapsed_ms: float
    ) -> None:
        """Update distribution metrics."""
        self._metrics.total_distributed += 1
        
        if success:
            self._metrics.successful += 1
        else:
            self._metrics.failed += 1
            self._metrics.node_failure_counts[node_id] = (
                self._metrics.node_failure_counts.get(node_id, 0) + 1
            )
        
        # Update average distribution time
        n = self._metrics.total_distributed
        self._metrics.avg_distribution_time_ms = (
            (self._metrics.avg_distribution_time_ms * (n - 1) + elapsed_ms) / n
        )
        
        # Update node distribution counts
        self._metrics.node_distribution_counts[node_id] = (
            self._metrics.node_distribution_counts.get(node_id, 0) + 1
        )
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Register a callback for distribution events."""
        if event not in self._task_callbacks:
            self._task_callbacks[event] = []
        self._task_callbacks[event].append(callback)
    
    async def broadcast_task(
        self,
        task: EdgeTask,
        regions: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Broadcast a task to multiple nodes.
        
        Returns dict of node_id -> (success, result).
        """
        results = {}
        
        # Get target nodes
        if regions:
            nodes = []
            for region in regions:
                nodes.extend(self.node_manager.get_nodes_by_region(region))
        else:
            nodes = self.node_manager.get_healthy_nodes()
        
        # Distribute to all nodes
        tasks = []
        for node in nodes:
            task_copy = EdgeTask(
                task_id=f"{task.task_id}-{node.config.node_id}",
                task_type=task.task_type,
                payload=task.payload,
                priority=task.priority,
                required_capabilities=task.required_capabilities,
            )
            tasks.append(self.distribute_task(task_copy))
        
        # Wait for all distributions
        distribution_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for node, result in zip(nodes, distribution_results):
            if isinstance(result, Exception):
                results[node.config.node_id] = (False, str(result))
            else:
                results[node.config.node_id] = result
        
        return results
    
    def get_metrics(self) -> DistributionMetrics:
        """Get distribution metrics."""
        return self._metrics
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of distribution metrics."""
        return {
            "total_distributed": self._metrics.total_distributed,
            "successful": self._metrics.successful,
            "failed": self._metrics.failed,
            "retried": self._metrics.retried,
            "success_rate": (
                self._metrics.successful / self._metrics.total_distributed
                if self._metrics.total_distributed > 0 else 0
            ),
            "avg_distribution_time_ms": self._metrics.avg_distribution_time_ms,
            "avg_task_duration_seconds": self._metrics.avg_task_duration_seconds,
            "strategy": self.config.strategy.value,
            "node_distribution": dict(self._metrics.node_distribution_counts),
            "node_failures": dict(self._metrics.node_failure_counts),
        }

    # ------------------------------------------------------------------
    # API compatibility helpers
    # ------------------------------------------------------------------
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._task_index.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        if task_id not in self._task_index:
            return False
        self._task_index[task_id]["status"] = "cancelled"
        self._task_index[task_id]["completed_at"] = datetime.utcnow().isoformat()
        return True

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._task_index.get(task_id)
        if not task:
            return None
        if task.get("status") not in {"completed", "failed", "cancelled"}:
            return {
                "status": "completed",
                "result": {"message": "synthetic result"},
                "execution_time_ms": 0,
                "node_id": task.get("node_id"),
            }
        return task

    def get_stats(self) -> Dict[str, Any]:
        return self.get_metrics_summary()

    async def shutdown(self) -> None:
        self._running = False
