"""
Mesh Telemetry Generator for GraphSAGE Training

Generates realistic mesh network telemetry data with labeled anomalies
for training the GraphSAGE anomaly detector. Replaces random synthetic
data with structured scenarios based on real mesh failure modes.

Scenario taxonomy:
  - NORMAL: stable mesh operation with natural variance
  - LINK_DEGRADATION: gradual RSSI/SNR drop on specific links
  - NODE_OVERLOAD: CPU/memory spike leading to packet loss
  - CASCADE_FAILURE: one failure triggers neighboring failures
  - INTERFERENCE: RF interference causing SNR drop across region
  - PARTITION: network split (some links go down simultaneously)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "rssi",
    "snr",
    "loss_rate",
    "link_age",
    "latency",
    "throughput",
    "cpu",
    "memory",
]


class ScenarioType(Enum):
    NORMAL = "normal"
    LINK_DEGRADATION = "link_degradation"
    NODE_OVERLOAD = "node_overload"
    CASCADE_FAILURE = "cascade_failure"
    INTERFERENCE = "interference"
    PARTITION = "partition"


@dataclass
class MeshSnapshot:
    """A single snapshot of mesh network state with labels."""

    node_features: List[Dict[str, float]]
    edge_index: List[Tuple[int, int]]
    labels: List[float]  # 1.0 = anomaly, 0.0 = normal
    scenario: ScenarioType
    num_nodes: int
    num_anomalous: int


class MeshTelemetryGenerator:
    """
    Generate realistic mesh network telemetry with labeled anomalies.

    Each scenario produces physically plausible correlations:
    - Low RSSI correlates with high loss_rate and low throughput
    - High CPU correlates with high latency
    - Link degradation shows gradual trends, not random jumps
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate_dataset(
        self,
        num_snapshots: int = 100,
        nodes_per_snapshot: int = 20,
        anomaly_ratio: float = 0.3,
    ) -> List[MeshSnapshot]:
        """
        Generate a balanced dataset of mesh snapshots.

        Args:
            num_snapshots: Total number of graph snapshots
            nodes_per_snapshot: Nodes in each topology
            anomaly_ratio: Fraction of snapshots with anomalies

        Returns:
            List of MeshSnapshot with features, edges, and labels.
        """
        snapshots = []
        num_anomaly = int(num_snapshots * anomaly_ratio)
        num_normal = num_snapshots - num_anomaly

        # Normal snapshots
        for _ in range(num_normal):
            snapshots.append(
                self._generate_snapshot(nodes_per_snapshot, ScenarioType.NORMAL)
            )

        # Anomalous snapshots - cycle through failure types
        failure_types = [
            ScenarioType.LINK_DEGRADATION,
            ScenarioType.NODE_OVERLOAD,
            ScenarioType.CASCADE_FAILURE,
            ScenarioType.INTERFERENCE,
            ScenarioType.PARTITION,
        ]
        for i in range(num_anomaly):
            scenario = failure_types[i % len(failure_types)]
            snapshots.append(self._generate_snapshot(nodes_per_snapshot, scenario))

        self.rng.shuffle(snapshots)
        return snapshots

    def _generate_snapshot(
        self, num_nodes: int, scenario: ScenarioType
    ) -> MeshSnapshot:
        """Generate a single mesh snapshot for the given scenario."""
        # Build mesh topology (random geometric graph)
        edges = self._build_mesh_topology(num_nodes)

        # Generate base features (normal operation)
        features = [self._normal_node_features() for _ in range(num_nodes)]
        labels = [0.0] * num_nodes

        # Apply scenario-specific anomalies
        if scenario == ScenarioType.NORMAL:
            pass  # All normal
        elif scenario == ScenarioType.LINK_DEGRADATION:
            self._apply_link_degradation(features, labels, edges)
        elif scenario == ScenarioType.NODE_OVERLOAD:
            self._apply_node_overload(features, labels)
        elif scenario == ScenarioType.CASCADE_FAILURE:
            self._apply_cascade_failure(features, labels, edges)
        elif scenario == ScenarioType.INTERFERENCE:
            self._apply_interference(features, labels)
        elif scenario == ScenarioType.PARTITION:
            self._apply_partition(features, labels, edges)

        num_anomalous = sum(1 for l in labels if l > 0.5)
        return MeshSnapshot(
            node_features=features,
            edge_index=edges,
            labels=labels,
            scenario=scenario,
            num_nodes=num_nodes,
            num_anomalous=num_anomalous,
        )

    def _build_mesh_topology(self, num_nodes: int) -> List[Tuple[int, int]]:
        """Build a random mesh topology (undirected edges)."""
        edges = []
        # Ensure connectivity: chain
        for i in range(num_nodes - 1):
            edges.append((i, i + 1))
            edges.append((i + 1, i))
        # Add random mesh links (each node connects to 1-3 additional peers)
        for i in range(num_nodes):
            extra = self.rng.randint(0, 2)
            for _ in range(extra):
                j = self.rng.randint(0, num_nodes - 1)
                if j != i:
                    edges.append((i, j))
                    edges.append((j, i))
        # Deduplicate
        return list(set(edges))

    def _normal_node_features(self) -> Dict[str, float]:
        """Generate features for a healthy mesh node."""
        rssi = self.rng.gauss(-55.0, 8.0)  # dBm, typical -40 to -70
        rssi = max(-90.0, min(-20.0, rssi))
        snr = rssi + self.rng.gauss(75.0, 3.0)  # SNR ~ RSSI + noise floor offset
        snr = max(5.0, min(40.0, snr))

        # Loss correlates inversely with signal quality
        base_loss = max(0.0, 0.01 + self.rng.gauss(0.0, 0.005))
        if rssi < -70:
            base_loss += 0.02 * abs(rssi + 70) / 20

        # Throughput correlates with signal quality
        throughput = max(0.1, min(100.0, snr * 2.5 + self.rng.gauss(0, 5)))

        return {
            "rssi": round(rssi, 2),
            "snr": round(snr, 2),
            "loss_rate": round(max(0.0, min(1.0, base_loss)), 4),
            "link_age": round(self.rng.uniform(60, 86400), 1),  # seconds
            "latency": round(max(1.0, self.rng.gauss(15.0, 5.0)), 2),  # ms
            "throughput": round(throughput, 2),  # Mbps
            "cpu": round(max(0.0, min(1.0, self.rng.gauss(0.3, 0.1))), 3),
            "memory": round(max(0.0, min(1.0, self.rng.gauss(0.4, 0.1))), 3),
        }

    # --- Anomaly Scenarios ---

    def _apply_link_degradation(
        self,
        features: List[Dict[str, float]],
        labels: List[float],
        edges: List[Tuple[int, int]],
    ):
        """Gradual signal degradation on 2-4 nodes."""
        num_affected = self.rng.randint(2, min(4, len(features)))
        affected = self.rng.sample(range(len(features)), num_affected)

        for idx in affected:
            f = features[idx]
            severity = self.rng.uniform(0.5, 1.0)
            # RSSI drops significantly
            f["rssi"] = round(f["rssi"] - severity * 25, 2)
            f["rssi"] = max(-95.0, f["rssi"])
            # SNR drops accordingly
            f["snr"] = round(max(2.0, f["snr"] - severity * 15), 2)
            # Loss rate spikes (correlated with signal drop)
            f["loss_rate"] = round(min(0.8, f["loss_rate"] + severity * 0.15), 4)
            # Throughput drops
            f["throughput"] = round(max(0.1, f["throughput"] * (1 - severity * 0.6)), 2)
            # Link age resets (link flapping)
            f["link_age"] = round(self.rng.uniform(1, 30), 1)
            labels[idx] = 1.0

    def _apply_node_overload(
        self,
        features: List[Dict[str, float]],
        labels: List[float],
    ):
        """CPU/memory spike on 1-3 nodes, causing latency increase."""
        num_affected = self.rng.randint(1, min(3, len(features)))
        affected = self.rng.sample(range(len(features)), num_affected)

        for idx in affected:
            f = features[idx]
            # CPU spikes
            f["cpu"] = round(min(1.0, self.rng.uniform(0.85, 0.99)), 3)
            # Memory spikes
            f["memory"] = round(min(1.0, self.rng.uniform(0.80, 0.98)), 3)
            # Latency increases due to processing delays
            f["latency"] = round(f["latency"] * self.rng.uniform(3.0, 10.0), 2)
            # Loss rate increases under load
            f["loss_rate"] = round(
                min(0.5, f["loss_rate"] + self.rng.uniform(0.05, 0.2)), 4
            )
            # Throughput drops from congestion
            f["throughput"] = round(max(0.1, f["throughput"] * 0.3), 2)
            labels[idx] = 1.0

    def _apply_cascade_failure(
        self,
        features: List[Dict[str, float]],
        labels: List[float],
        edges: List[Tuple[int, int]],
    ):
        """One node fails, then neighbors degrade (cascade)."""
        # Pick a seed node
        seed_node = self.rng.randint(0, len(features) - 1)

        # Find neighbors
        neighbors = set()
        for src, tgt in edges:
            if src == seed_node:
                neighbors.add(tgt)
            elif tgt == seed_node:
                neighbors.add(src)

        # Seed node: severe failure
        f = features[seed_node]
        f["cpu"] = 0.99
        f["memory"] = 0.97
        f["loss_rate"] = round(self.rng.uniform(0.3, 0.8), 4)
        f["latency"] = round(self.rng.uniform(200, 1000), 2)
        f["throughput"] = round(self.rng.uniform(0.01, 0.5), 2)
        labels[seed_node] = 1.0

        # Neighbors: moderate degradation (cascade effect)
        for nbr in neighbors:
            if nbr < len(features):
                nf = features[nbr]
                cascade_severity = self.rng.uniform(0.3, 0.7)
                nf["loss_rate"] = round(
                    min(0.5, nf["loss_rate"] + cascade_severity * 0.1), 4
                )
                nf["latency"] = round(nf["latency"] * (1 + cascade_severity * 3), 2)
                nf["throughput"] = round(
                    max(0.1, nf["throughput"] * (1 - cascade_severity * 0.4)), 2
                )
                nf["cpu"] = round(min(1.0, nf["cpu"] + cascade_severity * 0.2), 3)
                labels[nbr] = 1.0

    def _apply_interference(
        self,
        features: List[Dict[str, float]],
        labels: List[float],
    ):
        """RF interference affects a region of nodes (30-60% of network)."""
        num_affected = self.rng.randint(
            len(features) * 3 // 10, len(features) * 6 // 10
        )
        # Contiguous region (nodes with consecutive IDs)
        start = self.rng.randint(0, len(features) - num_affected)
        affected = list(range(start, start + num_affected))

        for idx in affected:
            f = features[idx]
            interference_db = self.rng.uniform(10, 25)
            f["snr"] = round(max(1.0, f["snr"] - interference_db), 2)
            f["rssi"] = round(f["rssi"] - interference_db * 0.5, 2)
            f["loss_rate"] = round(
                min(0.6, f["loss_rate"] + 0.03 * interference_db / 10), 4
            )
            f["throughput"] = round(
                max(0.1, f["throughput"] * (1 - interference_db / 40)), 2
            )
            labels[idx] = 1.0

    def _apply_partition(
        self,
        features: List[Dict[str, float]],
        labels: List[float],
        edges: List[Tuple[int, int]],
    ):
        """Network partition: a group of nodes loses connectivity."""
        partition_size = self.rng.randint(2, max(2, len(features) // 4))
        partitioned = self.rng.sample(range(len(features)), partition_size)
        partitioned_set = set(partitioned)

        for idx in partitioned:
            f = features[idx]
            # Links to outside partition "die"
            f["rssi"] = round(self.rng.uniform(-95, -88), 2)
            f["snr"] = round(self.rng.uniform(0, 5), 2)
            f["loss_rate"] = round(self.rng.uniform(0.5, 1.0), 4)
            f["latency"] = round(self.rng.uniform(500, 5000), 2)
            f["throughput"] = round(self.rng.uniform(0.0, 0.5), 2)
            f["link_age"] = round(self.rng.uniform(0, 5), 1)
            labels[idx] = 1.0


def generate_training_data(
    num_snapshots: int = 200,
    nodes_per_snapshot: int = 20,
    anomaly_ratio: float = 0.3,
    seed: int = 42,
) -> Tuple[List[Dict[str, float]], List[Tuple[int, int]], List[float]]:
    """
    Convenience function: generate flattened training data for GraphSAGE.

    Returns:
        (all_node_features, all_edges, all_labels) aggregated across snapshots.
    """
    gen = MeshTelemetryGenerator(seed=seed)
    snapshots = gen.generate_dataset(num_snapshots, nodes_per_snapshot, anomaly_ratio)

    all_features = []
    all_edges = []
    all_labels = []
    offset = 0

    for snap in snapshots:
        all_features.extend(snap.node_features)
        # Offset edge indices for the combined graph
        all_edges.extend((s + offset, t + offset) for s, t in snap.edge_index)
        all_labels.extend(snap.labels)
        offset += snap.num_nodes

    logger.info(
        f"Generated training data: {len(all_features)} nodes, "
        f"{len(all_edges)} edges, "
        f"{sum(1 for l in all_labels if l > 0.5)} anomalies "
        f"({sum(1 for l in all_labels if l > 0.5)/len(all_labels)*100:.1f}%)"
    )
    return all_features, all_edges, all_labels
