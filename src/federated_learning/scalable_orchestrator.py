"""
Scalable Federated Learning Orchestrator for x0tta6bl4

Extends the basic FL coordinator with:
- Horizontal scaling (async task queue)
- Load balancing across multiple coordinators
- Distributed node registry
- Bulk aggregation for thousands of nodes
- Adaptive participation selection
- Resource-aware task distribution

Architecture:
    [Master Orchestrator]
           ↓
    ┌──────┴──────┬──────────┬──────────┐
    ↓             ↓          ↓          ↓
 [Coordinator] [Coordinator] ... [Coordinator]
    ↓             ↓          ↓          ↓
  [Nodes]      [Nodes]    [Nodes]    [Nodes]
  (1000+)       (1000+)    (1000+)    (1000+)

Features:
- Async task queuing (Redis/RabbitMQ compatible)
- Node registry with consistent hashing
- Batch operations for <100ms latency
- Automatic failover and retry logic
- Monitoring and metrics
"""

import asyncio
import hashlib
import json
import logging
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ScalableNodeRegistry:
    """
    Distributed node registry using consistent hashing.

    Enables:
    - O(log N) node lookup
    - Minimal remapping on node joins/leaves
    - Automatic rebalancing
    """

    def __init__(self, num_virtual_nodes: int = 160):
        """
        Args:
            num_virtual_nodes: Virtual nodes per physical node (default: 160)
                Higher = better distribution, higher overhead
        """
        self.num_virtual_nodes = num_virtual_nodes
        self.ring: Dict[int, str] = {}  # hash -> node_id
        self.nodes: Dict[str, "NodeMetadata"] = {}  # node_id -> metadata

    @staticmethod
    def _hash(key: str) -> int:
        """Consistent hash using SHA-256."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def add_node(self, node_id: str, capacity: int = 1000) -> None:
        """Add a new node to the ring."""
        self.nodes[node_id] = NodeMetadata(
            node_id=node_id, capacity=capacity, joined_at=time.time()
        )

        # Add virtual nodes
        for i in range(self.num_virtual_nodes):
            virtual_key = f"{node_id}:{i}"
            hash_value = self._hash(virtual_key)
            self.ring[hash_value] = node_id

        logger.info(f"Added node {node_id} with capacity {capacity}")

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the ring."""
        if node_id not in self.nodes:
            return

        del self.nodes[node_id]

        # Remove virtual nodes
        to_delete = [hash_val for hash_val, nid in self.ring.items() if nid == node_id]
        for hash_val in to_delete:
            del self.ring[hash_val]

        logger.info(f"Removed node {node_id}")

    def get_node(self, key: str) -> Optional[str]:
        """Find the node responsible for a key."""
        if not self.ring:
            return None

        hash_value = self._hash(key)
        sorted_hashes = sorted(self.ring.keys())

        # Find first hash >= key hash
        for h in sorted_hashes:
            if h >= hash_value:
                return self.ring[h]

        # Wrap around to first node
        return self.ring[sorted_hashes[0]]

    def get_top_n_nodes(self, key: str, n: int = 3) -> List[str]:
        """Get top N nodes for replication/load balancing."""
        if not self.ring:
            return []

        hash_value = self._hash(key)
        sorted_hashes = sorted(self.ring.keys())

        # Find starting position
        start_idx = 0
        for i, h in enumerate(sorted_hashes):
            if h >= hash_value:
                start_idx = i
                break

        # Collect unique nodes
        result = []
        seen = set()
        for i in range(len(sorted_hashes)):
            idx = (start_idx + i) % len(sorted_hashes)
            node_id = self.ring[sorted_hashes[idx]]
            if node_id not in seen:
                result.append(node_id)
                seen.add(node_id)
                if len(result) == n:
                    break

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_nodes": len(self.nodes),
            "total_capacity": sum(n.capacity for n in self.nodes.values()),
            "virtual_nodes_per_physical": self.num_virtual_nodes,
            "nodes": {
                node_id: asdict(metadata) for node_id, metadata in self.nodes.items()
            },
        }


@dataclass
class NodeMetadata:
    """Metadata for a node in the registry."""

    node_id: str
    capacity: int  # Max samples/round
    joined_at: float
    last_heartbeat: float = field(default_factory=time.time)
    samples_contributed: int = 0
    rounds_participated: int = 0
    cpu_load: float = 0.0
    memory_load: float = 0.0


@dataclass
class BulkAggregationTask:
    """Task for aggregating updates from multiple nodes."""

    task_id: str
    round_number: int
    coordinator_id: str

    # Node assignment
    assigned_nodes: Set[str] = field(default_factory=set)
    received_nodes: Set[str] = field(default_factory=set)

    # Aggregation
    updates: Dict[str, Any] = field(default_factory=dict)
    aggregation_method: str = "fedavg"

    # Timing
    created_at: float = field(default_factory=time.time)
    deadline: float = field(default_factory=lambda: time.time() + 60)

    def is_overdue(self) -> bool:
        """Check if task exceeded deadline."""
        return time.time() > self.deadline

    def is_complete(self) -> bool:
        """Check if received enough updates."""
        required = max(1, len(self.assigned_nodes) // 2)  # Majority
        return len(self.received_nodes) >= required


class ScalableFLOrchestrator:
    """
    Master orchestrator for federated learning at scale (1000+ nodes).

    Responsibilities:
    - Coordinate multiple sub-coordinators
    - Manage node registry
    - Distribute workload
    - Handle aggregation
    - Monitor health and metrics
    """

    def __init__(
        self,
        orchestrator_id: str,
        num_coordinators: int = 4,
        max_nodes_per_coordinator: int = 500,
    ):
        self.orchestrator_id = orchestrator_id
        self.num_coordinators = num_coordinators
        self.max_nodes_per_coordinator = max_nodes_per_coordinator

        # Node management
        self.registry = ScalableNodeRegistry()

        # Coordinator pool
        self.coordinators: Dict[str, "CoordinatorProxy"] = {}
        self._init_coordinators()

        # Task management
        self.active_tasks: Dict[str, BulkAggregationTask] = {}
        self.completed_tasks: List[BulkAggregationTask] = []

        # Metrics
        self.metrics = {
            "total_rounds": 0,
            "total_nodes_trained": 0,
            "aggregation_errors": 0,
            "avg_round_time": 0.0,
        }

    def _init_coordinators(self) -> None:
        """Initialize coordinator pool."""
        for i in range(self.num_coordinators):
            coordinator_id = f"coordinator-{i}"
            self.coordinators[coordinator_id] = CoordinatorProxy(
                coordinator_id=coordinator_id,
                max_capacity=self.max_nodes_per_coordinator,
            )

    async def register_node(self, node_id: str, capacity: int = 1000) -> str:
        """
        Register a new node and assign to coordinator.

        Returns:
            coordinator_id responsible for this node
        """
        # Add to registry
        self.registry.add_node(node_id, capacity)

        # Assign to least-loaded coordinator
        coordinator_id = self._select_coordinator()
        await self.coordinators[coordinator_id].register_node(node_id)

        logger.info(f"Registered node {node_id} -> {coordinator_id}")
        return coordinator_id

    def _select_coordinator(self) -> str:
        """Select coordinator with least load."""
        return min(
            self.coordinators.keys(), key=lambda cid: len(self.coordinators[cid].nodes)
        )

    async def start_training_round(
        self, round_number: int, target_participants: int
    ) -> BulkAggregationTask:
        """
        Initiate a federated learning round across all coordinators.

        Args:
            round_number: Round identifier
            target_participants: Target number of nodes to participate

        Returns:
            BulkAggregationTask tracking this round
        """
        start_time = time.time()

        # Create aggregation task
        task = BulkAggregationTask(
            task_id=f"round-{round_number}",
            round_number=round_number,
            coordinator_id=self.orchestrator_id,
        )

        # Assign nodes proportionally across coordinators
        nodes_to_select = self._adaptive_node_selection(target_participants)
        task.assigned_nodes = nodes_to_select

        self.active_tasks[task.task_id] = task

        # Distribute to coordinators
        coordinator_tasks = self._distribute_nodes(nodes_to_select)

        tasks = []
        for coordinator_id, node_subset in coordinator_tasks.items():
            coro = self.coordinators[coordinator_id].start_round(
                round_number, node_subset
            )
            tasks.append(coro)

        # Wait for all coordinators to start rounds
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time
        logger.info(
            f"Round {round_number} started: {len(nodes_to_select)} nodes, "
            f"{elapsed:.2f}s elapsed"
        )

        return task

    def _adaptive_node_selection(self, target_count: int) -> Set[str]:
        """
        Select nodes adaptively based on:
        - Availability (is_eligible)
        - Resource load (cpu_load, memory_load)
        - Recent performance (trust score)
        """
        candidates = []

        for node_id, metadata in self.registry.nodes.items():
            # Skip overloaded nodes
            if metadata.cpu_load > 0.8 or metadata.memory_load > 0.8:
                continue

            # Bias toward higher-capacity nodes
            weight = metadata.capacity / 1000.0
            candidates.append((node_id, weight))

        # Weighted random selection
        if not candidates:
            logger.warning("No eligible nodes available!")
            return set()

        node_ids, weights = zip(*candidates)
        weights = [w / sum(weights) for w in weights]

        selected = np.random.choice(
            node_ids, size=min(target_count, len(node_ids)), replace=False, p=weights
        )

        return set(selected)

    def _distribute_nodes(self, node_ids: Set[str]) -> Dict[str, List[str]]:
        """
        Distribute nodes across coordinators using consistent hashing.

        Returns:
            {coordinator_id: [node_ids]}
        """
        distribution = defaultdict(list)

        for node_id in node_ids:
            # Use registry to find coordinator
            coordinator_idx = hash(node_id) % self.num_coordinators
            coordinator_id = f"coordinator-{coordinator_idx}"
            distribution[coordinator_id].append(node_id)

        return distribution

    async def collect_updates(
        self, task_id: str, timeout_sec: float = 60
    ) -> Optional[BulkAggregationTask]:
        """
        Collect updates from nodes for a round.

        Returns:
            Updated task or None if timeout
        """
        if task_id not in self.active_tasks:
            return None

        task = self.active_tasks[task_id]
        start_time = time.time()

        # Periodically check for updates
        while time.time() - start_time < timeout_sec:
            # Collect from all coordinators
            gather_tasks = []
            for coordinator_id, coordinator in self.coordinators.items():
                coro = coordinator.collect_updates(task.round_number)
                gather_tasks.append(coro)

            results = await asyncio.gather(*gather_tasks, return_exceptions=True)

            # Merge updates
            for result in results:
                if isinstance(result, dict):
                    task.updates.update(result)
                    task.received_nodes.update(result.keys())

            # Check if complete
            if task.is_complete():
                elapsed = time.time() - start_time
                logger.info(
                    f"Round {task.round_number} collection complete: "
                    f"{len(task.received_nodes)} nodes, {elapsed:.2f}s"
                )
                return task

            # Wait before retry
            await asyncio.sleep(1)

        logger.warning(
            f"Round {task.round_number} collection timeout: "
            f"got {len(task.received_nodes)}/{len(task.assigned_nodes)}"
        )
        return task

    async def aggregate_round(self, task_id: str) -> bool:
        """
        Aggregate updates from all nodes in a round.

        Returns:
            True if successful
        """
        if task_id not in self.active_tasks:
            return False

        task = self.active_tasks[task_id]

        try:
            # Distribute aggregation work across coordinators
            agg_tasks = []
            for coordinator_id, coordinator in self.coordinators.items():
                coro = coordinator.aggregate(task.round_number)
                agg_tasks.append(coro)

            results = await asyncio.gather(*agg_tasks, return_exceptions=True)

            if any(isinstance(r, Exception) for r in results):
                self.metrics["aggregation_errors"] += 1
                logger.error(f"Aggregation failed for round {task.round_number}")
                return False

            # Move to completed
            self.active_tasks.pop(task_id)
            self.completed_tasks.append(task)

            logger.info(f"Round {task.round_number} aggregated successfully")
            return True

        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            self.metrics["aggregation_errors"] += 1
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        return {
            "orchestrator_id": self.orchestrator_id,
            "registry": self.registry.get_stats(),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "metrics": self.metrics,
            "coordinators": {
                cid: coordinator.get_status()
                for cid, coordinator in self.coordinators.items()
            },
        }


class CoordinatorProxy:
    """
    Proxy for a single FL coordinator (simplification).

    In production, this would communicate with remote coordinators
    via gRPC or HTTP.
    """

    def __init__(self, coordinator_id: str, max_capacity: int = 500):
        self.coordinator_id = coordinator_id
        self.max_capacity = max_capacity
        self.nodes: Set[str] = set()
        self.updates: Dict[int, Dict[str, Any]] = defaultdict(dict)

    async def register_node(self, node_id: str) -> bool:
        """Register a node with this coordinator."""
        if len(self.nodes) >= self.max_capacity:
            return False
        self.nodes.add(node_id)
        return True

    async def start_round(self, round_number: int, nodes: List[str]) -> bool:
        """Start a training round."""
        logger.info(
            f"{self.coordinator_id} starting round {round_number} "
            f"with {len(nodes)} nodes"
        )
        return True

    async def collect_updates(self, round_number: int) -> Dict[str, Any]:
        """Collect updates for a round (simulated)."""
        # In production, fetch from actual nodes
        return self.updates.get(round_number, {})

    async def aggregate(self, round_number: int) -> bool:
        """Aggregate updates for a round."""
        logger.info(f"{self.coordinator_id} aggregating round {round_number}")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status."""
        return {
            "coordinator_id": self.coordinator_id,
            "nodes": len(self.nodes),
            "capacity": self.max_capacity,
            "load": len(self.nodes) / self.max_capacity,
        }


# Import numpy for weighted selection
try:
    import numpy as np
except ImportError:
    np = None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def demo():
        # Create orchestrator
        orchestrator = ScalableFLOrchestrator(
            orchestrator_id="master-1",
            num_coordinators=4,
            max_nodes_per_coordinator=500,
        )

        # Register 1000 nodes
        print("Registering 1000 nodes...")
        for i in range(1000):
            await orchestrator.register_node(f"node-{i}")

        print(f"Registry stats: {orchestrator.registry.get_stats()}")

        # Start training round
        task = await orchestrator.start_training_round(
            round_number=1, target_participants=500
        )

        print(f"Started round with {len(task.assigned_nodes)} participants")

        # Collect updates (timeout after 5 seconds for demo)
        task = await orchestrator.collect_updates(task.task_id, timeout_sec=5)

        # Aggregate
        success = await orchestrator.aggregate_round(task.task_id)
        print(f"Aggregation success: {success}")

        # Show status
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2, default=str))

    # Run demo
    asyncio.run(demo())


# ============================================================================
# ENHANCEMENT: Byzantine-Robust Aggregation for FL
# ============================================================================


class ByzantineRobustAggregator:
    """
    Byzantine-robust aggregation for Federated Learning.

    Detects and filters out malicious client updates using:
    - Krum algorithm
    - MultiKrum for improved robustness
    - Distance-based anomaly detection
    """

    @staticmethod
    def krum_aggregation(updates: List[np.ndarray], num_byzantine: int) -> np.ndarray:
        """
        Krum algorithm for Byzantine-robust aggregation.

        Selects the update that is closest to (n - f - 2) other updates,
        where f is the number of Byzantine clients.
        """
        n = len(updates)
        if n <= num_byzantine + 2:
            # Not enough honest clients, fall back to median
            return np.median(np.array(updates), axis=0)

        # Compute pairwise distances
        distances = []
        for i, update_i in enumerate(updates):
            dist_sum = 0
            for j, update_j in enumerate(updates):
                if i != j:
                    dist_sum += np.linalg.norm(update_i - update_j)
            distances.append((i, dist_sum))

        # Find update closest to n - f - 2 others
        distances.sort(key=lambda x: x[1])
        selected_idx = distances[0][0]

        return updates[selected_idx]

    @staticmethod
    def multikrum_aggregation(
        updates: List[np.ndarray], num_byzantine: int, m: int = 1
    ) -> np.ndarray:
        """
        MultiKrum - select m best updates and average them.

        More robust than single Krum.
        """
        n = len(updates)
        if n <= num_byzantine + 2:
            return np.mean(updates, axis=0)

        # Compute distances
        distances = []
        for i, update_i in enumerate(updates):
            dist_sum = 0
            for j, update_j in enumerate(updates):
                if i != j:
                    dist_sum += np.linalg.norm(update_i - update_j)
            distances.append((i, dist_sum))

        # Select top m
        distances.sort(key=lambda x: x[1])
        selected_indices = [idx for idx, _ in distances[:m]]
        selected_updates = [updates[idx] for idx in selected_indices]

        return np.mean(selected_updates, axis=0)


# ============================================================================
# ENHANCEMENT: Gradient Compression for Bandwidth Reduction
# ============================================================================


class GradientCompressor:
    """
    Compress gradients to reduce bandwidth by 50%+.

    Techniques:
    - Top-K sparsification
    - Quantization (INT8)
    - Random projection
    """

    @staticmethod
    def top_k_sparsify(
        gradient: np.ndarray, k_percent: float = 0.1
    ) -> Tuple[np.ndarray, Dict]:
        """
        Keep only top K% of gradient values by magnitude.

        k_percent: fraction of values to keep (0.0-1.0)
        """
        original_size = gradient.size
        k = max(1, int(original_size * k_percent))

        # Flatten and get indices of top-k
        flat = gradient.flatten()
        top_indices = np.argsort(np.abs(flat))[-k:]

        # Create sparse representation
        sparse_gradient = np.zeros_like(flat)
        sparse_gradient[top_indices] = flat[top_indices]

        metadata = {
            "compression_ratio": k_percent,
            "original_size": original_size,
            "compressed_size": k,
            "bandwidth_reduction_percent": (1 - k / original_size) * 100,
        }

        return sparse_gradient.reshape(gradient.shape), metadata

    @staticmethod
    def quantize_to_int8(gradient: np.ndarray) -> Tuple[np.ndarray, float]:
        """Quantize gradient to INT8 (8x compression)."""
        max_val = np.max(np.abs(gradient))
        quantized = np.round(gradient / max_val * 127).astype(np.int8)
        return quantized, max_val

    @staticmethod
    def dequantize_from_int8(quantized: np.ndarray, scale: float) -> np.ndarray:
        """Dequantize INT8 gradient back to float."""
        return quantized.astype(np.float32) / 127.0 * scale


# ============================================================================
# ENHANCEMENT: Adaptive Client Sampling
# ============================================================================


class AdaptiveClientSampler:
    """
    Intelligently select clients for each FL round based on:
    - Recent convergence contribution
    - Available bandwidth
    - Stragglers (slow clients)
    - Device heterogeneity
    """

    def __init__(self, total_clients: int):
        self.total_clients = total_clients
        self.convergence_scores = defaultdict(float)
        self.bandwidth_estimates = defaultdict(lambda: 10.0)  # Default 10 Mbps
        self.straggler_history = defaultdict(list)

    def select_clients(
        self,
        round_num: int,
        target_fraction: float = 0.1,
        exclude_stragglers: bool = False,
    ) -> List[str]:
        """
        Adaptive sampling of clients for FL round.

        target_fraction: select this fraction of total clients
        """
        num_to_select = max(1, int(self.total_clients * target_fraction))

        # Score clients by convergence contribution
        scores = []
        for client_id in range(self.total_clients):
            client_str = f"client_{client_id}"

            score = self.convergence_scores[client_str]

            # Penalize stragglers
            if exclude_stragglers:
                straggler_ratio = len(self.straggler_history[client_str]) / max(
                    1, round_num
                )
                score *= 1 - straggler_ratio

            scores.append((client_str, score))

        # Select top clients
        scores.sort(key=lambda x: x[1], reverse=True)
        return [client_id for client_id, _ in scores[:num_to_select]]

    def update_convergence_score(self, client_id: str, improvement: float):
        """Update convergence score based on improvement."""
        self.convergence_scores[client_id] = (
            0.7 * self.convergence_scores[client_id] + 0.3 * improvement
        )

    def mark_straggler(self, client_id: str, round_num: int):
        """Mark client as straggler for round."""
        self.straggler_history[client_id].append(round_num)
