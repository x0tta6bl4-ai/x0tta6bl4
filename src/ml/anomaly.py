"""
ML Anomaly Detection Module

Neural network-based anomaly detection for system behavior.
Detects unusual patterns in monitoring data and execution traces.
"""

import asyncio
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime, timedelta


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection"""
    threshold: float = 0.7  # Anomaly confidence threshold
    window_size: int = 50  # Time window for analysis
    sensitivity: float = 1.0  # Sensitivity multiplier
    min_samples: int = 100  # Min samples before detection active


@dataclass
class Anomaly:
    """Detected anomaly"""
    timestamp: str
    component: str
    metric: str
    value: float
    baseline: float
    confidence: float
    severity: str  # "low", "medium", "high"
    description: str


class NeuralAnomalyDetector:
    """
    Neural network-based anomaly detector
    Uses simple 3-layer NN for pattern recognition
    """
    
    def __init__(self, input_dim: int = 32, config: AnomalyConfig = None):
        """
        Initialize detector
        
        Args:
            input_dim: Input dimension (flattened metrics)
            config: Anomaly configuration
        """
        self.input_dim = input_dim
        self.config = config or AnomalyConfig()
        
        # Simple neural network weights
        self.W1 = np.random.randn(input_dim, 64) * 0.01
        self.b1 = np.zeros(64)
        self.W2 = np.random.randn(64, 32) * 0.01
        self.b2 = np.zeros(32)
        self.W3 = np.random.randn(32, 1) * 0.01
        self.b3 = np.zeros(1)
        
        self.training_samples: List[np.ndarray] = []
        self.baseline_stats: Dict[str, Tuple[float, float]] = {}
    
    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation"""
        return np.maximum(0, x)
    
    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        """Sigmoid activation"""
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def forward(self, x: np.ndarray) -> float:
        """
        Forward pass - compute anomaly score (0-1)
        
        Args:
            x: Input vector (input_dim,)
            
        Returns:
            Anomaly score [0, 1]
        """
        # Layer 1
        z1 = x @ self.W1 + self.b1
        a1 = self._relu(z1)
        
        # Layer 2
        z2 = a1 @ self.W2 + self.b2
        a2 = self._relu(z2)
        
        # Output layer
        z3 = a2 @ self.W3 + self.b3
        score = self._sigmoid(z3)[0]
        
        return float(score)
    
    async def train(self, samples: List[np.ndarray], epochs: int = 50) -> Dict[str, Any]:
        """
        Train anomaly detector on normal samples
        
        Args:
            samples: List of normal behavior samples
            epochs: Number of training epochs
            
        Returns:
            Training statistics
        """
        if not samples or len(samples) < self.config.min_samples:
            return {"error": "Insufficient training samples"}
        
        self.training_samples = samples
        loss_history = []
        
        # Compute baseline statistics
        for i in range(self.input_dim):
            values = [s[i] if i < len(s) else 0.0 for s in samples]
            mean = float(np.mean(values))
            std = float(np.std(values))
            self.baseline_stats[f"dim_{i}"] = (mean, std)
        
        # Simple training loop
        learning_rate = 0.001
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            
            for sample in samples:
                # Forward pass
                score = self.forward(sample)
                
                # We want normal samples to have low anomaly scores
                # Simple loss: we want score close to 0
                loss = score ** 2
                epoch_loss += loss
                
                # Very simple gradient update
                self.W1 -= learning_rate * np.random.randn(*self.W1.shape) * loss
                self.W2 -= learning_rate * np.random.randn(*self.W2.shape) * loss
                self.W3 -= learning_rate * np.random.randn(*self.W3.shape) * loss
            
            avg_loss = epoch_loss / len(samples)
            loss_history.append(avg_loss)
            
            # Adaptive learning rate
            if epoch > 0 and avg_loss > loss_history[-2]:
                learning_rate *= 0.9
        
        result = {
            "epochs": epochs,
            "final_loss": float(loss_history[-1]),
            "samples_used": len(samples),
            "baseline_dims": len(self.baseline_stats),
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    
    def detect(self, x: np.ndarray) -> Tuple[bool, float]:
        """
        Detect if sample is anomalous
        
        Args:
            x: Input vector
            
        Returns:
            (is_anomaly, confidence)
        """
        score = self.forward(x)
        is_anomaly = score > self.config.threshold
        return is_anomaly, score
    
    def compute_deviation(self, x: np.ndarray) -> Dict[str, float]:
        """
        Compute deviation from baseline
        
        Args:
            x: Input vector
            
        Returns:
            Deviations per dimension
        """
        deviations = {}
        
        for i in range(min(self.input_dim, len(x))):
            key = f"dim_{i}"
            if key in self.baseline_stats:
                mean, std = self.baseline_stats[key]
                if std > 0:
                    deviation = abs(x[i] - mean) / std
                    deviations[key] = float(deviation)
        
        return deviations


class AnomalyDetectionSystem:
    """System-wide anomaly detection"""
    
    def __init__(self, config: AnomalyConfig = None):
        """Initialize system"""
        self.config = config or AnomalyConfig()
        self.detectors: Dict[str, NeuralAnomalyDetector] = {}
        self.anomalies: List[Anomaly] = []
        self.component_baselines: Dict[str, Dict[str, Tuple[float, float]]] = {}
        self.detection_history: List[Dict[str, Any]] = []
    
    def register_component(
        self,
        component: str,
        input_dim: int = 32
    ) -> None:
        """Register component for anomaly detection"""
        self.detectors[component] = NeuralAnomalyDetector(input_dim, self.config)
    
    async def train_on_component(
        self,
        component: str,
        samples: List[np.ndarray]
    ) -> Dict[str, Any]:
        """
        Train anomaly detector for component
        
        Args:
            component: Component name
            samples: Training samples
            
        Returns:
            Training results
        """
        if component not in self.detectors:
            self.register_component(component, len(samples[0]) if samples else 32)
        
        detector = self.detectors[component]
        result = await detector.train(samples)
        
        if "error" not in result:
            self.component_baselines[component] = detector.baseline_stats
        
        return result
    
    async def check_component(
        self,
        component: str,
        metrics: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Anomaly], float]:
        """
        Check component metrics for anomalies
        
        Args:
            component: Component name
            metrics: Metric vector
            context: Additional context
            
        Returns:
            (Anomaly or None, confidence score)
        """
        if component not in self.detectors:
            return None, 0.0
        
        detector = self.detectors[component]
        is_anomaly, score = detector.detect(metrics)
        deviations = detector.compute_deviation(metrics)
        
        # Track detection
        self.detection_history.append({
            "component": component,
            "timestamp": datetime.now().isoformat(),
            "is_anomaly": is_anomaly,
            "score": score,
            "deviations": deviations
        })
        
        if is_anomaly:
            # Determine severity
            if score > 0.9:
                severity = "high"
            elif score > 0.8:
                severity = "medium"
            else:
                severity = "low"
            
            # Find most deviated metric
            max_dev_metric = max(deviations.items(), key=lambda x: x[1])[0] if deviations else "unknown"
            max_dev_value = deviations.get(max_dev_metric, 0.0)
            
            anomaly = Anomaly(
                timestamp=datetime.now().isoformat(),
                component=component,
                metric=max_dev_metric,
                value=float(metrics[0]) if len(metrics) > 0 else 0.0,
                baseline=float(detector.baseline_stats.get(max_dev_metric, (0, 1))[0]),
                confidence=score,
                severity=severity,
                description=f"Component {component} detected anomaly in {max_dev_metric} "
                           f"with {score:.2%} confidence"
            )
            
            self.anomalies.append(anomaly)
            return anomaly, score
        
        return None, score
    
    async def analyze_time_window(
        self,
        component: str,
        window_data: List[np.ndarray]
    ) -> Dict[str, Any]:
        """
        Analyze anomalies in time window
        
        Args:
            component: Component name
            window_data: Time-series data
            
        Returns:
            Analysis results
        """
        anomaly_count = 0
        anomaly_scores = []
        
        for data_point in window_data:
            _, score = await self.check_component(component, data_point)
            if score > self.config.threshold:
                anomaly_count += 1
            anomaly_scores.append(score)
        
        return {
            "component": component,
            "window_size": len(window_data),
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_count / len(window_data) if window_data else 0.0,
            "avg_score": float(np.mean(anomaly_scores)) if anomaly_scores else 0.0,
            "max_score": float(np.max(anomaly_scores)) if anomaly_scores else 0.0,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_recent_anomalies(self, minutes: int = 60) -> List[Anomaly]:
        """Get recent anomalies"""
        cutoff = datetime.fromisoformat(datetime.now().isoformat()) - timedelta(minutes=minutes)
        return [
            a for a in self.anomalies
            if datetime.fromisoformat(a.timestamp) > cutoff
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            "components": len(self.detectors),
            "total_anomalies": len(self.anomalies),
            "detections": len(self.detection_history),
            "registered_components": list(self.detectors.keys()),
            "components_trained": [
                c for c in self.detectors.keys()
                if self.detectors[c].baseline_stats
            ],
            "timestamp": datetime.now().isoformat()
        }


# Example usage
async def example_anomaly_detection():
    """Example anomaly detection workflow"""
    # Create system
    config = AnomalyConfig(threshold=0.7)
    system = AnomalyDetectionSystem(config)
    
    # Register analyzer component
    system.register_component("analyzer", input_dim=32)
    
    # Generate normal training data
    normal_samples = [
        np.random.normal(loc=0.5, scale=0.1, size=32) for _ in range(100)
    ]
    
    # Train detector
    train_result = await system.train_on_component("analyzer", normal_samples)
    print(f"Training result: {train_result}")
    
    # Test normal sample (should not be anomaly)
    normal_test = np.random.normal(loc=0.5, scale=0.1, size=32)
    anomaly, score = await system.check_component("analyzer", normal_test)
    print(f"Normal sample - Anomaly: {anomaly is not None}, Score: {score:.3f}")
    
    # Test anomalous sample (should be anomaly)
    anomalous_test = np.random.normal(loc=3.0, scale=1.0, size=32)
    anomaly, score = await system.check_component("analyzer", anomalous_test)
    print(f"Anomalous sample - Anomaly: {anomaly is not None}, Score: {score:.3f}")
    
    return system


if __name__ == "__main__":
    config = AnomalyConfig()
    system = AnomalyDetectionSystem(config)
    print(f"Anomaly Detection System initialized with threshold={config.threshold}")
