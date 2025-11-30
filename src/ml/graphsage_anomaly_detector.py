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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Optional PyTorch imports for GNN
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv
    from torch_geometric.data import Data
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning("PyTorch/Geometric not available, using fallback mode")
    
    # Mock torch for type hints
    class MockTorch:
        Tensor = Any
        long = Any
        float = Any
        device = Any
        def tensor(self, *args, **kwargs): return None
        def load(self, *args, **kwargs): return None
        def save(self, *args, **kwargs): return None
        class optim:
            Adam = Any
    
    torch = MockTorch()


# Optional quantization imports
try:
    import torch.quantization as quantization
    from torch.quantization import QuantStub, DeQuantStub
    _QUANTIZATION_AVAILABLE = _TORCH_AVAILABLE
except ImportError:
    _QUANTIZATION_AVAILABLE = False


@dataclass
class AnomalyPrediction:
    """Anomaly detection prediction result"""
    is_anomaly: bool
    anomaly_score: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    node_id: str
    features: Dict[str, float]
    inference_time_ms: float


if _TORCH_AVAILABLE:
    class GraphSAGEAnomalyDetectorV2(nn.Module):
        """
        GraphSAGE v2 model for anomaly detection with attention mechanism.
        
        Architecture:
        - Input: 8D node features (RSSI, SNR, loss rate, link age, etc.)
        - Hidden: 64-dim (lightweight for edge deployment)
        - Layers: 2 (vs typical 3-4 for efficiency)
        - Output: Anomaly probability [0, 1]
        - Params: ~15K (fits in RPi RAM)
        """
        
        def __init__(
            self,
            input_dim: int = 8,
            hidden_dim: int = 64,
            num_layers: int = 2,
            dropout: float = 0.3
        ):
            super(GraphSAGEAnomalyDetectorV2, self).__init__()
            
            self.num_layers = num_layers
            self.convs = nn.ModuleList()
            
            # First layer
            self.convs.append(SAGEConv(input_dim, hidden_dim))
            
            # Hidden layers
            for _ in range(num_layers - 1):
                self.convs.append(SAGEConv(hidden_dim, hidden_dim))
            
            # Attention mechanism for better accuracy
            self.attention = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, 1),
                nn.Sigmoid()
            )
            
            # Output: anomaly probability
            self.anomaly_predictor = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
                nn.Sigmoid()
            )
            
            # Quantization stubs for INT8
            self.quant = QuantStub()
            self.dequant = DeQuantStub()
        
        def forward(self, x, edge_index, batch=None):
            """
            Forward pass with attention mechanism.
            
            Args:
                x: Node features (N, input_dim)
                edge_index: Graph connectivity (2, E)
                batch: Batch vector (optional)
            
            Returns:
                anomaly_prob: Anomaly probability per node (N, 1)
            """
            # Quantize input
            x = self.quant(x)
            
            # GraphSAGE layers
            for i, conv in enumerate(self.convs):
                x = conv(x, edge_index)
                if i != self.num_layers - 1:
                    x = F.relu(x)
                    x = F.dropout(x, p=0.3, training=self.training)
            
            # Attention mechanism
            attention_weights = self.attention(x)
            x_attended = x * attention_weights
            
            # Anomaly prediction
            anomaly_prob = self.anomaly_predictor(x_attended)
            
            # Dequantize output
            anomaly_prob = self.dequant(anomaly_prob)
            
            return anomaly_prob
        
        def prepare_for_quantization(self):
            """Prepare model for INT8 quantization."""
            self.eval()
            # Set quantization config
            self.qconfig = quantization.get_default_qconfig('fbgemm')
            quantization.prepare(self, inplace=True)
        
        def convert_to_int8(self):
            """Convert model to INT8 quantized format."""
            quantization.convert(self, inplace=True)
            logger.info("Model converted to INT8 quantized format")
else:
    class GraphSAGEAnomalyDetectorV2:
        """Dummy class when PyTorch is not available"""
        pass


class GraphSAGEAnomalyDetector:
    """
    GraphSAGE v2 Anomaly Detector with INT8 quantization support.
    
    Detects anomalies in mesh network topology using GraphSAGE
    with attention mechanism and INT8 quantization for edge deployment.
    """
    
    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        num_layers: int = 2,
        anomaly_threshold: float = 0.6,
        use_quantization: bool = True
    ):
        """
        Initialize GraphSAGE anomaly detector.
        
        Args:
            input_dim: Input feature dimension (default: 8)
            hidden_dim: Hidden layer dimension (default: 64)
            num_layers: Number of GraphSAGE layers (default: 2)
            anomaly_threshold: Threshold for anomaly detection (default: 0.6)
            use_quantization: Enable INT8 quantization (default: True)
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.anomaly_threshold = anomaly_threshold
        self.use_quantization = use_quantization and _QUANTIZATION_AVAILABLE
        
        if not _TORCH_AVAILABLE:
            logger.warning("PyTorch not available, using fallback detector")
            self.model = None
            self.device = None
            return
        
        # Initialize model
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = GraphSAGEAnomalyDetectorV2(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers
        ).to(self.device)
        
        # Prepare for quantization if enabled
        if self.use_quantization:
            self.model.prepare_for_quantization()
            logger.info("Model prepared for INT8 quantization")
        
        self.is_trained = False
        logger.info(f"GraphSAGE v2 detector initialized on {self.device}")
    
    def train(
        self,
        node_features: List[Dict[str, float]],
        edge_index: List[Tuple[int, int]],
        labels: Optional[List[float]] = None,
        epochs: int = 50,
        lr: float = 0.001
    ):
        """
        Train GraphSAGE model on mesh topology data.
        
        Args:
            node_features: List of node feature dicts
            edge_index: List of (source, target) edge tuples
            labels: Optional anomaly labels (1.0 = anomaly, 0.0 = normal)
            epochs: Training epochs
            lr: Learning rate
        """
        if not _TORCH_AVAILABLE or self.model is None:
            logger.warning("Training skipped: PyTorch not available")
            return
        
        if not node_features or not edge_index:
            logger.warning("Training skipped: insufficient data")
            return
        
        logger.info(f"Training GraphSAGE v2 model: {len(node_features)} nodes, {len(edge_index)} edges")
        
        # Convert to PyTorch format
        x = self._features_to_tensor(node_features)
        edge_index_tensor = self._edges_to_tensor(edge_index)
        
        # Generate labels if not provided (use simple heuristic)
        if labels is None:
            labels = self._generate_labels(node_features)
        
        y = torch.tensor(labels, dtype=torch.float).unsqueeze(1).to(self.device)
        
        # Create data object
        data = Data(x=x, edge_index=edge_index_tensor, y=y)
        
        # Training setup
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCELoss()
        
        self.model.train()
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            
            # Forward pass
            predictions = self.model(data.x, data.edge_index)
            
            # Compute loss
            loss = criterion(predictions, data.y)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
        
        # Convert to INT8 if quantization enabled
        if self.use_quantization:
            self.model.convert_to_int8()
            logger.info("Model converted to INT8 quantized format")
        
        self.is_trained = True
        logger.info("GraphSAGE v2 training completed")
    
    def predict(
        self,
        node_id: str,
        node_features: Dict[str, float],
        neighbors: List[Tuple[str, Dict[str, float]]],
        edge_index: Optional[List[Tuple[int, int]]] = None
    ) -> AnomalyPrediction:
        """
        Predict anomaly for a single node.
        
        Args:
            node_id: Node identifier
            node_features: Node feature dict (RSSI, SNR, loss rate, etc.)
            neighbors: List of (neighbor_id, neighbor_features) tuples
            edge_index: Optional edge connectivity (auto-generated if None)
        
        Returns:
            AnomalyPrediction with anomaly score and confidence
        """
        start_time = time.time()
        
        if not _TORCH_AVAILABLE or self.model is None or not self.is_trained:
            # Fallback to simple threshold-based detection
            return self._fallback_predict(node_id, node_features, start_time)
        
        # Prepare graph data
        all_nodes = [(node_id, node_features)] + neighbors
        x = self._features_to_tensor([features for _, features in all_nodes])
        
        # Generate edge_index if not provided
        if edge_index is None:
            # Connect node to all neighbors
            edge_index = [(0, i+1) for i in range(len(neighbors))]
            edge_index += [(i+1, 0) for i in range(len(neighbors))]  # Bidirectional
        
        edge_index_tensor = self._edges_to_tensor(edge_index)
        
        # Inference
        self.model.eval()
        with torch.no_grad():
            predictions = self.model(x.to(self.device), edge_index_tensor.to(self.device))
            anomaly_score = float(predictions[0].item())
        
        inference_time = (time.time() - start_time) * 1000  # ms
        
        is_anomaly = anomaly_score >= self.anomaly_threshold
        confidence = abs(anomaly_score - 0.5) * 2  # Distance from threshold
        
        return AnomalyPrediction(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            node_id=node_id,
            features=node_features,
            inference_time_ms=inference_time
        )
    
    def _features_to_tensor(self, features_list: List[Dict[str, float]]) -> torch.Tensor:
        """Convert list of feature dicts to tensor."""
        feature_names = ['rssi', 'snr', 'loss_rate', 'link_age', 'latency', 'throughput', 'cpu', 'memory']
        
        tensor_data = []
        for features in features_list:
            row = [features.get(name, 0.0) for name in feature_names]
            tensor_data.append(row)
        
        return torch.tensor(tensor_data, dtype=torch.float)
    
    def _edges_to_tensor(self, edges: List[Tuple[int, int]]) -> torch.Tensor:
        """Convert edge list to tensor format."""
        if not edges:
            return torch.tensor([[], []], dtype=torch.long)
        
        edge_list = [[src, tgt] for src, tgt in edges]
        return torch.tensor(edge_list, dtype=torch.long).t().contiguous()
    
    def _generate_labels(self, node_features: List[Dict[str, float]]) -> List[float]:
        """Generate simple heuristic labels for training."""
        labels = []
        for features in node_features:
            # Simple heuristic: high loss rate or low RSSI = anomaly
            loss_rate = features.get('loss_rate', 0.0)
            rssi = features.get('rssi', -50.0)
            
            is_anomaly = loss_rate > 0.05 or rssi < -80.0
            labels.append(1.0 if is_anomaly else 0.0)
        
        return labels
    
    def _fallback_predict(
        self,
        node_id: str,
        node_features: Dict[str, float],
        start_time: float
    ) -> AnomalyPrediction:
        """Fallback prediction when model not available."""
        # Simple threshold-based detection
        loss_rate = node_features.get('loss_rate', 0.0)
        rssi = node_features.get('rssi', -50.0)
        
        anomaly_score = (loss_rate / 0.1) * 0.5 + ((rssi + 80) / 30) * 0.5
        anomaly_score = max(0.0, min(1.0, anomaly_score))
        
        is_anomaly = anomaly_score >= self.anomaly_threshold
        confidence = abs(anomaly_score - 0.5) * 2
        
        inference_time = (time.time() - start_time) * 1000
        
        return AnomalyPrediction(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            node_id=node_id,
            features=node_features,
            inference_time_ms=inference_time
        )
    
    def save_model(self, path: str):
        """Save model to file."""
        if not _TORCH_AVAILABLE or self.model is None:
            logger.warning("Cannot save model: PyTorch not available")
            return
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'num_layers': self.num_layers,
            'anomaly_threshold': self.anomaly_threshold,
            'is_trained': self.is_trained
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """Load model from file."""
        if not _TORCH_AVAILABLE:
            logger.warning("Cannot load model: PyTorch not available")
            return
        
        checkpoint = torch.load(path, map_location=self.device)
        
        self.model = GraphSAGEAnomalyDetectorV2(
            input_dim=checkpoint['input_dim'],
            hidden_dim=checkpoint['hidden_dim'],
            num_layers=checkpoint['num_layers']
        ).to(self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.anomaly_threshold = checkpoint['anomaly_threshold']
        self.is_trained = checkpoint.get('is_trained', False)
        
        if self.use_quantization:
            self.model.prepare_for_quantization()
            self.model.convert_to_int8()
        
        logger.info(f"Model loaded from {path}")


# Integration with MAPE-K
def create_graphsage_detector_for_mapek() -> GraphSAGEAnomalyDetector:
    """
    Create GraphSAGE detector configured for MAPE-K integration.
    
    Returns:
        GraphSAGEAnomalyDetector instance ready for use in Monitor phase
    """
    detector = GraphSAGEAnomalyDetector(
        input_dim=8,
        hidden_dim=64,
        num_layers=2,
        anomaly_threshold=0.6,
        use_quantization=True
    )
    
    return detector

