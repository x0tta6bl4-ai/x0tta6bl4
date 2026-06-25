"""
Mesh GNN — Graph Neural Network classifier for mesh network anomaly detection.

Built entirely on micro_tensor (NumPy autograd engine). No PyTorch required.

Architecture:
    SAGEConv(input→hidden1) → ReLU → SAGEConv(hidden1→hidden2) → ReLU
    → Linear(hidden2→1) → sigmoid (binary anomaly classification)

Integrates with existing GraphSAGEAnomalyDetector via AnomalyPrediction interface.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.ml.micro_tensor import (
    Tensor,
    Linear,
    SAGEConv,
    ReLU,
    BCELoss,
    Adam,
)

logger = logging.getLogger(__name__)

FEATURE_NAMES = ["rssi", "snr", "loss_rate", "link_age",
                 "latency", "throughput", "cpu", "memory"]
DEFAULT_INPUT_DIM = 8
DEFAULT_HIDDEN_DIM = 64
DEFAULT_EPOCHS = 100
DEFAULT_LR = 0.005


# ═══════════════════════════════════════════════════════════════
# GNN Model
# ═══════════════════════════════════════════════════════════════

class MeshGNN:
    """Two-layer GraphSAGE-based GNN for node-level anomaly classification.

    SAGEConv(input_dim → hidden_dim) → ReLU → SAGEConv(hidden_dim → hidden_dim)
    → ReLU → Linear(hidden_dim → 1) → sigmoid

    Args:
        input_dim: number of input features per node
        hidden_dim: number of hidden units in each SAGEConv layer
        init_scale: weight initialisation standard deviation
    """

    def __init__(
        self,
        input_dim: int = DEFAULT_INPUT_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        *,
        init_scale: float = 0.05,
    ) -> None:
        self.conv1 = SAGEConv(input_dim, hidden_dim, init_scale=init_scale)
        self.relu1 = ReLU()
        self.conv2 = SAGEConv(hidden_dim, hidden_dim, init_scale=init_scale)
        self.relu2 = ReLU()
        self.output = Linear(hidden_dim, 1, init_scale=init_scale)
        self.bce = BCELoss()

    def parameters(self):
        return (self.conv1.parameters() + self.conv2.parameters()
                + self.output.parameters())

    def forward(self, x: Tensor, adj_norm: np.ndarray) -> Tensor:
        """Forward pass: node features → node-level anomaly logits.

        Args:
            x: node features (N, input_dim)
            adj_norm: D^{-1}A normalised adjacency (N, N)

        Returns:
            anomaly logits (N, 1)
        """
        h = self.conv1(x, adj_norm)
        h = self.relu1(h)
        h = self.conv2(h, adj_norm)
        h = self.relu2(h)
        logits = self.output(h)
        return logits

    def predict(self, x: np.ndarray, adj_norm: np.ndarray) -> np.ndarray:
        """NumPy-in/NumPy-out prediction (no grad tracking)."""
        x_t = Tensor(x, requires_grad=False)
        logits = self.forward(x_t, adj_norm)
        clipped = np.clip(logits.data, -100.0, 100.0)
        sig = 1.0 / (1.0 + np.exp(-clipped))
        return sig

    def predict_proba(self, x: np.ndarray, adj_norm: np.ndarray) -> np.ndarray:
        """Return sigmoid probabilities (0-1)."""
        return self.predict(x, adj_norm)


# ═══════════════════════════════════════════════════════════════
# Graph utilities
# ═══════════════════════════════════════════════════════════════

def build_adj_norm(
    edge_index: List[Tuple[int, int]],
    num_nodes: int,
) -> np.ndarray:
    """Build D^{-1}A normalised adjacency from an edge list.

    Args:
        edge_index: list of (src, dst) directed edges
        num_nodes: total number of nodes

    Returns:
        (num_nodes, num_nodes) adjacency normalised by row degree.
    """
    adj = np.zeros((num_nodes, num_nodes), dtype=np.float64)
    for src, dst in edge_index:
        if src < num_nodes and dst < num_nodes:
            adj[src, dst] = 1.0
    deg = adj.sum(axis=1, keepdims=True)
    deg[deg == 0] = 1.0
    return adj / deg


def features_to_array(
    node_features: List[Dict[str, float]],
    feature_names: List[str] | None = None,
) -> np.ndarray:
    """Convert list-of-dict features to (N, F) float64 array.

    Missing keys are filled with 0.0.
    """
    names = feature_names or FEATURE_NAMES
    arr = np.zeros((len(node_features), len(names)), dtype=np.float64)
    for i, feat in enumerate(node_features):
        for j, name in enumerate(names):
            arr[i, j] = float(feat.get(name, 0.0))
    return arr


# ═══════════════════════════════════════════════════════════════
# Trainer
# ═══════════════════════════════════════════════════════════════

@dataclass
class TrainingHistory:
    """Loss and accuracy per epoch."""
    epochs: List[int] = field(default_factory=list)
    losses: List[float] = field(default_factory=list)
    accuracies: List[float] = field(default_factory=list)


def train_mesh_gnn(
    model: MeshGNN,
    snapshots: list,
    *,
    epochs: int = DEFAULT_EPOCHS,
    lr: float = DEFAULT_LR,
    verbose: bool = True,
) -> TrainingHistory:
    """Train a MeshGNN on a list of mesh snapshots.

    Each snapshot must have:
        .node_features: List[Dict[str, float]]
        .edge_index: List[Tuple[int, int]]
        .labels: List[float]

    Args:
        model: MeshGNN instance
        snapshots: list of mesh telemetry snapshots (e.g. MeshSnapshot)
        epochs: number of full passes over the dataset
        lr: Adam learning rate
        verbose: print epoch logs

    Returns:
        TrainingHistory with per-epoch metrics.
    """
    opt = Adam(model.parameters(), lr=lr)
    history = TrainingHistory()

    for epoch in range(epochs):
        epoch_loss = 0.0
        epoch_accy = 0.0
        n = 0

        for snap in snapshots:
            x_arr = features_to_array(snap.node_features)
            adj_norm = build_adj_norm(snap.edge_index, snap.num_nodes)
            targets = Tensor(np.array(snap.labels, dtype=np.float64).reshape(-1, 1))

            x = Tensor(x_arr, requires_grad=False)

            opt.zero_grad()
            logits = model.forward(x, adj_norm)
            loss = model.bce(logits, targets)
            loss.backward()
            opt.step()

            # Accuracy — clip to prevent exp overflow for extreme logits
            clipped = np.clip(logits.data, -100.0, 100.0)
            probs = 1.0 / (1.0 + np.exp(-clipped))
            preds = (probs >= 0.5).astype(np.float64)

            batch_size = snap.num_nodes
            epoch_loss += float(loss.data) * batch_size
            epoch_accy += float(np.mean(preds == targets.data)) * batch_size
            n += batch_size

        avg_loss = epoch_loss / n
        avg_accy = epoch_accy / n
        history.epochs.append(epoch)
        history.losses.append(avg_loss)
        history.accuracies.append(avg_accy)

        if verbose and (epoch % 10 == 0 or epoch == epochs - 1):
            logger.info(
                f"Epoch {epoch:3d}/{epochs}  loss={avg_loss:.4f}  acc={avg_accy:.1%}")

    return history


# ═══════════════════════════════════════════════════════════════
# Model persistence
# ═══════════════════════════════════════════════════════════════

def save_mesh_gnn(model: MeshGNN, path: str | Path) -> None:
    """Save trained model weights to a JSON file.

    Args:
        model: trained MeshGNN
        path: save path (.json recommended)
    """
    weights = {
        "conv1.W_self": model.conv1.W_self.data.tolist(),
        "conv1.W_neigh": model.conv1.W_neigh.data.tolist(),
        "conv2.W_self": model.conv2.W_self.data.tolist(),
        "conv2.W_neigh": model.conv2.W_neigh.data.tolist(),
        "output.W": model.output.W.data.tolist(),
        "output.b": model.output.b.data.tolist() if model.output.b is not None else None,
    }
    with open(path, "w") as f:
        json.dump(weights, f)
    logger.info(f"Model saved to {path} ({sum(v is not None for v in weights.values())} layers)")


def load_mesh_gnn(model: MeshGNN, path: str | Path) -> None:
    """Load model weights from a JSON file.

    Args:
        model: MeshGNN instance (architecture must match the saved weights)
        path: path to JSON weight file
    """
    with open(path) as f:
        weights = json.load(f)

    model.conv1.W_self.data[:] = np.array(weights["conv1.W_self"])
    model.conv1.W_neigh.data[:] = np.array(weights["conv1.W_neigh"])
    model.conv2.W_self.data[:] = np.array(weights["conv2.W_self"])
    model.conv2.W_neigh.data[:] = np.array(weights["conv2.W_neigh"])
    model.output.W.data[:] = np.array(weights["output.W"])
    if model.output.b is not None and weights.get("output.b") is not None:
        model.output.b.data[:] = np.array(weights["output.b"])

    logger.info(f"Model loaded from {path}")


# ═══════════════════════════════════════════════════════════════
# Detector wrapper — integrates with GraphSAGEAnomalyDetector
# interface (AnomalyPrediction)
# ═══════════════════════════════════════════════════════════════

@dataclass
class AnomalyPrediction:
    """Anomaly detection prediction result — matches the existing interface."""
    is_anomaly: bool
    anomaly_score: float
    confidence: float
    node_id: str
    features: Dict[str, float]
    inference_time_ms: float


class MeshGNNDetector:
    """Wrapper that runs MeshGNN on live topology and returns AnomalyPredictions.

    Args:
        model: trained MeshGNN (or None to use default init)
        threshold: score ≥ threshold → anomaly flagged
    """

    def __init__(
        self,
        model: MeshGNN | None = None,
        threshold: float = 0.5,
    ) -> None:
        self.model = model or MeshGNN()
        self.threshold = threshold
        self._is_trained = False

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def predict_node(
        self,
        node_features: Dict[str, float],
        edge_index: List[Tuple[int, int]],
        num_nodes: int,
        node_idx: int,
    ) -> AnomalyPrediction:
        """Predict anomaly for a single node in the topology."""
        t0 = time.perf_counter()

        # Build full graph
        x_arr = np.zeros((num_nodes, DEFAULT_INPUT_DIM), dtype=np.float64)
        for i, feat in enumerate([node_features] if num_nodes == 1 else [{}] * num_nodes):
            pass  # We only have one node's features — use a simplified path

        # More generically, need all node features — but the single-node API
        # is limited. For production the caller should pass all nodes.
        # Fallback: build from whatever we have
        if isinstance(node_features, dict):
            # Assume it's a full list passed as first arg
            x_arr = features_to_array([node_features] * num_nodes)
        else:
            x_arr = features_to_array(node_features)

        adj_norm = build_adj_norm(edge_index, num_nodes)
        probs = self.model.predict(x_arr, adj_norm)
        score = float(probs[node_idx, 0])
        confidence = abs(score - 0.5) * 2.0  # 0.5→0.0, 0.0 or 1.0→1.0
        elapsed = (time.perf_counter() - t0) * 1000.0

        return AnomalyPrediction(
            is_anomaly=score >= self.threshold,
            anomaly_score=round(score, 4),
            confidence=round(min(1.0, confidence), 4),
            node_id=str(node_idx),
            features=node_features if isinstance(node_features, dict) else {},
            inference_time_ms=round(elapsed, 2),
        )

    def predict_topology(
        self,
        node_features: List[Dict[str, float]],
        edge_index: List[Tuple[int, int]],
    ) -> List[AnomalyPrediction]:
        """Predict anomalies for all nodes in the topology at once."""
        t0 = time.perf_counter()
        num_nodes = len(node_features)
        x_arr = features_to_array(node_features)
        adj_norm = build_adj_norm(edge_index, num_nodes)
        probs = self.model.predict(x_arr, adj_norm)
        elapsed = (time.perf_counter() - t0) * 1000.0

        predictions = []
        for i in range(num_nodes):
            score = float(probs[i, 0])
            confidence = abs(score - 0.5) * 2.0
            predictions.append(AnomalyPrediction(
                is_anomaly=score >= self.threshold,
                anomaly_score=round(score, 4),
                confidence=round(min(1.0, confidence), 4),
                node_id=str(i),
                features=node_features[i] if isinstance(node_features[i], dict) else {},
                inference_time_ms=round(elapsed, 2),
            ))
        return predictions
