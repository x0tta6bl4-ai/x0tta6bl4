"""
Advanced Federated Learning Orchestrator Enhancements

Provides enterprise-grade orchestration with:
- Adaptive resource management
- Dynamic scaling policies
- Performance prediction and optimization
- Fault tolerance and recovery
- Load forecasting and balancing
- Cluster topology optimization
"""

import asyncio
import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ScalingPolicy(Enum):
    """Scaling policies for FL orchestration"""

    CONSERVATIVE = "conservative"  # Scale up by 10%, down by 5%
    BALANCED = "balanced"  # Scale up by 25%, down by 10%
    AGGRESSIVE = "aggressive"  # Scale up by 50%, down by 25%
    AUTO = "auto"  # Automatically adjust based on metrics


class ResourceMetric(Enum):
    """Resource metrics for scaling decisions"""

    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK_IO = "disk_io"
    TASK_QUEUE = "task_queue"
    MODEL_SIZE = "model_size"


@dataclass
class PerformanceMetrics:
    """Performance metrics for an FL round"""

    round_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    nodes_participated: int = 0
    aggregation_time_ms: float = 0.0
    network_time_ms: float = 0.0
    computation_time_ms: float = 0.0
    total_time_ms: float = 0.0
    model_accuracy: float = 0.0
    convergence_speed: float = 0.0
    stragglers_count: int = 0
    failed_nodes: int = 0

    def calculate_efficiency(self) -> float:
        """Calculate round efficiency (0-1)"""
        if self.total_time_ms <= 0:
            return 0.0

        useful_time = self.computation_time_ms
        return min(1.0, useful_time / self.total_time_ms)


@dataclass
class ResourceUtilization:
    """Resource utilization snapshot"""

    timestamp: datetime
    cpu_percent: float  # 0-100
    memory_percent: float  # 0-100
    network_bandwidth_mbps: float
    disk_io_percent: float
    queue_depth: int
    active_tasks: int

    def total_utilization(self) -> float:
        """Calculate weighted total utilization"""
        weights = {"cpu": 0.3, "memory": 0.3, "network": 0.2, "disk_io": 0.2}

        total = (
            self.cpu_percent * weights["cpu"]
            + self.memory_percent * weights["memory"]
            + min(100, self.network_bandwidth_mbps) * weights["network"]
            + self.disk_io_percent * weights["disk_io"]
        )

        return total / 100


class AdaptiveScaler:
    """
    Adaptive scaling controller for FL orchestrators.

    Makes scaling decisions based on:
    - Resource utilization trends
    - Round completion times
    - Queue depth and latency
    - Node failures and recovery
    """

    def __init__(
        self,
        policy: ScalingPolicy = ScalingPolicy.BALANCED,
        min_nodes: int = 1,
        max_nodes: int = 1000,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.3,
        cooldown_seconds: int = 300,
    ):
        """Initialize adaptive scaler"""
        self.policy = policy
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.cooldown_seconds = cooldown_seconds

        self.current_nodes = min_nodes
        self.last_scale_time = datetime.now()
        self.utilization_history: List[ResourceUtilization] = []
        self.performance_history: List[PerformanceMetrics] = []

    def record_utilization(self, metrics: ResourceUtilization) -> None:
        """Record resource utilization snapshot"""
        self.utilization_history.append(metrics)
        # Keep only last 100 measurements
        if len(self.utilization_history) > 100:
            self.utilization_history = self.utilization_history[-100:]

    def record_performance(self, metrics: PerformanceMetrics) -> None:
        """Record FL round performance"""
        self.performance_history.append(metrics)
        # Keep only last 50 rounds
        if len(self.performance_history) > 50:
            self.performance_history = self.performance_history[-50:]

    def should_scale_up(self) -> bool:
        """Determine if we should scale up"""
        if self.current_nodes >= self.max_nodes:
            return False

        if (
            datetime.now() - self.last_scale_time
        ).total_seconds() < self.cooldown_seconds:
            return False

        if not self.utilization_history:
            return False

        # Check recent utilization trend
        recent_util = [m.total_utilization() for m in self.utilization_history[-10:]]
        avg_util = statistics.mean(recent_util)

        return avg_util > self.scale_up_threshold

    def should_scale_down(self) -> bool:
        """Determine if we should scale down"""
        if self.current_nodes <= self.min_nodes:
            return False

        if (
            datetime.now() - self.last_scale_time
        ).total_seconds() < self.cooldown_seconds:
            return False

        if not self.utilization_history:
            return False

        # Check recent utilization trend
        recent_util = [m.total_utilization() for m in self.utilization_history[-10:]]
        avg_util = statistics.mean(recent_util)

        return avg_util < self.scale_down_threshold

    def get_scaling_factor(self) -> float:
        """
        Get scaling factor based on policy and utilization.

        Returns:
            Factor to multiply current_nodes by (> 1 = scale up, < 1 = scale down)
        """
        if not self.utilization_history:
            return 1.0

        recent_util = statistics.mean(
            [m.total_utilization() for m in self.utilization_history[-10:]]
        )

        factors = {
            ScalingPolicy.CONSERVATIVE: (1.1, 0.95),
            ScalingPolicy.BALANCED: (1.25, 0.9),
            ScalingPolicy.AGGRESSIVE: (1.5, 0.75),
            ScalingPolicy.AUTO: self._calculate_auto_factor(recent_util),
        }

        scale_up_factor, scale_down_factor = factors.get(self.policy, (1.25, 0.9))

        if recent_util > self.scale_up_threshold:
            return scale_up_factor
        elif recent_util < self.scale_down_threshold:
            return scale_down_factor

        return 1.0

    def _calculate_auto_factor(self, utilization: float) -> Tuple[float, float]:
        """Calculate auto scaling factors based on utilization"""
        if utilization > 90:
            return (1.5, 0.75)
        elif utilization > 75:
            return (1.25, 0.9)
        else:
            return (1.1, 0.95)

    def apply_scaling(self) -> Optional[int]:
        """
        Apply scaling decision and return new node count.

        Returns:
            New node count if scaled, None if no scaling
        """
        if self.should_scale_up():
            factor = self.get_scaling_factor()
            new_count = int(self.current_nodes * factor)
            new_count = min(new_count, self.max_nodes)

            if new_count > self.current_nodes:
                self.current_nodes = new_count
                self.last_scale_time = datetime.now()
                logger.info(f"Scaling UP to {self.current_nodes} nodes")
                return self.current_nodes

        elif self.should_scale_down():
            factor = self.get_scaling_factor()
            new_count = int(self.current_nodes * factor)
            new_count = max(new_count, self.min_nodes)

            if new_count < self.current_nodes:
                self.current_nodes = new_count
                self.last_scale_time = datetime.now()
                logger.info(f"Scaling DOWN to {self.current_nodes} nodes")
                return self.current_nodes

        return None


class PerformancePredictor:
    """
    Predicts FL round performance based on historical metrics.

    Provides:
    - Convergence time estimation
    - Resource requirement forecasting
    - Bottleneck identification
    - Optimal parallelization recommendations
    """

    def __init__(self, window_size: int = 20):
        """Initialize predictor with historical window size"""
        self.window_size = window_size
        self.history: List[PerformanceMetrics] = []

    def add_metrics(self, metrics: PerformanceMetrics) -> None:
        """Add new performance metrics"""
        self.history.append(metrics)
        if len(self.history) > self.window_size:
            self.history = self.history[-self.window_size :]

    def predict_next_round_time(self) -> float:
        """
        Predict execution time of next FL round (in ms).

        Returns:
            Predicted round time in milliseconds
        """
        if not self.history:
            return 1000.0  # Default estimate

        recent_times = [m.total_time_ms for m in self.history[-5:]]

        # Use weighted average (more recent = higher weight)
        weights = [i + 1 for i in range(len(recent_times))]
        weighted_avg = sum(t * w for t, w in zip(recent_times, weights)) / sum(weights)

        return weighted_avg

    def predict_convergence_rounds(self, target_accuracy: float) -> int:
        """
        Predict rounds needed to reach target accuracy.

        Args:
            target_accuracy: Target model accuracy (0-1)

        Returns:
            Estimated number of additional rounds
        """
        if len(self.history) < 2:
            return 10  # Default estimate

        # Calculate accuracy improvement rate
        accuracies = [m.model_accuracy for m in self.history[-10:]]

        if len(accuracies) < 2:
            return 10

        # Linear regression on accuracy improvement
        improvements = [
            accuracies[i + 1] - accuracies[i] for i in range(len(accuracies) - 1)
        ]
        avg_improvement = statistics.mean(improvements) if improvements else 0.001

        if avg_improvement <= 0:
            return 100  # Cannot predict convergence

        current_accuracy = accuracies[-1]
        rounds_needed = max(
            0, int((target_accuracy - current_accuracy) / avg_improvement)
        )

        return rounds_needed

    def identify_bottlenecks(self) -> Dict[str, float]:
        """
        Identify performance bottlenecks.

        Returns:
            Dict mapping bottleneck type to severity (0-1)
        """
        if not self.history:
            return {}

        recent = self.history[-10:]

        bottlenecks = {
            "aggregation": statistics.mean([m.aggregation_time_ms for m in recent])
            / statistics.mean([m.total_time_ms for m in recent]),
            "network": statistics.mean([m.network_time_ms for m in recent])
            / statistics.mean([m.total_time_ms for m in recent]),
            "computation": statistics.mean([m.computation_time_ms for m in recent])
            / statistics.mean([m.total_time_ms for m in recent]),
            "stragglers": (
                statistics.mean([m.stragglers_count for m in recent])
                / statistics.mean([m.nodes_participated for m in recent])
                if recent[0].nodes_participated > 0
                else 0
            ),
        }

        return bottlenecks

    def recommend_optimizations(self) -> List[str]:
        """
        Recommend optimizations based on bottlenecks.

        Returns:
            List of optimization recommendations
        """
        bottlenecks = self.identify_bottlenecks()
        recommendations = []

        if bottlenecks.get("aggregation", 0) > 0.3:
            recommendations.append(
                "Consider distributed aggregation to reduce aggregation bottleneck"
            )

        if bottlenecks.get("network", 0) > 0.3:
            recommendations.append(
                "Implement model compression for faster network transfers"
            )

        if bottlenecks.get("stragglers", 0) > 0.1:
            recommendations.append(
                "Use straggler mitigation techniques (e.g., deadline-based selection)"
            )

        if bottlenecks.get("computation", 0) > 0.5:
            recommendations.append("Increase parallelism or optimize model computation")

        return recommendations


class ClusterOptimizer:
    """
    Optimizes FL cluster topology and resource allocation.

    Features:
    - Partition nodes into optimal groups
    - Assign tasks to minimize latency
    - Recommend resource consolidation
    """

    def __init__(self, num_nodes: int = 100):
        """Initialize cluster optimizer"""
        self.num_nodes = num_nodes
        self.node_latencies: Dict[str, float] = {}
        self.node_bandwidths: Dict[str, float] = {}

    def recommend_partition_size(self, model_size_mb: float) -> int:
        """
        Recommend optimal number of partitions (groups of nodes).

        Args:
            model_size_mb: Model size in MB

        Returns:
            Recommended number of partitions
        """
        # Heuristic: partition size ~= sqrt(num_nodes)
        # Adjustment for model size
        base_partitions = int(self.num_nodes**0.5)

        # Adjust based on model size
        if model_size_mb > 1000:  # Large model
            base_partitions = max(1, base_partitions // 2)
        elif model_size_mb < 10:  # Small model
            base_partitions = min(self.num_nodes, base_partitions * 2)

        return max(1, base_partitions)

    def recommend_batch_size(self, total_nodes: int, available_memory_gb: float) -> int:
        """
        Recommend optimal batch size for training.

        Args:
            total_nodes: Total number of nodes
            available_memory_gb: Average memory per node in GB

        Returns:
            Recommended batch size
        """
        # Base batch size: 32
        base_batch = 32

        # Adjust based on available memory
        # Assume ~2GB per batch
        max_batches = max(1, int(available_memory_gb / 2))
        batches_count = min(max_batches, total_nodes // 10)

        return base_batch * max(1, batches_count)

    def get_summary(self) -> Dict[str, Any]:
        """Get cluster optimization summary"""
        return {
            "total_nodes": self.num_nodes,
            "recommended_partitions": self.recommend_partition_size(100),
            "recommended_batch_size": self.recommend_batch_size(self.num_nodes, 8),
            "optimization_timestamp": datetime.now().isoformat(),
        }
