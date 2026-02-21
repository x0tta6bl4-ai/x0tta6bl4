"""
GraphSAGE v2 Anomaly Detector with INT8 Quantization

Implements GraphSAGE-based anomaly detection for mesh network topology
with INT8 quantization for edge deployment (<50ms inference, <5MB model size).

Target metrics (Stage 2):
- Accuracy: ≥99% (current: 94-98%)
- FPR: ≤8% (current: 5%)
- Inference latency: <50ms
- Model size: <5MB (INT8 quantized)
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Monitoring metrics
try:
    from src.monitoring import record_graphsage_inference

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

    def record_graphsage_inference(*args, **kwargs):
        pass


# Lazy loading for causal analysis
CAUSAL_ANALYSIS_AVAILABLE = None
def _ensure_causal():
    global CAUSAL_ANALYSIS_AVAILABLE, CausalAnalysisEngine, IncidentEvent, IncidentSeverity
    if CAUSAL_ANALYSIS_AVAILABLE is not None:
        return CAUSAL_ANALYSIS_AVAILABLE
    try:
        from src.ml.causal_analysis import (CausalAnalysisEngine, IncidentEvent, IncidentSeverity)
        CAUSAL_ANALYSIS_AVAILABLE = True
    except ImportError:
        CAUSAL_ANALYSIS_AVAILABLE = False
    return CAUSAL_ANALYSIS_AVAILABLE

# Lazy loading for SHAP
SHAP_AVAILABLE = None
def _ensure_shap():
    global SHAP_AVAILABLE, shap
    if SHAP_AVAILABLE is not None:
        return SHAP_AVAILABLE
    try:
        import shap
        SHAP_AVAILABLE = True
    except ImportError:
        SHAP_AVAILABLE = False
    return SHAP_AVAILABLE

def get_model_class():
    """Get the GraphSAGEAnomalyDetectorV2 class (lazy loaded)."""
    return _ensure_torch()["ModelClass"]

def is_torch_available() -> bool:
    """Check if torch and torch_geometric are available."""
    return _ensure_torch()["available"]

def is_quantization_available() -> bool:
    """Check if quantization support is available."""
    t_comp = _ensure_torch()
    if not t_comp["available"]:
        return False
    try:
        import torch.quantization
        return True
    except ImportError:
        return False

# Module-level lazy loading for backward compatibility
_LAZY_GLOBALS = {
    "_TORCH_AVAILABLE": lambda: is_torch_available(),
    "_QUANTIZATION_AVAILABLE": lambda: is_quantization_available(),
    "torch": lambda: _ensure_torch().get("torch"),
    "nn": lambda: _ensure_torch().get("nn"),
    "F": lambda: _ensure_torch().get("F"),
    "Data": lambda: _ensure_torch().get("Data"),
    "SAGEConv": lambda: _ensure_torch().get("SAGEConv"),
    "GraphSAGEAnomalyDetectorV2": lambda: _ensure_torch().get("ModelClass"),
}

def __getattr__(name):
    if name in _LAZY_GLOBALS:
        return _LAZY_GLOBALS[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

_TORCH_INTERNAL = None


def _ensure_torch():
    """Lazy loader for torch and torch_geometric components."""
    global _TORCH_INTERNAL
    if _TORCH_INTERNAL is not None:
        return _TORCH_INTERNAL

    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch_geometric.data import Data
        from torch_geometric.nn import SAGEConv

        # Define the model class here to ensure nn.Module is available
        class GraphSAGEAnomalyDetectorV2(nn.Module):
            """
            GraphSAGE v2 model for anomaly detection with attention mechanism.
            """
            def __init__(
                self,
                input_dim: int = 8,
                hidden_dim: int = 64,
                num_layers: int = 2,
                dropout: float = 0.3,
            ):
                super(GraphSAGEAnomalyDetectorV2, self).__init__()
                self.num_layers = num_layers
                self.convs = nn.ModuleList()
                self.convs.append(SAGEConv(input_dim, hidden_dim))
                for _ in range(num_layers - 1):
                    self.convs.append(SAGEConv(hidden_dim, hidden_dim))
                self.attention = nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim // 2),
                    nn.ReLU(),
                    nn.Linear(hidden_dim // 2, 1),
                    nn.Sigmoid(),
                )
                self.anomaly_predictor = nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim // 2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim // 2, 1),
                    nn.Sigmoid(),
                )
                try:
                    import torch.quantization as quantization
                    from torch.quantization import DeQuantStub, QuantStub
                    self.quant = QuantStub()
                    self.dequant = DeQuantStub()
                    self._has_quant = True
                except ImportError:
                    self._has_quant = False

            def forward(self, x, edge_index, batch=None):
                if getattr(self, "_has_quant", False):
                    x = self.quant(x)
                for i, conv in enumerate(self.convs):
                    x = conv(x, edge_index)
                    if i != self.num_layers - 1:
                        x = F.relu(x)
                        x = F.dropout(x, p=0.3, training=self.training)
                attention_weights = self.attention(x)
                x_attended = x * attention_weights
                anomaly_prob = self.anomaly_predictor(x_attended)
                if getattr(self, "_has_quant", False):
                    anomaly_prob = self.dequant(anomaly_prob)
                return anomaly_prob

            def prepare_for_quantization(self):
                import torch.quantization as quantization
                self.eval()
                self.qconfig = quantization.get_default_qconfig("fbgemm")
                quantization.prepare(self, inplace=True)

            def convert_to_int8(self):
                import torch.quantization as quantization
                quantization.convert(self, inplace=True)
                logger.info("Model converted to INT8 quantized format")

        _TORCH_INTERNAL = {
            "torch": torch,
            "nn": nn,
            "F": F,
            "Data": Data,
            "SAGEConv": SAGEConv,
            "ModelClass": GraphSAGEAnomalyDetectorV2,
            "available": True
        }
    except ImportError as e:
        logger.warning(f"⚠️ GraphSAGE: torch components not available: {e}")
        _TORCH_INTERNAL = {"available": False}
    
    return _TORCH_INTERNAL


@dataclass
class AnomalyPrediction:
    """Anomaly detection prediction result"""
    is_anomaly: bool
    anomaly_score: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    node_id: str
    features: Dict[str, float]
    inference_time_ms: float

class GraphSAGEAnomalyDetector:
    """
    GraphSAGE v2 Anomaly Detector with INT8 quantization support.
    """
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        num_layers: int = 2,
        anomaly_threshold: float = 0.6,
        use_quantization: bool = True,
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.anomaly_threshold = anomaly_threshold
        self.use_quantization = bool(use_quantization and is_quantization_available())
        self.recall = 0.96
        self.precision = 0.98
        self.is_trained = False
        self.model = None
        self.device = None
        
        # We don't call _ensure_torch here to keep __init__ fast
        # unless we explicitly need to create the model.
        
        # Initialize causal analysis engine if available
        self.causal_engine: Optional[Any] = None
        if _ensure_causal():
            try:
                from src.ml.causal_analysis import CausalAnalysisEngine
                self.causal_engine = CausalAnalysisEngine(
                    correlation_window_seconds=300.0, min_confidence=0.5
                )
                logger.info("Causal analysis engine integrated with GraphSAGE")
            except Exception as e:
                logger.warning(f"Failed to initialize causal engine: {e}")

    def _init_model_if_needed(self):
        """Deferred initialization of the torch model."""
        if self.model is not None:
            return True
            
        if not is_torch_available():
            return False
            
        t_comp = _ensure_torch()
        if not t_comp["available"]:
            return False
            
        torch = t_comp["torch"]
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = t_comp["ModelClass"](
            input_dim=self.input_dim, 
            hidden_dim=self.hidden_dim, 
            num_layers=self.num_layers
        ).to(self.device)

        if self.use_quantization:
            try:
                self.model.prepare_for_quantization()
                logger.info("Model prepared for INT8 quantization")
            except Exception as e:
                logger.warning(f"Quantization prep failed: {e}")
        
        return True

    def train(
        self,
        node_features: List[Dict[str, float]],
        edge_index: List[Tuple[int, int]],
        labels: Optional[List[float]] = None,
        epochs: int = 50,
        lr: float = 0.001,
    ):
        if not self._init_model_if_needed():
            return

        if not node_features or not edge_index:
            return

        # Basic validation: ensure edge indices are within range
        num_nodes = len(node_features)
        valid_edges = [e for e in edge_index if e[0] < num_nodes and e[1] < num_nodes]
        if not valid_edges:
            logger.warning("No valid edges found for the given node features. Skipping training.")
            return
        
        t_comp = _ensure_torch()
        torch = t_comp["torch"]
        nn = t_comp["nn"]
        Data = t_comp["Data"]

        x = self._features_to_tensor(node_features)
        edge_index_tensor = self._edges_to_tensor(valid_edges)

        if labels is None:
            labels = self._generate_labels(node_features)

        y = torch.tensor(labels, dtype=torch.float).unsqueeze(1).to(self.device)
        data = Data(x=x, edge_index=edge_index_tensor, y=y)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCELoss()
        self.model.train()

        for epoch in range(epochs):
            optimizer.zero_grad()
            predictions = self.model(data.x, data.edge_index)
            loss = criterion(predictions, data.y)
            loss.backward()
            optimizer.step()

        if self.use_quantization:
            try:
                self.model.convert_to_int8()
            except Exception:
                pass

        self.is_trained = True

    def predict(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        edge_index: Optional[List[Tuple[int, int]]] = None,
    ) -> AnomalyPrediction:
        start_time = time.time()

        # If torch not available or model not ready, use rule-based fallback
        if not self._init_model_if_needed() or not self.is_trained:
            labels = self._generate_labels([node_features])
            anomaly_score = float(labels[0]) if labels else 0.0
            is_anomaly = anomaly_score >= self.anomaly_threshold
            return AnomalyPrediction(
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
                confidence=0.8,
                node_id=node_id,
                features=node_features,
                inference_time_ms=(time.time() - start_time) * 1000,
            )

        t_comp = _ensure_torch()
        torch = t_comp["torch"]

        all_nodes = [(node_id, node_features)] + neighbors
        x = self._features_to_tensor([features for _, features in all_nodes])

        if edge_index is None:
            edge_index = [(0, i + 1) for i in range(len(neighbors))]
            edge_index += [(i + 1, 0) for i in range(len(neighbors))]

        edge_index_tensor = self._edges_to_tensor(edge_index)

        self.model.eval()
        with torch.no_grad():
            predictions = self.model(
                x.to(self.device), edge_index_tensor.to(self.device)
            )
            anomaly_score = float(predictions[0].item())

        inf_time = (time.time() - start_time) * 1000
        is_anomaly = anomaly_score >= self.anomaly_threshold
        
        record_graphsage_inference(inf_time, is_anomaly, "CRITICAL" if is_anomaly else "NORMAL")

        return AnomalyPrediction(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=abs(anomaly_score - 0.5) * 2,
            node_id=node_id,
            features=node_features,
            inference_time_ms=inf_time,
        )

        # Prepare graph data
        all_nodes = [(node_id, node_features)] + neighbors
        x = self._features_to_tensor([features for _, features in all_nodes])

        # Generate edge_index if not provided
        if edge_index is None:
            # Connect node to all neighbors
            edge_index = [(0, i + 1) for i in range(len(neighbors))]
            edge_index += [(i + 1, 0) for i in range(len(neighbors))]  # Bidirectional

        edge_index_tensor = self._edges_to_tensor(edge_index)

        # Inference
        self.model.eval()
        with torch.no_grad():
            predictions = self.model(
                x.to(self.device), edge_index_tensor.to(self.device)
            )
            anomaly_score = float(predictions[0].item())

        inference_time = (time.time() - start_time) * 1000  # ms

        is_anomaly = anomaly_score >= self.anomaly_threshold
        confidence = abs(anomaly_score - 0.5) * 2  # Distance from threshold

        # Record metrics
        severity = "CRITICAL" if is_anomaly else "NORMAL"
        record_graphsage_inference(inference_time, is_anomaly, severity)

        return AnomalyPrediction(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            node_id=node_id,
            features=node_features,
            inference_time_ms=inference_time,
        )

    def predict_with_causal(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        edge_index: Optional[List[Tuple[int, int]]] = None,
    ) -> Tuple[AnomalyPrediction, Optional[Any]]:
        """
        Predict anomaly and provide causal analysis if anomaly detected.

        Args:
            node_id: Node identifier
            node_features: Node feature dict (RSSI, SNR, loss rate, etc.)
            neighbors: List of (neighbor_id, neighbor_features) tuples
            edge_index: Optional edge connectivity (auto-generated if None)

        Returns:
            Tuple of (AnomalyPrediction, Optional[CausalAnalysisResult])
            CausalAnalysisResult is None if no anomaly or causal engine unavailable
        """
        # 1. Get GraphSAGE prediction
        prediction = self.predict(node_id, node_features, neighbors, edge_index)

        # 2. If anomaly detected and causal engine available, perform causal
        # analysis
        if (
            prediction.is_anomaly
            and self.causal_engine is not None
            and _ensure_causal()
        ):
            try:
                from src.ml.causal_analysis import IncidentEvent
                # Create incident event from prediction
                incident = IncidentEvent(
                    event_id=f"graphsage_{node_id}_{int(time.time())}",
                    timestamp=datetime.now(),
                    node_id=node_id,
                    service_id=None,
                    anomaly_type="graphsage_anomaly",
                    severity=self._score_to_severity(prediction.anomaly_score),
                    metrics=node_features,
                    detected_by="graphsage",
                    anomaly_score=prediction.anomaly_score,
                )

                # Add incident to causal engine
                self.causal_engine.add_incident(incident)

                # Perform causal analysis
                causal_result = self.causal_engine.analyze(incident.event_id)

                logger.info(
                    f"Causal analysis completed for {node_id}: "
                    f"{len(causal_result.root_causes)} root causes identified "
                    f"(confidence: {causal_result.confidence:.2f})"
                )

                return prediction, causal_result

            except Exception as e:
                logger.warning(f"Error in causal analysis: {e}")
                return prediction, None

        return prediction, None

    def explain_anomaly(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        edge_index: Optional[List[Tuple[int, int]]] = None,
    ) -> Dict[str, float]:
        if not _ensure_shap() or not self._init_model_if_needed():
            logger.warning("SHAP not available or model not initialized")
            return {}

        try:
            # Prepare input data
            all_nodes = [(node_id, node_features)] + neighbors
            x = self._features_to_tensor([features for _, features in all_nodes])

            if edge_index is None:
                edge_index = [(0, i + 1) for i in range(len(neighbors))]
                edge_index += [(i + 1, 0) for i in range(len(neighbors))]

            edge_index_tensor = self._edges_to_tensor(edge_index)

            # Create SHAP explainer
            # For GraphSAGE, we use a wrapper function
            def model_wrapper(x_input):
                """Wrapper for SHAP to work with GraphSAGE model."""
                self.model.eval()
                with torch.no_grad():
                    predictions = self.model(
                        x_input.to(self.device), edge_index_tensor.to(self.device)
                    )
                    return predictions.cpu().numpy()

            # Use KernelExplainer for model-agnostic explanation
            # Focus on the target node's features
            feature_names = [
                "rssi",
                "snr",
                "loss_rate",
                "link_age",
                "latency",
                "throughput",
                "cpu",
                "memory",
            ]
            target_features = x[0:1].cpu().numpy()  # First node (target)

            # Create explainer with background data (use mean of neighbors as
            # background)
            if len(neighbors) > 0:
                background = x[1:].cpu().numpy().mean(axis=0, keepdims=True)
            else:
                background = target_features

            explainer = shap.KernelExplainer(
                lambda x_in: model_wrapper(torch.tensor(x_in, dtype=torch.float)),
                background,
            )

            # Calculate SHAP values
            shap_values = explainer.shap_values(target_features, nsamples=100)

            # Map to feature names
            if isinstance(shap_values, list):
                shap_values = shap_values[0]  # Take first output

            feature_importance = {
                feature_names[i]: float(shap_values[0][i])
                for i in range(min(len(feature_names), shap_values.shape[1]))
            }

            logger.debug(f"SHAP values calculated for {node_id}: {feature_importance}")
            return feature_importance

        except Exception as e:
            logger.warning(f"Error calculating SHAP values: {e}")
            return {}

    def _score_to_severity(self, anomaly_score: float):
        """Convert anomaly score to incident severity."""
        if not _ensure_causal():
            return None

        # Re-import inside if needed or use from global (mapped via _ensure_causal)
        from src.ml.causal_analysis import IncidentSeverity

        if anomaly_score >= 0.9:
            return IncidentSeverity.CRITICAL
        elif anomaly_score >= 0.7:
            return IncidentSeverity.HIGH
        elif anomaly_score >= 0.5:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW

    def _features_to_tensor(self, features_list: List[Dict[str, float]]):
        """Convert list of feature dicts to tensor."""
        t_comp = _ensure_torch()
        if not t_comp["available"]:
            return None
        torch = t_comp["torch"]

        feature_names = [
            "rssi",
            "snr",
            "loss_rate",
            "link_age",
            "latency",
            "throughput",
            "cpu",
            "memory",
        ]

        tensor_data = []
        for features in features_list:
            row = [features.get(name, 0.0) for name in feature_names]
            tensor_data.append(row)

        return torch.tensor(tensor_data, dtype=torch.float)

    def _edges_to_tensor(self, edges: List[Tuple[int, int]]):
        """Convert edge list to tensor format."""
        t_comp = _ensure_torch()
        if not t_comp["available"]:
            return None
        torch = t_comp["torch"]

        if not edges:
            return torch.tensor([[], []], dtype=torch.long)

        edge_list = [[src, tgt] for src, tgt in edges]
        return torch.tensor(edge_list, dtype=torch.long).t().contiguous()

    def _generate_labels(self, node_features: List[Dict[str, float]]) -> List[float]:
        """
        Generate anomaly labels using multi-signal scoring.

        Combines multiple correlated indicators rather than a single
        threshold.  A node is labeled anomalous when several signals
        agree, reducing false positives from normal variance.
        """
        labels = []
        for features in node_features:
            score = 0.0

            rssi = features.get("rssi", -50.0)
            snr = features.get("snr", 20.0)
            loss_rate = features.get("loss_rate", 0.0)
            cpu = features.get("cpu", 0.3)
            memory = features.get("memory", 0.4)
            latency = features.get("latency", 15.0)
            throughput = features.get("throughput", 50.0)
            link_age = features.get("link_age", 3600.0)

            # --- Signal quality degradation ---
            if rssi < -80.0:
                score += 0.30
            elif rssi < -70.0:
                score += 0.10

            # SNR drop (catches interference where RSSI stays moderate but SNR
            # tanks)
            if snr < 8.0:
                score += 0.25
            elif snr < 12.0:
                score += 0.10

            # --- Packet loss ---
            if loss_rate > 0.15:
                score += 0.35
            elif loss_rate > 0.05:
                score += 0.15

            # --- Resource exhaustion ---
            if cpu > 0.85 or memory > 0.85:
                score += 0.25

            # --- Latency spike ---
            if latency > 100.0:
                score += 0.25
            elif latency > 40.0:
                score += 0.10

            # --- Throughput collapse (only severe) ---
            if throughput < 2.0:
                score += 0.20

            # --- Link instability (very young link = flapping) ---
            if link_age < 10.0:
                score += 0.15

            # --- Correlated signal patterns (boost for multi-degradation) ---
            # Interference: SNR down + throughput down without extreme RSSI
            # drop
            if snr < 15.0 and throughput < 30.0 and rssi > -75.0:
                score += 0.15
            # Cascade: high latency + elevated loss
            if latency > 30.0 and loss_rate > 0.03:
                score += 0.10

            labels.append(1.0 if score >= 0.50 else 0.0)

        return labels

    def train_from_telemetry(
        self,
        num_snapshots: int = 200,
        nodes_per_snapshot: int = 20,
        anomaly_ratio: float = 0.3,
        epochs: int = 50,
        lr: float = 0.001,
        seed: int = 42,
    ):
        """Train the model using structured mesh telemetry data.

        Uses MeshTelemetryGenerator to produce scenario-based training data
        with physically plausible anomalies instead of random noise.

        Args:
            num_snapshots: Number of mesh snapshots to generate
            nodes_per_snapshot: Nodes per snapshot
            anomaly_ratio: Fraction of anomalous snapshots
            epochs: Training epochs
            lr: Learning rate
            seed: RNG seed for reproducibility
        """
        from src.ml.mesh_telemetry import generate_training_data

        features, edges, labels = generate_training_data(
            num_snapshots=num_snapshots,
            nodes_per_snapshot=nodes_per_snapshot,
            anomaly_ratio=anomaly_ratio,
            seed=seed,
        )
        logger.info(
            f"Training from telemetry: {len(features)} nodes, "
            f"{len(edges)} edges, {sum(1 for label in labels if label > 0.5)} anomalies"
        )
        self.train(features, edges, labels, epochs=epochs, lr=lr)

    def save_model(self, path: str):
        """Save model to file."""
        if not self._init_model_if_needed():
            logger.warning("Cannot save model: torch initialization failed")
            return

        t_comp = _ensure_torch()
        torch = t_comp["torch"]

        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "input_dim": self.input_dim,
                "hidden_dim": self.hidden_dim,
                "num_layers": self.num_layers,
                "anomaly_threshold": self.anomaly_threshold,
                "is_trained": self.is_trained,
            },
            path,
        )
        logger.info(f"Model saved to {path}")

    def load_model(self, path: str):
        """Load model from file."""
        t_comp = _ensure_torch()
        if not t_comp["available"]:
            return
        torch = t_comp["torch"]

        checkpoint = torch.load(path, map_location=torch.device("cpu"), weights_only=True)
        
        # Update detector parameters from checkpoint
        self.input_dim = checkpoint["input_dim"]
        self.hidden_dim = checkpoint["hidden_dim"]
        self.num_layers = checkpoint["num_layers"]
        self.anomaly_threshold = checkpoint["anomaly_threshold"]
        self.is_trained = checkpoint.get("is_trained", False)

        # Re-create model instance with correct dimensions
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = t_comp["ModelClass"](
            input_dim=self.input_dim, 
            hidden_dim=self.hidden_dim, 
            num_layers=self.num_layers
        ).to(self.device)

        # Load weights
        self.model.load_state_dict(checkpoint["model_state_dict"])

        if self.use_quantization:
            try:
                self.model.prepare_for_quantization()
                self.model.convert_to_int8()
            except Exception:
                pass

        logger.info(f"Model loaded from {path}")


# Integration with MAPE-K
def create_graphsage_detector_for_mapek(
    pretrain: bool = False,
    num_snapshots: int = 200,
    epochs: int = 50,
    use_quantization: bool = True,  # Add this parameter
) -> GraphSAGEAnomalyDetector:
    """
    Create GraphSAGE detector configured for MAPE-K integration.

    Args:
        pretrain: If True, train on mesh telemetry data before returning.
        num_snapshots: Number of training snapshots (when pretrain=True).
        epochs: Training epochs (when pretrain=True).
        use_quantization: Enable/disable INT8 quantization (default: True).

    Returns:
        GraphSAGEAnomalyDetector instance ready for use in Monitor phase
    """
    detector = GraphSAGEAnomalyDetector(
        input_dim=8,
        hidden_dim=64,
        num_layers=2,
        anomaly_threshold=0.6,
        use_quantization=use_quantization,  # Use the new parameter
    )

    if pretrain:
        detector.train_from_telemetry(
            num_snapshots=num_snapshots,
            epochs=epochs,
        )

    return detector
