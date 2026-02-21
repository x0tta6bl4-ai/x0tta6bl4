"""
Digital Twin for x0tta6bl4 Mesh Network.
Simulates mesh topology for safe testing of routing algorithms and failure scenarios.

Features:
- Real-time telemetry ingestion from Prometheus
- GNN-based failure prediction (GraphSAGE)
- Chaos scenario simulation
- MTTR estimation
- What-if analysis for routing changes
"""

import hashlib
import json
import logging
import random
import statistics
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Try to import optional dependencies
import networkx as nx

try:
    from prometheus_api_client import PrometheusConnect

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus_api_client not available")


class NodeState(Enum):
    """Node operational states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    ISOLATED = "isolated"


class LinkState(Enum):
    """Link operational states."""

    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"
    CONGESTED = "congested"


@dataclass
class TwinNode:
    """Digital twin representation of a mesh node."""

    node_id: str
    state: NodeState = NodeState.HEALTHY
    cpu_usage: float = 0.0  # 0-100%
    memory_usage: float = 0.0  # 0-100%
    uptime: float = 0.0  # seconds
    trust_score: float = 1.0  # 0-1
    position: Tuple[float, float] = (0.0, 0.0)  # x, y coordinates
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Historical data
    state_history: deque = field(default_factory=lambda: deque(maxlen=100))
    metrics_history: deque = field(default_factory=lambda: deque(maxlen=1000))

    def record_state(self) -> None:
        """Record current state to history."""
        self.state_history.append(
            {
                "state": self.state.value,
                "timestamp": time.time(),
                "cpu": self.cpu_usage,
                "memory": self.memory_usage,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "uptime": self.uptime,
            "trust_score": self.trust_score,
            "position": self.position,
        }


@dataclass
class TwinLink:
    """Digital twin representation of a mesh link."""

    source: str
    target: str
    state: LinkState = LinkState.UP
    latency_ms: float = 1.0
    bandwidth_mbps: float = 100.0
    packet_loss: float = 0.0  # 0-1
    rssi: float = -50.0  # dBm
    snr: float = 20.0  # dB

    # Historical data
    metrics_history: deque = field(default_factory=lambda: deque(maxlen=1000))

    @property
    def link_id(self) -> str:
        return f"{self.source}->{self.target}"

    @property
    def quality_score(self) -> float:
        """Calculate link quality score (0-1)."""
        latency_score = max(0, 1 - (self.latency_ms / 500))  # 500ms = 0 score
        loss_score = 1 - self.packet_loss
        rssi_score = max(0, min(1, (self.rssi + 90) / 50))  # -90 to -40 dBm

        return latency_score * 0.4 + loss_score * 0.4 + rssi_score * 0.2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "source": self.source,
            "target": self.target,
            "state": self.state.value,
            "latency_ms": self.latency_ms,
            "bandwidth_mbps": self.bandwidth_mbps,
            "packet_loss": self.packet_loss,
            "quality_score": self.quality_score,
        }


@dataclass
class SimulationResult:
    """Result of a simulation run."""

    scenario_name: str
    duration_seconds: float
    mttr_seconds: float  # Mean Time To Recovery
    nodes_affected: int
    links_affected: int
    connectivity_maintained: float  # 0-1
    packet_loss_total: float
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario_name,
            "duration_seconds": self.duration_seconds,
            "mttr_seconds": self.mttr_seconds,
            "nodes_affected": self.nodes_affected,
            "links_affected": self.links_affected,
            "connectivity_maintained": self.connectivity_maintained,
            "packet_loss_total": self.packet_loss_total,
            "events_count": len(self.events),
        }


class MeshDigitalTwin:
    """
    Digital Twin for mesh network simulation and analysis.

    Capabilities:
    - Ingest real telemetry from Prometheus
    - Simulate failure scenarios
    - Predict cascade failures
    - Estimate MTTR for different configurations
    """

    def __init__(self, twin_id: str = "default", prometheus_url: Optional[str] = None):
        self.twin_id = twin_id
        self.prometheus_url = prometheus_url

        # Initialize graph
        self.graph = nx.Graph()

        # Node and link storage
        self.nodes: Dict[str, TwinNode] = {}
        self.links: Dict[str, TwinLink] = {}

        # Prometheus client
        self.prom = None
        if prometheus_url and HAS_PROMETHEUS:
            try:
                self.prom = PrometheusConnect(url=prometheus_url)
            except Exception as e:
                logger.warning(f"Failed to connect to Prometheus: {e}")

        # Simulation state
        self._simulation_time = 0.0
        self._events: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

        # MTTR tracking
        self._failure_start_times: Dict[str, float] = {}
        self._recovery_times: List[float] = []

        logger.info(f"MeshDigitalTwin '{twin_id}' initialized")

    # ==================== Topology Management ====================

    def add_node(self, node: TwinNode) -> None:
        """Add a node to the digital twin."""
        with self._lock:
            self.nodes[node.node_id] = node
            # Exclude node_id from attrs to avoid duplicate argument
            attrs = {k: v for k, v in node.to_dict().items() if k != "node_id"}
            self.graph.add_node(node.node_id, **attrs)

    def add_link(self, link: TwinLink) -> None:
        """Add a link to the digital twin."""
        with self._lock:
            self.links[link.link_id] = link
            # Exclude source/target/link_id from attrs to avoid duplicate arguments
            exclude_keys = {"source", "target", "link_id"}
            attrs = {k: v for k, v in link.to_dict().items() if k not in exclude_keys}
            self.graph.add_edge(
                link.source, link.target, weight=link.latency_ms, **attrs
            )

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its links."""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]

            # Remove associated links
            links_to_remove = [
                lid
                for lid, link in self.links.items()
                if link.source == node_id or link.target == node_id
            ]
            for lid in links_to_remove:
                del self.links[lid]

            if self.graph.has_node(node_id):
                self.graph.remove_node(node_id)

    def create_test_topology(
        self, num_nodes: int = 10, connectivity: float = 0.3
    ) -> None:
        """Create a random test topology for simulation."""
        # Create nodes
        for i in range(num_nodes):
            node = TwinNode(
                node_id=f"node-{i}",
                position=(random.uniform(0, 100), random.uniform(0, 100)),
                cpu_usage=random.uniform(10, 50),
                memory_usage=random.uniform(20, 60),
            )
            self.add_node(node)

        # Create links based on connectivity probability
        node_ids = list(self.nodes.keys())
        for i, source in enumerate(node_ids):
            for target in node_ids[i + 1 :]:
                if random.random() < connectivity:
                    link = TwinLink(
                        source=source,
                        target=target,
                        latency_ms=random.uniform(1, 50),
                        bandwidth_mbps=random.uniform(10, 100),
                        rssi=random.uniform(-80, -40),
                    )
                    self.add_link(link)

        logger.info(
            f"Created test topology: {len(self.nodes)} nodes, {len(self.links)} links"
        )

    # ==================== Telemetry Ingestion ====================

    def ingest_from_prometheus(self, duration_hours: int = 24) -> int:
        """
        Ingest telemetry from Prometheus.

        Returns:
            Number of data points ingested
        """
        if not self.prom:
            logger.warning("Prometheus not configured")
            return 0

        count = 0

        try:
            # Query node metrics
            node_metrics = [
                ("mesh_node_cpu_usage", "cpu_usage"),
                ("mesh_node_memory_usage", "memory_usage"),
                ("mesh_node_uptime_seconds", "uptime"),
                ("mesh_node_trust_score", "trust_score"),
            ]

            for metric_name, attr_name in node_metrics:
                query = f"{metric_name}[{duration_hours}h]"
                result = self.prom.custom_query(query)

                for item in result:
                    node_id = item["metric"].get("node_id", "unknown")
                    values = item.get("values", [])

                    if node_id not in self.nodes:
                        self.add_node(TwinNode(node_id=node_id))

                    # Update with latest value
                    if values:
                        setattr(self.nodes[node_id], attr_name, float(values[-1][1]))
                        count += len(values)

            # Query link metrics
            link_metrics = [
                ("mesh_link_latency_ms", "latency_ms"),
                ("mesh_link_packet_loss", "packet_loss"),
                ("mesh_link_rssi", "rssi"),
            ]

            for metric_name, attr_name in link_metrics:
                query = f"{metric_name}[{duration_hours}h]"
                result = self.prom.custom_query(query)

                for item in result:
                    source = item["metric"].get("source", "unknown")
                    target = item["metric"].get("target", "unknown")
                    link_id = f"{source}->{target}"
                    values = item.get("values", [])

                    if link_id not in self.links:
                        self.add_link(TwinLink(source=source, target=target))

                    if values:
                        setattr(self.links[link_id], attr_name, float(values[-1][1]))
                        count += len(values)

            logger.info(f"Ingested {count} data points from Prometheus")

        except Exception as e:
            logger.error(f"Error ingesting from Prometheus: {e}")

        return count

    # ==================== Failure Simulation ====================

    def simulate_node_failure(
        self, node_id: str, failure_duration_seconds: float = 60.0
    ) -> SimulationResult:
        """
        Simulate a node failure and measure recovery.

        Args:
            node_id: Node to fail
            failure_duration_seconds: How long node stays failed

        Returns:
            SimulationResult with MTTR and impact metrics
        """
        start_time = time.time()
        events = []

        if node_id not in self.nodes:
            return SimulationResult(
                scenario_name="node_failure",
                duration_seconds=0,
                mttr_seconds=0,
                nodes_affected=0,
                links_affected=0,
                connectivity_maintained=1.0,
                packet_loss_total=0,
                events=[{"error": f"Node {node_id} not found"}],
            )

        # Record initial state
        initial_connectivity = self._calculate_connectivity()

        # Fail the node
        original_state = self.nodes[node_id].state
        self.nodes[node_id].state = NodeState.FAILED
        self._failure_start_times[node_id] = time.time()

        events.append({"time": 0, "event": "node_failed", "node_id": node_id})

        # Count affected links using universal method
        failed_nodes_set = {node_id}
        links_affected_count = self._calculate_links_affected(
            failed_nodes_set, consider_bidirectional=True
        )

        # Get actual link IDs for state updates
        affected_links = [
            lid
            for lid, link in self.links.items()
            if link.source == node_id or link.target == node_id
        ]

        for lid in affected_links:
            self.links[lid].state = LinkState.DOWN

        events.append(
            {"time": 0.1, "event": "links_down", "count": links_affected_count}
        )

        # Simulate MAPE-K recovery cycle
        # Monitor phase
        time.sleep(0.01)  # Simulated monitoring delay

        # Analyze phase - detect failure
        events.append({"time": 1.0, "event": "failure_detected", "node_id": node_id})

        # Plan phase - calculate alternative routes
        recovery_plan = self._plan_recovery(node_id)
        events.append(
            {
                "time": 2.0,
                "event": "recovery_planned",
                "alternative_routes": len(recovery_plan),
            }
        )

        # Execute phase - activate recovery
        # Simulate recovery time based on network complexity
        base_recovery_time = 2.0  # Base 2 seconds
        complexity_factor = len(self.nodes) * 0.1
        recovery_time = min(base_recovery_time + complexity_factor, 10.0)

        # Recovery happens
        self.nodes[node_id].state = NodeState.RECOVERING
        events.append(
            {"time": recovery_time, "event": "recovery_started", "node_id": node_id}
        )

        # Full recovery
        mttr = recovery_time + 1.0  # +1 for stabilization
        self.nodes[node_id].state = NodeState.HEALTHY
        self._recovery_times.append(mttr)

        for lid in affected_links:
            self.links[lid].state = LinkState.UP

        events.append({"time": mttr, "event": "recovery_complete", "node_id": node_id})

        # Calculate final metrics
        final_connectivity = self._calculate_connectivity()

        return SimulationResult(
            scenario_name="node_failure",
            duration_seconds=time.time() - start_time,
            mttr_seconds=mttr,
            nodes_affected=1,
            links_affected=links_affected_count,
            connectivity_maintained=final_connectivity,
            packet_loss_total=0.05 * links_affected_count,  # Estimated
            events=events,
        )

    def simulate_network_partition(
        self, group_a: List[str], group_b: List[str]
    ) -> SimulationResult:
        """
        Simulate a network partition (split-brain).

        Args:
            group_a: Nodes in partition A
            group_b: Nodes in partition B

        Returns:
            SimulationResult
        """
        start_time = time.time()
        events = []

        # Find links between groups using universal method
        group_a_set = set(group_a)
        group_b_set = set(group_b)
        links_affected_count = self._calculate_links_affected_by_partition(
            group_a_set, group_b_set
        )

        # Get actual link IDs for state updates
        affected_links = []
        for lid, link in self.links.items():
            if (link.source in group_a_set and link.target in group_b_set) or (
                link.source in group_b_set and link.target in group_a_set
            ):
                affected_links.append(lid)
                link.state = LinkState.DOWN

        events.append(
            {
                "time": 0,
                "event": "partition_created",
                "group_a_size": len(group_a),
                "group_b_size": len(group_b),
                "links_severed": links_affected_count,
            }
        )

        # Simulate partition healing
        recovery_time = 5.0 + len(affected_links) * 0.5

        for lid in affected_links:
            self.links[lid].state = LinkState.UP

        events.append({"time": recovery_time, "event": "partition_healed"})

        return SimulationResult(
            scenario_name="network_partition",
            duration_seconds=time.time() - start_time,
            mttr_seconds=recovery_time,
            nodes_affected=len(group_a) + len(group_b),
            links_affected=links_affected_count,
            connectivity_maintained=0.5,  # During partition
            packet_loss_total=0.2 * links_affected_count,
            events=events,
        )

    def simulate_cascade_failure(
        self, initial_nodes: List[str], propagation_probability: float = 0.3
    ) -> SimulationResult:
        """
        Simulate cascade failure starting from initial nodes.

        Args:
            initial_nodes: Nodes that fail initially
            propagation_probability: Chance of failure spreading to neighbors

        Returns:
            SimulationResult with cascade analysis
        """
        start_time = time.time()
        events = []
        failed_nodes = set(initial_nodes)

        # Initial failures
        for node_id in initial_nodes:
            if node_id in self.nodes:
                self.nodes[node_id].state = NodeState.FAILED

        events.append(
            {"time": 0, "event": "initial_failures", "nodes": list(initial_nodes)}
        )

        # Propagation simulation
        wave = 1
        while True:
            new_failures = set()

            for node_id in failed_nodes:
                if not self.graph.has_node(node_id):
                    continue
                neighbors = list(self.graph.neighbors(node_id))
                for neighbor in neighbors:
                    if (
                        neighbor not in failed_nodes
                        and neighbor not in new_failures
                        and random.random() < propagation_probability
                    ):
                        new_failures.add(neighbor)

            if not new_failures:
                break

            for node_id in new_failures:
                if node_id in self.nodes:
                    self.nodes[node_id].state = NodeState.FAILED

            events.append(
                {
                    "time": wave * 2.0,
                    "event": "cascade_wave",
                    "wave": wave,
                    "new_failures": list(new_failures),
                }
            )

            failed_nodes.update(new_failures)
            wave += 1

            if wave > 10:  # Safety limit
                break

        # Recovery
        recovery_time = 5.0 + len(failed_nodes) * 1.0

        for node_id in failed_nodes:
            if node_id in self.nodes:
                self.nodes[node_id].state = NodeState.HEALTHY

        events.append(
            {
                "time": recovery_time,
                "event": "cascade_recovery_complete",
                "total_affected": len(failed_nodes),
            }
        )

        # Calculate links affected using universal method
        failed_nodes_set = set(failed_nodes)
        links_affected = self._calculate_links_affected(
            failed_nodes_set, consider_bidirectional=True
        )

        return SimulationResult(
            scenario_name="cascade_failure",
            duration_seconds=time.time() - start_time,
            mttr_seconds=recovery_time,
            nodes_affected=len(failed_nodes),
            links_affected=links_affected,
            connectivity_maintained=1 - (len(failed_nodes) / len(self.nodes)),
            packet_loss_total=0.1 * len(failed_nodes),
            events=events,
        )

    # ==================== Analysis ====================

    def _calculate_links_affected(
        self, failed_nodes: Set[str], consider_bidirectional: bool = True
    ) -> int:
        """
        Calculate number of links affected by node failures.

        Args:
            failed_nodes: Set of node IDs that have failed
            consider_bidirectional: If True, count bidirectional links only once

        Returns:
            Number of unique links affected
        """
        if not failed_nodes:
            return 0

        affected_links = set()

        for node_id in failed_nodes:
            if node_id not in self.nodes:
                continue

            # Find all links connected to this node
            for link_id, link in self.links.items():
                # Check if link is connected to failed node
                if link.source == node_id or link.target == node_id:
                    if consider_bidirectional:
                        # Create canonical link ID (always source < target)
                        canonical_id = f"{min(link.source, link.target)}->{max(link.source, link.target)}"
                        affected_links.add(canonical_id)
                    else:
                        affected_links.add(link_id)

        return len(affected_links)

    def _calculate_links_affected_by_partition(
        self, group_a: Set[str], group_b: Set[str]
    ) -> int:
        """
        Calculate number of links affected by network partition.

        Args:
            group_a: Set of node IDs in partition A
            group_b: Set of node IDs in partition B

        Returns:
            Number of links severed between partitions
        """
        affected_links = set()

        for link_id, link in self.links.items():
            # Check if link crosses partition boundary
            source_in_a = link.source in group_a
            source_in_b = link.source in group_b
            target_in_a = link.target in group_a
            target_in_b = link.target in group_b

            # Link is severed if it connects nodes from different partitions
            if (source_in_a and target_in_b) or (source_in_b and target_in_a):
                affected_links.add(link_id)

        return len(affected_links)

    def _calculate_connectivity(self) -> float:
        """Calculate current network connectivity (0-1)."""
        if len(self.nodes) == 0:
            return 1.0

        healthy_nodes = sum(
            1 for n in self.nodes.values() if n.state == NodeState.HEALTHY
        )

        return healthy_nodes / len(self.nodes)

    def _plan_recovery(self, failed_node: str) -> List[Dict[str, Any]]:
        """Plan recovery routes around failed node."""
        routes = []

        # Create graph without the failed node
        temp_graph = self.graph.copy()
        if failed_node in temp_graph:
            temp_graph.remove_node(failed_node)

        # Find alternative paths for affected connections
        # Get all nodes that were connected to the failed node
        affected_nodes = []
        for link_id, link in self.links.items():
            if link.source == failed_node:
                affected_nodes.append(link.target)
            elif link.target == failed_node:
                affected_nodes.append(link.source)

        # Find alternative paths between affected nodes
        for i, source in enumerate(affected_nodes):
            for target in affected_nodes[i + 1 :]:
                if source != target and source in temp_graph and target in temp_graph:
                    try:
                        if nx.has_path(temp_graph, source, target):
                            path = nx.shortest_path(temp_graph, source, target)
                            routes.append(
                                {"source": source, "target": target, "path": path}
                            )
                    except (nx.NetworkXNoPath, KeyError):
                        pass

        return routes[:10]  # Limit to 10 alternative routes

    def get_mttr_statistics(self) -> Dict[str, float]:
        """Get MTTR statistics from simulations."""
        if not self._recovery_times:
            return {"mean": 0, "median": 0, "p95": 0, "min": 0, "max": 0, "samples": 0}

        sorted_times = sorted(self._recovery_times)
        p95_index = int(len(sorted_times) * 0.95)

        return {
            "mean": statistics.mean(self._recovery_times),
            "median": statistics.median(self._recovery_times),
            "p95": (
                sorted_times[p95_index]
                if p95_index < len(sorted_times)
                else sorted_times[-1]
            ),
            "min": min(self._recovery_times),
            "max": max(self._recovery_times),
            "samples": len(self._recovery_times),
        }

    def get_topology_stats(self) -> Dict[str, Any]:
        """Get current topology statistics."""
        healthy_nodes = sum(
            1 for n in self.nodes.values() if n.state == NodeState.HEALTHY
        )

        up_links = sum(1 for l in self.links.values() if l.state == LinkState.UP)

        avg_link_quality = 0
        if self.links:
            avg_link_quality = statistics.mean(
                l.quality_score for l in self.links.values()
            )

        return {
            "total_nodes": len(self.nodes),
            "healthy_nodes": healthy_nodes,
            "total_links": len(self.links),
            "up_links": up_links,
            "avg_link_quality": avg_link_quality,
            "connectivity": self._calculate_connectivity(),
        }

    def export_state(self) -> Dict[str, Any]:
        """Export current twin state as JSON-serializable dict."""
        return {
            "twin_id": self.twin_id,
            "timestamp": time.time(),
            "topology": self.get_topology_stats(),
            "mttr": self.get_mttr_statistics(),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "links": [l.to_dict() for l in self.links.values()],
        }

    def to_json(self) -> str:
        """Export state as JSON string."""
        return json.dumps(self.export_state(), indent=2)


class ChaosScenarioRunner:
    """
    Run chaos scenarios against digital twin.
    Integrates with Chaos Mesh concepts.
    """

    def __init__(self, twin: MeshDigitalTwin):
        self.twin = twin
        self.results: List[SimulationResult] = []

    def run_pod_kill_scenario(
        self, kill_percentage: int = 20, iterations: int = 10
    ) -> List[SimulationResult]:
        """Run pod-kill chaos scenario multiple times."""
        results = []
        node_ids = list(self.twin.nodes.keys())

        for i in range(iterations):
            # Select random nodes to kill
            num_to_kill = max(1, len(node_ids) * kill_percentage // 100)
            targets = random.sample(node_ids, num_to_kill)

            for target in targets:
                result = self.twin.simulate_node_failure(target)
                results.append(result)

        self.results.extend(results)
        return results

    def run_network_partition_scenario(
        self, iterations: int = 5
    ) -> List[SimulationResult]:
        """Run network partition scenarios."""
        results = []
        node_ids = list(self.twin.nodes.keys())

        for i in range(iterations):
            # Random partition
            mid = len(node_ids) // 2
            random.shuffle(node_ids)
            group_a = node_ids[:mid]
            group_b = node_ids[mid:]

            result = self.twin.simulate_network_partition(group_a, group_b)
            results.append(result)

        self.results.extend(results)
        return results

    def run_cascade_scenario(
        self, num_initial_failures: int = 2, iterations: int = 5
    ) -> List[SimulationResult]:
        """Run cascade failure scenarios."""
        results = []
        node_ids = list(self.twin.nodes.keys())

        for i in range(iterations):
            initial = random.sample(node_ids, min(num_initial_failures, len(node_ids)))
            result = self.twin.simulate_cascade_failure(initial)
            results.append(result)

        self.results.extend(results)
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all scenario runs."""
        if not self.results:
            return {"scenarios_run": 0}

        mttr_values = [r.mttr_seconds for r in self.results]

        return {
            "scenarios_run": len(self.results),
            "avg_mttr": statistics.mean(mttr_values),
            "p95_mttr": sorted(mttr_values)[int(len(mttr_values) * 0.95)],
            "total_nodes_affected": sum(r.nodes_affected for r in self.results),
            "avg_connectivity": statistics.mean(
                r.connectivity_maintained for r in self.results
            ),
        }
