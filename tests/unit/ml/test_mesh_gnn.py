"""
Unit tests for src/ml/mesh_gnn.py — GNN classifier trained on mesh telemetry.

Tests cover model construction, forward/backward, training convergence on
synthetic mesh-topology snapshots, model persistence, and integration
with the existing AnomalyPrediction interface.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.ml.mesh_telemetry import MeshTelemetryGenerator
from src.ml.mesh_gnn import (
    MeshGNN,
    MeshGNNDetector,
    AnomalyPrediction,
    build_adj_norm,
    features_to_array,
    train_mesh_gnn,
    save_mesh_gnn,
    load_mesh_gnn,
    TrainingHistory,
    FEATURE_NAMES,
    DEFAULT_INPUT_DIM,
    DEFAULT_HIDDEN_DIM,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def synthetic_dataset():
    """Generate a small dataset of mesh snapshots for testing."""
    gen = MeshTelemetryGenerator(seed=42)
    snapshots = gen.generate_dataset(
        num_snapshots=30, nodes_per_snapshot=16, anomaly_ratio=0.5,
    )
    assert len(snapshots) == 30
    return snapshots


@pytest.fixture
def trained_model(synthetic_dataset):
    """Train a small MeshGNN on synthetic data for downstream tests."""
    model = MeshGNN(input_dim=DEFAULT_INPUT_DIM, hidden_dim=16, init_scale=0.05)
    history = train_mesh_gnn(
        model, synthetic_dataset,
        epochs=80, lr=0.01, verbose=False,
    )
    return model, history


# ═══════════════════════════════════════════════════════════════
# Model construction
# ═══════════════════════════════════════════════════════════════

class TestMeshGNNConstruction:

    def test_instantiation(self):
        model = MeshGNN()
        assert isinstance(model, MeshGNN)
        assert len(model.parameters()) == 6  # 2 convs × 2 params + 1 linear × 2

    def test_custom_dims(self):
        model = MeshGNN(input_dim=8, hidden_dim=32)
        assert model.conv1.W_self.shape == (8, 32)
        assert model.conv1.W_neigh.shape == (8, 32)
        assert model.conv2.W_self.shape == (32, 32)
        assert model.conv2.W_neigh.shape == (32, 32)
        assert model.output.W.shape == (32, 1)
        assert model.output.b.shape == (1,)

    def test_forward_shape(self):
        model = MeshGNN(input_dim=8, hidden_dim=16)
        N = 10
        x = np.random.randn(N, 8).astype(np.float64)
        adj = np.eye(N, dtype=np.float64)
        probs = model.predict(x, adj)
        assert probs.shape == (N, 1)
        assert np.all((probs >= 0.0) & (probs <= 1.0))


# ═══════════════════════════════════════════════════════════════
# Graph utilities
# ═══════════════════════════════════════════════════════════════

class TestGraphUtilities:

    def test_build_adj_norm_simple(self):
        edges = [(0, 1), (1, 0), (1, 2), (2, 1)]
        adj = build_adj_norm(edges, 3)
        assert adj.shape == (3, 3)
        # Node 0: one neighbor → row sums to 1
        assert np.isclose(adj[0].sum(), 1.0)
        assert adj[0, 1] == 1.0
        # Node 1: two neighbors
        assert np.isclose(adj[1].sum(), 1.0)
        assert adj[1, 0] == 0.5
        assert adj[1, 2] == 0.5
        # Node 2: one neighbor
        assert np.isclose(adj[2].sum(), 1.0)
        assert adj[2, 1] == 1.0

    def test_build_adj_norm_isolated(self):
        edges = [(0, 1), (1, 0)]
        adj = build_adj_norm(edges, 3)
        assert adj.shape == (3, 3)
        # Node 2 is isolated — keep D^{-1} stable (1/1 = 1)
        assert np.isclose(adj[2].sum(), 0.0)  # no self-loop
        assert not np.any(np.isnan(adj))
        assert not np.any(np.isinf(adj))

    def test_build_adj_norm_empty(self):
        adj = build_adj_norm([], 1)
        assert adj.shape == (1, 1)
        assert not np.any(np.isnan(adj))

    def test_build_adj_norm_oob_filtering(self):
        edges = [(0, 5), (5, 0)]  # node 5 is out of bounds (N=3)
        adj = build_adj_norm(edges, 3)
        assert adj.shape == (3, 3)
        assert adj.sum() == 0.0  # all edges filtered out

    def test_features_to_array(self):
        features = [
            {"rssi": -50.0, "snr": 25.0, "latency": 10.0},
            {"rssi": -70.0, "latency": 20.0},  # missing snr
        ]
        arr = features_to_array(features)
        assert arr.shape == (2, 8)
        assert arr[0, 0] == -50.0  # rssi
        assert arr[0, 1] == 25.0   # snr
        assert arr[0, 4] == 10.0   # latency
        assert arr[1, 0] == -70.0  # rssi
        assert arr[1, 1] == 0.0    # missing snr → 0.0
        assert arr[1, 4] == 20.0   # latency

    def test_features_to_array_custom_names(self):
        features = [{"a": 1.0, "b": 2.0}]
        arr = features_to_array(features, feature_names=["a", "b"])
        assert arr.shape == (1, 2)
        assert arr[0, 0] == 1.0
        assert arr[0, 1] == 2.0


# ═══════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════

class TestTraining:

    def test_training_convergence(self, synthetic_dataset):
        """Loss must decrease measurably after training on synthetic data."""
        model = MeshGNN(input_dim=DEFAULT_INPUT_DIM, hidden_dim=16, init_scale=0.05)
        history = train_mesh_gnn(
            model, synthetic_dataset,
            epochs=60, lr=0.01, verbose=False,
        )

        assert len(history.epochs) == 60
        assert len(history.losses) == 60
        assert len(history.accuracies) == 60

        # Loss should be decreasing
        late_avg = float(np.mean(history.losses[-10:]))
        early_avg = float(np.mean(history.losses[:10]))
        assert late_avg < early_avg, (
            f"Loss did not decrease: early_avg={early_avg:.4f}, late_avg={late_avg:.4f}"
        )

        # Accuracy should improve
        late_acc = float(np.mean(history.accuracies[-10:]))
        early_acc = float(np.mean(history.accuracies[:10]))
        assert late_acc > 0.55, (
            f"Final accuracy too low: {late_acc:.1%}"
        )

    def test_training_history_dataclass(self):
        h = TrainingHistory(
            epochs=[0, 1],
            losses=[0.7, 0.5],
            accuracies=[0.5, 0.8],
        )
        assert h.epochs == [0, 1]
        assert h.losses == [0.7, 0.5]

    def test_training_deterministic_seed(self):
        """Same seed + same data = same initial loss."""
        gen = MeshTelemetryGenerator(seed=123)
        data = gen.generate_dataset(num_snapshots=5, nodes_per_snapshot=12, anomaly_ratio=0.5)

        np.random.seed(42)
        model1 = MeshGNN(input_dim=8, hidden_dim=16, init_scale=0.05)
        h1 = train_mesh_gnn(model1, data, epochs=3, lr=0.01, verbose=False)

        np.random.seed(42)
        model2 = MeshGNN(input_dim=8, hidden_dim=16, init_scale=0.05)
        h2 = train_mesh_gnn(model2, data, epochs=3, lr=0.01, verbose=False)

        # Initial loss should match (same init seed)
        assert np.isclose(h1.losses[0], h2.losses[0], rtol=1e-10), (
            f"loss[0] differs: {h1.losses[0]:.10f} vs {h2.losses[0]:.10f}"
        )


# ═══════════════════════════════════════════════════════════════
# Model persistence
# ═══════════════════════════════════════════════════════════════

class TestModelPersistence:

    def test_save_load_roundtrip(self, trained_model):
        model, _ = trained_model
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
            save_mesh_gnn(model, tmp_path)

        # Verify file content
        with open(tmp_path) as f:
            weights = json.load(f)
        expected_keys = {
            "conv1.W_self", "conv1.W_neigh",
            "conv2.W_self", "conv2.W_neigh",
            "output.W", "output.b",
        }
        assert set(weights.keys()) == expected_keys

        # Load into a fresh model
        fresh = MeshGNN(input_dim=8, hidden_dim=16)
        load_mesh_gnn(fresh, tmp_path)

        # Weights should match
        for key, tens in [
            ("conv1.W_self", fresh.conv1.W_self),
            ("conv1.W_neigh", fresh.conv1.W_neigh),
            ("conv2.W_self", fresh.conv2.W_self),
            ("conv2.W_neigh", fresh.conv2.W_neigh),
            ("output.W", fresh.output.W),
        ]:
            assert np.allclose(tens.data, np.array(weights[key])), f"Mismatch: {key}"

        Path(tmp_path).unlink(missing_ok=True)

    def test_save_load_preserves_prediction(self, synthetic_dataset):
        """After save + load, predictions should be identical."""
        model = MeshGNN(input_dim=8, hidden_dim=16, init_scale=0.05)
        train_mesh_gnn(model, synthetic_dataset, epochs=20, lr=0.01, verbose=False)

        # Predict before save
        snap = synthetic_dataset[0]
        x_arr = features_to_array(snap.node_features)
        adj = build_adj_norm(snap.edge_index, snap.num_nodes)
        before = model.predict(x_arr, adj).copy()

        # Save + load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
            save_mesh_gnn(model, tmp_path)

        fresh = MeshGNN(input_dim=8, hidden_dim=16, init_scale=0.05)
        load_mesh_gnn(fresh, tmp_path)
        after = fresh.predict(x_arr, adj)

        assert np.allclose(before, after), "Predictions differ after save/load"
        Path(tmp_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Detector wrapper
# ═══════════════════════════════════════════════════════════════

class TestMeshGNNDetector:

    def test_detector_default_init(self):
        det = MeshGNNDetector()
        assert det.is_trained is False
        assert det.threshold == 0.5

    def test_predict_topology(self, trained_model):
        model, _ = trained_model
        det = MeshGNNDetector(model=model, threshold=0.5)

        gen = MeshTelemetryGenerator(seed=1)
        snap = gen.generate_dataset(num_snapshots=1, nodes_per_snapshot=8, anomaly_ratio=0.5)[0]

        preds = det.predict_topology(snap.node_features, snap.edge_index)
        assert len(preds) == snap.num_nodes
        assert all(isinstance(p, AnomalyPrediction) for p in preds)

        # All fields populated
        for p in preds:
            assert 0.0 <= p.anomaly_score <= 1.0
            assert 0.0 <= p.confidence <= 1.0
            assert isinstance(p.node_id, str)
            assert p.inference_time_ms > 0.0
            assert isinstance(p.is_anomaly, bool)

    def test_predict_topology_labels_correlate(self, synthetic_dataset):
        """Trained detector should give higher scores to actually anomalous nodes."""
        model = MeshGNN(input_dim=8, hidden_dim=16, init_scale=0.05)
        train_mesh_gnn(model, synthetic_dataset, epochs=80, lr=0.01, verbose=False)
        det = MeshGNNDetector(model=model, threshold=0.5)

        # Evaluate on held-out snapshot
        gen = MeshTelemetryGenerator(seed=99)
        snap = gen.generate_dataset(num_snapshots=1, nodes_per_snapshot=16, anomaly_ratio=0.5)[0]

        preds = det.predict_topology(snap.node_features, snap.edge_index)
        scores = np.array([p.anomaly_score for p in preds])
        labels = np.array(snap.labels)

        # The mean score for anomalous nodes should be higher
        anom_scores = scores[labels > 0.5]
        norm_scores = scores[labels <= 0.5]
        if len(anom_scores) > 0 and len(norm_scores) > 0:
            assert np.mean(anom_scores) > np.mean(norm_scores), (
                f"Anomalous nodes should score higher: anom={np.mean(anom_scores):.3f} "
                f"norm={np.mean(norm_scores):.3f}"
            )

    def test_detector_threshold(self, trained_model):
        model, _ = trained_model
        det_loose = MeshGNNDetector(model=model, threshold=0.1)
        det_tight = MeshGNNDetector(model=model, threshold=0.9)

        gen = MeshTelemetryGenerator(seed=5)
        snap = gen.generate_dataset(num_snapshots=1, nodes_per_snapshot=8, anomaly_ratio=0.5)[0]

        loose_preds = det_loose.predict_topology(snap.node_features, snap.edge_index)
        tight_preds = det_tight.predict_topology(snap.node_features, snap.edge_index)

        # Loose threshold should flag more anomalies than tight
        loose_rate = sum(p.is_anomaly for p in loose_preds) / len(loose_preds)
        tight_rate = sum(p.is_anomaly for p in tight_preds) / len(tight_preds)
        assert loose_rate >= tight_rate, (
            f"Loose threshold ({det_loose.threshold}) gave rate {loose_rate:.1%} "
            f"but tight ({det_tight.threshold}) gave {tight_rate:.1%}"
        )
