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
EDGE_FEATURE_NAMES = [
    "rssi_diff", "snr_diff", "loss_sum", "latency_diff", "throughput_sum",
]
DEFAULT_EDGE_FEAT_DIM = len(EDGE_FEATURE_NAMES)
DEFAULT_EPOCHS = 100
DEFAULT_LR = 0.005


# ═══════════════════════════════════════════════════════════════
# GNN Model
# ═══════════════════════════════════════════════════════════════

class MeshGNN:
    """Two-layer GraphSAGE-based GNN for node-level anomaly classification.

    SAGEConv(input_dim → hidden_dim) → ReLU → SAGEConv(hidden_dim → hidden_dim)
    → ReLU → Linear(hidden_dim → 1) → sigmoid

    When *edge_feat_dim* is set, the model uses edge features computed from
    node feature differences (asymmetry + sum of correlated metrics).

    Args:
        input_dim: number of input features per node
        hidden_dim: number of hidden units in each SAGEConv layer
        edge_feat_dim: number of edge features (0 to disable)
        init_scale: weight initialisation standard deviation
    """

    def __init__(
        self,
        input_dim: int = DEFAULT_INPUT_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        *,
        edge_feat_dim: int = 0,
        init_scale: float = 0.05,
    ) -> None:
        self.conv1 = SAGEConv(input_dim, hidden_dim,
                              edge_feat_dim=edge_feat_dim if edge_feat_dim > 0 else None,
                              init_scale=init_scale)
        self.relu1 = ReLU()
        self.conv2 = SAGEConv(hidden_dim, hidden_dim,
                              edge_feat_dim=edge_feat_dim if edge_feat_dim > 0 else None,
                              init_scale=init_scale)
        self.relu2 = ReLU()
        self.output = Linear(hidden_dim, 1, init_scale=init_scale)
        self.bce = BCELoss()
        self._edge_feat_dim = edge_feat_dim

    def parameters(self):
        return (self.conv1.parameters() + self.conv2.parameters()
                + self.output.parameters())

    def forward(
        self,
        x: Tensor,
        adj_norm: np.ndarray,
        edge_index: np.ndarray | None = None,
        edge_attr: np.ndarray | None = None,
    ) -> Tensor:
        """Forward pass: node features → node-level anomaly logits.

        Args:
            x: node features (N, input_dim)
            adj_norm: D^{-1}A normalised adjacency (N, N)
            edge_index: optional (M, 2) edge indices
            edge_attr: optional (M, F) edge feature vectors

        Returns:
            anomaly logits (N, 1)
        """
        h = self.conv1(x, adj_norm, edge_index, edge_attr)
        h = self.relu1(h)
        h = self.conv2(h, adj_norm, edge_index, edge_attr)
        h = self.relu2(h)
        logits = self.output(h)
        return logits

    def predict(
        self,
        x: np.ndarray,
        adj_norm: np.ndarray,
        edge_index: np.ndarray | None = None,
        edge_attr: np.ndarray | None = None,
    ) -> np.ndarray:
        """NumPy-in/NumPy-out prediction (no grad tracking)."""
        x_t = Tensor(x, requires_grad=False)
        logits = self.forward(x_t, adj_norm, edge_index, edge_attr)
        clipped = np.clip(logits.data, -100.0, 100.0)
        sig = 1.0 / (1.0 + np.exp(-clipped))
        return sig

    def predict_proba(
        self,
        x: np.ndarray,
        adj_norm: np.ndarray,
        edge_index: np.ndarray | None = None,
        edge_attr: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return sigmoid probabilities (0-1)."""
        return self.predict(x, adj_norm, edge_index, edge_attr)


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


def build_edge_index_array(
    edge_index: List[Tuple[int, int]],
    num_nodes: int,
) -> np.ndarray:
    """Convert edge list to (M, 2) numpy array of int64.

    Filters out-of-bound node references.
    """
    filtered = [(s, d) for s, d in edge_index
                if s < num_nodes and d < num_nodes]
    if not filtered:
        return np.zeros((0, 2), dtype=np.int64)
    return np.array(filtered, dtype=np.int64)


def build_edge_features(
    edge_index: np.ndarray,
    x_arr: np.ndarray,
    feature_names: List[str] | None = None,
) -> np.ndarray:
    """Compute edge features from per-node feature differences.

    For each edge (src, dst), computes:
        rssi_diff = |rssi_src - rssi_dst|
        snr_diff = |snr_src - snr_dst|
        loss_sum = loss_src + loss_dst
        latency_diff = |latency_src - latency_dst|
        throughput_sum = throughput_src + throughput_dst

    Args:
        edge_index: (M, 2) array of edge indices.
        x_arr: (N, F) node feature array.
        feature_names: list of feature names matching FEATURE_NAMES order.

    Returns:
        (M, 5) edge feature array.
    """
    names = feature_names or FEATURE_NAMES
    name_to_idx = {n: i for i, n in enumerate(names)}

    def _val(name):
        return name_to_idx.get(name, 0)

    i_rssi = _val("rssi")
    i_snr = _val("snr")
    i_loss = _val("loss_rate")
    i_lat = _val("latency")
    i_thr = _val("throughput")

    M = edge_index.shape[0]
    edge_attr = np.zeros((M, 5), dtype=np.float64)
    for e in range(M):
        s = int(edge_index[e, 0])
        d = int(edge_index[e, 1])
        edge_attr[e, 0] = abs(x_arr[s, i_rssi] - x_arr[d, i_rssi])
        edge_attr[e, 1] = abs(x_arr[s, i_snr] - x_arr[d, i_snr])
        edge_attr[e, 2] = x_arr[s, i_loss] + x_arr[d, i_loss]
        edge_attr[e, 3] = abs(x_arr[s, i_lat] - x_arr[d, i_lat])
        edge_attr[e, 4] = x_arr[s, i_thr] + x_arr[d, i_thr]
    return edge_attr


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

    When model uses edge features (``model._edge_feat_dim > 0``), they are
    automatically computed from node features and the adjacency.

    Args:
        model: MeshGNN instance
        snapshots: list of mesh telemetry snapshots
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

            # Build edge features when model supports them
            edge_idx = None
            edge_attr = None
            if model._edge_feat_dim > 0:
                edge_idx = build_edge_index_array(snap.edge_index, snap.num_nodes)
                if edge_idx.shape[0] > 0:
                    edge_attr = build_edge_features(edge_idx, x_arr)

            opt.zero_grad()
            logits = model.forward(x, adj_norm, edge_idx, edge_attr)
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
    weights: Dict[str, Any] = {
        "conv1.W_self": model.conv1.W_self.data.tolist(),
        "conv1.W_neigh": model.conv1.W_neigh.data.tolist(),
        "conv2.W_self": model.conv2.W_self.data.tolist(),
        "conv2.W_neigh": model.conv2.W_neigh.data.tolist(),
        "output.W": model.output.W.data.tolist(),
        "output.b": model.output.b.data.tolist() if model.output.b is not None else None,
    }
    # Save edge weights when present
    if model.conv1.W_edge is not None:
        weights["conv1.W_edge"] = model.conv1.W_edge.data.tolist()
    if model.conv2.W_edge is not None:
        weights["conv2.W_edge"] = model.conv2.W_edge.data.tolist()

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
    # Load edge weights when present
    if model.conv1.W_edge is not None and "conv1.W_edge" in weights:
        model.conv1.W_edge.data[:] = np.array(weights["conv1.W_edge"])
    if model.conv2.W_edge is not None and "conv2.W_edge" in weights:
        model.conv2.W_edge.data[:] = np.array(weights["conv2.W_edge"])

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
        threshold: score >= threshold → anomaly flagged
        experience_buffer: optional ExperienceReplayBuffer for online fine-tuning
        fine_tune_lr: learning rate for fine-tuning
        fine_tune_lr_decay: multiplicative LR decay per fine-tune step
        fine_tune_steps: number of gradient steps per fine-tune call
    """

    def __init__(
        self,
        model: MeshGNN | None = None,
        threshold: float = 0.5,
        experience_buffer: ExperienceReplayBuffer | None = None,
        fine_tune_lr: float = 0.001,
        fine_tune_lr_decay: float = 0.95,
        fine_tune_steps: int = 5,
    ) -> None:
        self.model = model or MeshGNN()
        self.threshold = threshold
        self._is_trained = False
        self._experience_buffer = experience_buffer
        self._fine_tune_lr = fine_tune_lr
        self._fine_tune_lr_decay = fine_tune_lr_decay
        self._fine_tune_steps = fine_tune_steps

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def push_experience(self, snapshot) -> None:
        """Push a labeled snapshot into the experience replay buffer.

        The snapshot must have .node_features, .edge_index, .labels, .num_nodes.
        """
        if self._experience_buffer is not None:
            self._experience_buffer.push(snapshot)

    def fine_tune(self, *, steps: int | None = None,
                  lr: float | None = None, verbose: bool = False) -> TrainingHistory:
        """Run fine-tuning on the experience replay buffer.

        Returns:
            TrainingHistory with per-step metrics (empty if no buffer).
        """
        if self._experience_buffer is None or self._experience_buffer.is_empty:
            return TrainingHistory()
        return fine_tune_mesh_gnn(
            self.model,
            self._experience_buffer,
            steps=steps or self._fine_tune_steps,
            lr=lr or self._fine_tune_lr,
            lr_decay=self._fine_tune_lr_decay,
            verbose=verbose,
        )

    def experience_stats(self) -> dict:
        """Return statistics about the experience replay buffer."""
        if self._experience_buffer is None:
            return {"size": 0, "anomaly_ratio": 0.0, "capacity": 0}
        return {
            "size": self._experience_buffer.size,
            "anomaly_ratio": self._experience_buffer.anomaly_ratio(),
            "capacity": self._experience_buffer.capacity,
        }

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

        # Build edge features when model supports them
        edge_idx = edge_attr = None
        if self.model._edge_feat_dim > 0:
            edge_idx = build_edge_index_array(edge_index, num_nodes)
            if edge_idx.shape[0] > 0:
                edge_attr = build_edge_features(edge_idx, x_arr)

        probs = self.model.predict(x_arr, adj_norm, edge_idx, edge_attr)
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


# ═══════════════════════════════════════════════════════════════
# Online learning — experience replay buffer + fine-tuning
# ═══════════════════════════════════════════════════════════════

class ExperienceReplayBuffer:
    """Sliding window of labeled mesh snapshots for online learning.

    Maintains class balance via reservoir sampling: when the buffer is full,
    the minority class is kept, and only the majority class is evicted.

    Args:
        capacity: maximum number of snapshots to retain.
        balance_classes: if True, attempt to keep equal normal/anomaly ratio.
    """

    def __init__(self, capacity: int = 100, *, balance_classes: bool = True) -> None:
        self.capacity = capacity
        self.balance_classes = balance_classes
        self._snapshots: list = []

    @property
    def size(self) -> int:
        return len(self._snapshots)

    @property
    def is_empty(self) -> bool:
        return len(self._snapshots) == 0

    def push(self, snapshot) -> None:
        if self.balance_classes:
            self._push_balanced(snapshot)
        else:
            self._push_fifo(snapshot)

    def push_batch(self, snapshots: list) -> None:
        for snap in snapshots:
            self.push(snap)

    def sample(self, n: int | None = None) -> list:
        if n is None:
            return list(self._snapshots)
        return list(self._snapshots[-n:])

    def clear(self) -> None:
        self._snapshots.clear()

    def _push_fifo(self, snapshot) -> None:
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.capacity:
            self._snapshots.pop(0)

    def _push_balanced(self, snapshot) -> None:
        n_anom = sum(1 for l in snapshot.labels if l > 0.5)
        is_anom_snap = n_anom > len(snapshot.labels) / 2

        if len(self._snapshots) < self.capacity:
            self._snapshots.append(snapshot)
            return

        buf_normal = sum(
            1 for s in self._snapshots
            if sum(1 for l in s.labels if l > 0.5) <= len(s.labels) / 2
        )
        buf_anom = self.size - buf_normal

        victim_idx = -1
        for i, s in enumerate(self._snapshots):
            s_is_anom = sum(1 for l in s.labels if l > 0.5) > len(s.labels) / 2
            if is_anom_snap and not s_is_anom and buf_normal > buf_anom:
                victim_idx = i
                break
            if not is_anom_snap and s_is_anom and buf_anom > buf_normal:
                victim_idx = i
                break

        if victim_idx >= 0:
            self._snapshots.pop(victim_idx)
            self._snapshots.append(snapshot)
        else:
            self._push_fifo(snapshot)

    def anomaly_ratio(self) -> float:
        if not self._snapshots:
            return 0.0
        total_anom = sum(
            sum(1 for l in s.labels if l > 0.5)
            for s in self._snapshots
        )
        total_nodes = sum(len(s.labels) for s in self._snapshots)
        return total_anom / max(total_nodes, 1)

    def __repr__(self) -> str:
        return (
            f"ExperienceReplayBuffer(capacity={self.capacity}, "
            f"size={self.size}, anomaly_ratio={self.anomaly_ratio():.2%})"
        )


def fine_tune_mesh_gnn(
    model: MeshGNN,
    buffer: ExperienceReplayBuffer,
    *,
    steps: int = 10,
    lr: float = 0.001,
    lr_decay: float = 0.95,
    verbose: bool = False,
) -> TrainingHistory:
    """Fine-tune a MeshGNN on the experience replay buffer.

    Uses a lower LR than initial training to avoid catastrophic forgetting.
    Each *step* is one gradient update on the entire buffer (a mini-epoch).
    """
    if buffer.is_empty:
        logger.warning("fine_tune_mesh_gnn called with empty buffer -- skipping")
        return TrainingHistory()

    snapshots = buffer.sample()
    opt = Adam(model.parameters(), lr=lr)
    history = TrainingHistory()

    for step in range(steps):
        total_loss = 0.0
        total_accy = 0.0
        n = 0

        for snap in snapshots:
            x_arr = features_to_array(snap.node_features)
            adj_norm = build_adj_norm(snap.edge_index, snap.num_nodes)
            targets = Tensor(np.array(snap.labels, dtype=np.float64).reshape(-1, 1))
            x = Tensor(x_arr, requires_grad=False)

            edge_idx = edge_attr = None
            if model._edge_feat_dim > 0:
                edge_idx = build_edge_index_array(snap.edge_index, snap.num_nodes)
                if edge_idx.shape[0] > 0:
                    edge_attr = build_edge_features(edge_idx, x_arr)

            opt.zero_grad()
            logits = model.forward(x, adj_norm, edge_idx, edge_attr)
            loss = model.bce(logits, targets)
            loss.backward()
            opt.step()

            clipped = np.clip(logits.data, -100.0, 100.0)
            probs = 1.0 / (1.0 + np.exp(-clipped))
            preds = (probs >= 0.5).astype(np.float64)

            total_loss += float(loss.data) * snap.num_nodes
            total_accy += float(np.mean(preds == targets.data)) * snap.num_nodes
            n += snap.num_nodes

        avg_loss = total_loss / n
        avg_accy = total_accy / n
        history.epochs.append(step)
        history.losses.append(avg_loss)
        history.accuracies.append(avg_accy)

        if verbose:
            logger.info(
                f"Fine-tune step {step:3d}/{steps}  loss={avg_loss:.4f}  acc={avg_accy:.1%}")

        opt.lr *= lr_decay

    return history


# ═══════════════════════════════════════════════════════════════
# Edge deployment — model export to C header and binary format
# ═══════════════════════════════════════════════════════════════

def export_to_c_header(
    model: MeshGNN,
    path: str | Path,
    *,
    array_prefix: str = "gnn",
    sigmoid_after_output: bool = True,
) -> None:
    """Export model weights as a C header file for embedded deployment.

    The header defines float arrays for each weight matrix and bias vector,
    plus metadata constants (layer sizes, feature dimensions).

    An embedded C application can include this header and run inference
    using the weights directly.

    Args:
        model: trained MeshGNN
        path: output path (.h recommended)
        array_prefix: C variable name prefix (prevents name collisions)
        sigmoid_after_output: if True, comment documents expected sigmoid
    """
    import textwrap

    def _array(name: str, data: np.ndarray) -> str:
        flat = data.ravel().tolist()
        lines = []
        # Values per line — 6 for readability
        vpl = 6
        for i in range(0, len(flat), vpl):
            chunk = flat[i:i + vpl]
            lines.append("    " + ", ".join(f"{v:.10f}f" for v in chunk))
        body = ",\n".join(lines)
        return (
            f"static const float {array_prefix}_{name}[{data.size}] = {{\n"
            f"{body}\n"
            f"}};"
        )

    def _shape(name: str, data: np.ndarray) -> str:
        return f"static const int {array_prefix}_{name}_shape[{data.ndim}] = {{{', '.join(str(s) for s in data.shape)}}};"

    weights = []

    def _add(key, tens):
        if tens is not None:
            weights.append(_array(key, tens.data))
            weights.append(_shape(key, tens.data))

    _add("conv1_W_self", model.conv1.W_self)
    _add("conv1_W_neigh", model.conv1.W_neigh)
    if model.conv1.W_edge is not None:
        _add("conv1_W_edge", model.conv1.W_edge)
    _add("conv2_W_self", model.conv2.W_self)
    _add("conv2_W_neigh", model.conv2.W_neigh)
    if model.conv2.W_edge is not None:
        _add("conv2_W_edge", model.conv2.W_edge)
    _add("output_W", model.output.W)
    if model.output.b is not None:
        _add("output_b", model.output.b)

    meta = f"""\
static const int {array_prefix}_input_dim = {model.conv1.W_self.data.shape[0]};
static const int {array_prefix}_hidden_dim = {model.conv1.W_self.data.shape[1]};
static const int {array_prefix}_output_dim = 1;
static const int {array_prefix}_edge_feat_dim = {model._edge_feat_dim};
static const int {array_prefix}_num_layers = 2;
"""

    header = f"""\
/*
 * MeshGNN model weights — auto-generated by mesh_gnn.py
 * Architecture: SAGEConv -> ReLU -> SAGEConv -> ReLU -> Linear -> sigmoid
 * Input dim: {model.conv1.W_self.data.shape[0]}
 * Hidden dim: {model.conv1.W_self.data.shape[1]}
 * Edge feat dim: {model._edge_feat_dim}
{" * Output activation: sigmoid" if sigmoid_after_output else ""}
 *
 * Inference steps:
 *   1. h = ReLU(D^{-1}A @ x @ W_neigh1 + x @ W_self1 + edge_agg @ W_edge1)
 *   2. h = ReLU(D^{-1}A @ h @ W_neigh2 + h @ W_self2 + edge_agg @ W_edge2)
 *   3. logit = h @ W_out + b_out
 *   4. prob = 1 / (1 + exp(-logit))
 */

#ifndef {array_prefix.upper()}_MODEL_H
#define {array_prefix.upper()}_MODEL_H

#ifdef __cplusplus
extern "C" {{
#endif

{meta}
{chr(10).join(weights)}

#ifdef __cplusplus
}}
#endif

#endif /* {array_prefix.upper()}_MODEL_H */
"""
    with open(path, "w") as f:
        f.write(header)
    logger.info(f"C header exported to {path} ({len(weights)} arrays)")


def export_to_binary(model: MeshGNN, path: str | Path) -> None:
    """Export model weights as a compact binary file.

    Format (little-endian):
      [4 bytes]  magic: 0x474E4E58 ("GNNX")
      [4 bytes]  version: 1
      [4 bytes]  input_dim
      [4 bytes]  hidden_dim
      [4 bytes]  edge_feat_dim
      [4 bytes]  num_arrays (N)

      For each array:
        [4 bytes]  name_len
        [name_len bytes]  array name (e.g. "conv1.W_self")
        [4 bytes]  ndim
        [4 bytes * ndim]  shape
        [8 bytes * size]  float64 data

    Loadable on any platform — no Python required.
    """
    import struct

    arrays: List[tuple[str, np.ndarray]] = []

    def _add(name: str, tens):
        if tens is not None:
            arrays.append((name, tens.data))

    _add("conv1.W_self", model.conv1.W_self)
    _add("conv1.W_neigh", model.conv1.W_neigh)
    _add("conv1.W_edge", model.conv1.W_edge)
    _add("conv2.W_self", model.conv2.W_self)
    _add("conv2.W_neigh", model.conv2.W_neigh)
    _add("conv2.W_edge", model.conv2.W_edge)
    _add("output.W", model.output.W)
    _add("output.b", model.output.b)

    with open(path, "wb") as f:
        # Header
        f.write(struct.pack("<4sIIIII",
                           b"GNNX", 1,
                           model.conv1.W_self.data.shape[0],
                           model.conv1.W_self.data.shape[1],
                           model._edge_feat_dim,
                           len(arrays)))
        # Arrays with name labels
        for name, arr in arrays:
            name_bytes = name.encode("utf-8")
            f.write(struct.pack("<I", len(name_bytes)))
            f.write(name_bytes)
            f.write(struct.pack("<I", arr.ndim))
            for d in arr.shape:
                f.write(struct.pack("<I", d))
            f.write(arr.astype(np.float64).tobytes())

    size_kb = Path(path).stat().st_size / 1024
    logger.info(f"Binary model exported to {path} ({size_kb:.1f} KB, {len(arrays)} arrays)")


def load_from_binary(path: str | Path) -> dict:
    """Load model weights from binary format.

    Returns:
        dict of {"conv1.W_self": ndarray, ...} indexed by name.
    """
    import struct

    with open(path, "rb") as f:
        magic, version, input_dim, hidden_dim, edge_feat_dim, num_arrays = (
            struct.unpack("<4sIIIII", f.read(4 * 6)))
        assert magic == b"GNNX", f"Bad magic: {magic}"
        assert version == 1, f"Unsupported version: {version}"

        result = {}
        for _ in range(num_arrays):
            name_len = struct.unpack("<I", f.read(4))[0]
            name = f.read(name_len).decode("utf-8")
            ndim = struct.unpack("<I", f.read(4))[0]
            shape = struct.unpack(f"<{'I' * ndim}", f.read(4 * ndim))
            data = np.frombuffer(f.read(8 * np.prod(shape).item()),
                                 dtype=np.float64).reshape(shape)
            result[name] = data

    result["_meta"] = {
        "input_dim": input_dim,
        "hidden_dim": hidden_dim,
        "edge_feat_dim": edge_feat_dim,
    }
    return result


class EdgeInferenceEngine:
    """Lightweight inference engine for MeshGNN on edge devices.

    Loads only the weights (not the full training graph) and runs inference
    using pure NumPy matrix operations. No training dependencies needed.

    Args:
        weight_path: path to binary model file (.gnnx)
    """

    def __init__(self, weight_path: str | Path) -> None:
        self.weights = load_from_binary(weight_path)
        meta = self.weights["_meta"]
        self.input_dim = meta["input_dim"]
        self.hidden_dim = meta["hidden_dim"]
        self.edge_feat_dim = meta["edge_feat_dim"]
        self._has_edge = self.edge_feat_dim > 0 and "conv1.W_edge" in self.weights

    def predict(
        self,
        x: np.ndarray,
        adj_norm: np.ndarray,
        edge_index: np.ndarray | None = None,
        edge_attr: np.ndarray | None = None,
    ) -> np.ndarray:
        """Forward pass without autograd tracking (pure NumPy).

        Same interface as MeshGNN.predict() but without any Tensor objects.

        Args:
            x: (N, input_dim) node features
            adj_norm: (N, N) normalised adjacency
            edge_index: (M, 2) edge indices (required if model has edge features)
            edge_attr: (M, F) edge features (required if model has edge features)

        Returns:
            (N, 1) sigmoid probabilities
        """
        W = self.weights

        # Conv1
        h = x @ W["conv1.W_self"] + adj_norm @ x @ W["conv1.W_neigh"]
        if self._has_edge and edge_index is not None and edge_attr is not None:
            from src.ml.micro_tensor import _aggregate_edge_features
            edge_agg = _aggregate_edge_features(edge_index, edge_attr, x.shape[0])
            h += edge_agg @ W["conv1.W_edge"]
        h = np.maximum(0, h)

        # Conv2
        h = h @ W["conv2.W_self"] + adj_norm @ h @ W["conv2.W_neigh"]
        if self._has_edge:
            edge_agg2 = _aggregate_edge_features(edge_index, edge_attr, x.shape[0])
            h += edge_agg2 @ W["conv2.W_edge"]
        h = np.maximum(0, h)

        # Output
        logits = h @ W["output.W"]
        if "output.b" in W:
            logits += W["output.b"]

        # Sigmoid
        clipped = np.clip(logits, -100.0, 100.0)
        return 1.0 / (1.0 + np.exp(-clipped))

    def predict_topology(
        self,
        node_features: List[Dict[str, float]],
        edge_index_list: List[Tuple[int, int]],
    ) -> List[AnomalyPrediction]:
        """Full topology prediction — same interface as MeshGNNDetector."""
        from src.ml.mesh_gnn import (
            features_to_array, build_adj_norm, build_edge_index_array,
            build_edge_features,
        )

        num_nodes = len(node_features)
        x_arr = features_to_array(node_features)
        adj_norm = build_adj_norm(edge_index_list, num_nodes)

        edge_idx = edge_attr = None
        if self._has_edge:
            edge_idx = build_edge_index_array(edge_index_list, num_nodes)
            if edge_idx.shape[0] > 0:
                edge_attr = build_edge_features(edge_idx, x_arr)

        probs = self.predict(x_arr, adj_norm, edge_idx, edge_attr)

        predictions = []
        for i in range(num_nodes):
            score = float(probs[i, 0])
            confidence = abs(score - 0.5) * 2.0
            predictions.append(AnomalyPrediction(
                is_anomaly=score >= 0.5,
                anomaly_score=round(score, 4),
                confidence=round(min(1.0, confidence), 4),
                node_id=str(i),
                features=node_features[i] if isinstance(node_features[i], dict) else {},
                inference_time_ms=0.0,
            ))
        return predictions
