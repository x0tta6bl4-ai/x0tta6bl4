"""
Unit tests for mesh telemetry generator.
"""

import pytest

from src.ml.mesh_telemetry import (FEATURE_NAMES, MeshSnapshot,
                                   MeshTelemetryGenerator, ScenarioType,
                                   generate_training_data)


class TestMeshTelemetryGenerator:
    def setup_method(self):
        self.gen = MeshTelemetryGenerator(seed=42)

    def test_generate_dataset_size(self):
        snapshots = self.gen.generate_dataset(num_snapshots=50, nodes_per_snapshot=10)
        assert len(snapshots) == 50

    def test_generate_dataset_has_both_classes(self):
        snapshots = self.gen.generate_dataset(num_snapshots=100, anomaly_ratio=0.3)
        normal = sum(1 for s in snapshots if s.scenario == ScenarioType.NORMAL)
        anomalous = sum(1 for s in snapshots if s.scenario != ScenarioType.NORMAL)
        assert normal == 70
        assert anomalous == 30

    def test_snapshot_has_all_features(self):
        snapshots = self.gen.generate_dataset(num_snapshots=1, nodes_per_snapshot=5)
        snap = snapshots[0]
        for node_feat in snap.node_features:
            for name in FEATURE_NAMES:
                assert name in node_feat, f"Missing feature: {name}"

    def test_snapshot_has_labels(self):
        snapshots = self.gen.generate_dataset(num_snapshots=10, nodes_per_snapshot=10)
        for snap in snapshots:
            assert len(snap.labels) == snap.num_nodes
            for label in snap.labels:
                assert label in (0.0, 1.0)

    def test_normal_snapshot_no_anomalies(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.NORMAL)
        assert snap.num_anomalous == 0
        assert all(l == 0.0 for l in snap.labels)

    def test_link_degradation_has_anomalies(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.LINK_DEGRADATION)
        assert snap.num_anomalous > 0
        # Affected nodes should have degraded loss rate
        for i, label in enumerate(snap.labels):
            if label == 1.0:
                assert snap.node_features[i]["loss_rate"] > 0.02

    def test_node_overload_has_high_cpu(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.NODE_OVERLOAD)
        assert snap.num_anomalous > 0
        for i, label in enumerate(snap.labels):
            if label == 1.0:
                assert snap.node_features[i]["cpu"] > 0.8

    def test_cascade_failure_affects_neighbors(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.CASCADE_FAILURE)
        # At least 2 anomalous nodes (seed + at least 1 neighbor)
        assert snap.num_anomalous >= 2

    def test_interference_affects_region(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.INTERFERENCE)
        assert snap.num_anomalous >= 6  # 30% of 20

    def test_partition_has_anomalies(self):
        snap = self.gen._generate_snapshot(20, ScenarioType.PARTITION)
        assert snap.num_anomalous >= 2
        for i, label in enumerate(snap.labels):
            if label == 1.0:
                assert snap.node_features[i]["loss_rate"] > 0.3

    def test_edges_are_valid(self):
        snap = self.gen._generate_snapshot(15, ScenarioType.NORMAL)
        for src, tgt in snap.edge_index:
            assert 0 <= src < snap.num_nodes
            assert 0 <= tgt < snap.num_nodes
            assert src != tgt

    def test_feature_ranges_normal(self):
        """Normal features should be within physical bounds."""
        snap = self.gen._generate_snapshot(50, ScenarioType.NORMAL)
        for f in snap.node_features:
            assert -100 <= f["rssi"] <= 0
            assert 0 <= f["snr"] <= 50
            assert 0 <= f["loss_rate"] <= 1.0
            assert f["link_age"] >= 0
            assert f["latency"] >= 0
            assert f["throughput"] >= 0
            assert 0 <= f["cpu"] <= 1.0
            assert 0 <= f["memory"] <= 1.0

    def test_reproducibility(self):
        gen1 = MeshTelemetryGenerator(seed=123)
        gen2 = MeshTelemetryGenerator(seed=123)
        snap1 = gen1._generate_snapshot(10, ScenarioType.NORMAL)
        snap2 = gen2._generate_snapshot(10, ScenarioType.NORMAL)
        assert snap1.node_features == snap2.node_features

    def test_different_seeds_differ(self):
        gen1 = MeshTelemetryGenerator(seed=1)
        gen2 = MeshTelemetryGenerator(seed=2)
        snap1 = gen1._generate_snapshot(10, ScenarioType.NORMAL)
        snap2 = gen2._generate_snapshot(10, ScenarioType.NORMAL)
        assert snap1.node_features != snap2.node_features


class TestGenerateTrainingData:
    def test_returns_correct_types(self):
        features, edges, labels = generate_training_data(
            num_snapshots=10, nodes_per_snapshot=5, seed=42
        )
        assert isinstance(features, list)
        assert isinstance(edges, list)
        assert isinstance(labels, list)

    def test_aggregated_size(self):
        features, edges, labels = generate_training_data(
            num_snapshots=10, nodes_per_snapshot=5, seed=42
        )
        assert len(features) == 50  # 10 * 5
        assert len(labels) == 50

    def test_has_anomaly_labels(self):
        features, edges, labels = generate_training_data(
            num_snapshots=50, nodes_per_snapshot=10, anomaly_ratio=0.4, seed=42
        )
        num_anomalies = sum(1 for l in labels if l > 0.5)
        assert num_anomalies > 0
        # Not all should be anomalies
        assert num_anomalies < len(labels)

    def test_edge_indices_valid(self):
        features, edges, labels = generate_training_data(
            num_snapshots=5, nodes_per_snapshot=10, seed=42
        )
        num_nodes = len(features)
        for src, tgt in edges:
            assert 0 <= src < num_nodes
            assert 0 <= tgt < num_nodes
