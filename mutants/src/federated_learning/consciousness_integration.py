"""
FL-Consciousness Engine Integration
===================================

Интегрирует агрегированные FL модели обратно в Consciousness Engine
для использования в MAPE-K Analyze и Plan фазах.

Функции:
- Загрузка глобальной модели в Consciousness Engine
- Использование модели для предиктивного анализа
- Обновление директив на основе FL-предсказаний
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .protocol import GlobalModel, ModelWeights
from ..core.consciousness import ConsciousnessEngine, ConsciousnessMetrics

logger = logging.getLogger(__name__)


@dataclass
class FLPrediction:
    """Prediction from FL model."""
    anomaly_score: float  # 0.0 - 1.0
    predicted_latency: float
    predicted_packet_loss: float
    confidence: float  # 0.0 - 1.0
    recommendations: List[str]


class FLConsciousnessIntegration:
    """
    Интеграция FL моделей с Consciousness Engine.
    
    Usage:
        integration = FLConsciousnessIntegration(consciousness_engine)
        integration.load_global_model(global_model)
        prediction = integration.predict(metrics)
    """
    
    def __init__(self, consciousness_engine: ConsciousnessEngine):
        self.consciousness = consciousness_engine
        self.global_model: Optional[GlobalModel] = None
        self.model_weights: Optional[ModelWeights] = None
        
        logger.info("FLConsciousnessIntegration initialized")
    
    def load_global_model(self, global_model: GlobalModel):
        """Load global model from FL Coordinator."""
        self.global_model = global_model
        self.model_weights = global_model.weights
        logger.info(
            f"✅ Global FL model loaded: round {global_model.round_number}, "
            f"weights={len(global_model.weights.weights)}"
        )
    
    def predict(self, metrics: Dict[str, float]) -> Optional[FLPrediction]:
        """
        Predict system state using FL model.
        
        Args:
            metrics: System metrics (same format as MeshMetrics)
            
        Returns:
            FLPrediction with anomaly score and recommendations
        """
        if not self.model_weights:
            logger.warning("No FL model loaded, cannot predict")
            return None
        
        # Convert metrics to feature vector (same as MeshMetrics.to_feature_vector)
        features = [
            metrics.get("cpu_percent", 0.0) / 100.0,
            metrics.get("memory_percent", 0.0) / 100.0,
            metrics.get("peers_count", 0) / 100.0,
            metrics.get("latency_ms", 0.0) / 1000.0,
            metrics.get("packet_loss_percent", 0.0) / 100.0,
            metrics.get("throughput_mbps", 0.0) / 1000.0,
            metrics.get("zero_trust_success_rate", 1.0),
            metrics.get("byzantine_detections", 0) / 10.0,
            metrics.get("routes_count", 0) / 50.0,
            metrics.get("failover_count", 0) / 10.0
        ]
        
        # Simple prediction using model weights
        # In production, this would use actual ML model inference
        weights = self.model_weights.weights
        if len(weights) != len(features):
            logger.warning(f"Weight/feature mismatch: {len(weights)} vs {len(features)}")
            return None
        
        # Calculate anomaly score (distance from learned pattern)
        anomaly_score = sum(
            abs(f - w) for f, w in zip(features, weights)
        ) / len(features)
        
        # Predict latency and packet loss
        predicted_latency = features[3] * 1000  # Convert back to ms
        predicted_packet_loss = features[4] * 100  # Convert back to percent
        
        # Confidence based on how well features match weights
        confidence = 1.0 - min(anomaly_score, 1.0)
        
        # Generate recommendations
        recommendations = []
        if anomaly_score > 0.7:
            recommendations.append("High anomaly detected - trigger aggressive healing")
        if predicted_latency > 500:
            recommendations.append("High latency predicted - switch to low-latency routes")
        if predicted_packet_loss > 5.0:
            recommendations.append("High packet loss predicted - check network links")
        if metrics.get("cpu_percent", 0) > 80:
            recommendations.append("High CPU - consider load balancing")
        
        prediction = FLPrediction(
            anomaly_score=anomaly_score,
            predicted_latency=predicted_latency,
            predicted_packet_loss=predicted_packet_loss,
            confidence=confidence,
            recommendations=recommendations
        )
        
        return prediction
    
    def enhance_consciousness_analysis(
        self,
        raw_metrics: Dict[str, float],
        consciousness_metrics: ConsciousnessMetrics
    ) -> Dict[str, Any]:
        """
        Enhance Consciousness Engine analysis with FL predictions.
        
        Args:
            raw_metrics: Raw system metrics
            consciousness_metrics: Current consciousness metrics
            
        Returns:
            Enhanced analysis with FL predictions
        """
        prediction = self.predict(raw_metrics)
        
        if not prediction:
            return {
                "enhanced": False,
                "consciousness_metrics": consciousness_metrics
            }
        
        # Adjust phi-ratio based on anomaly score
        # Higher anomaly = lower harmony
        adjusted_phi = consciousness_metrics.phi_ratio * (1.0 - prediction.anomaly_score * 0.3)
        
        enhanced = {
            "enhanced": True,
            "consciousness_metrics": consciousness_metrics,
            "fl_prediction": {
                "anomaly_score": prediction.anomaly_score,
                "predicted_latency": prediction.predicted_latency,
                "predicted_packet_loss": prediction.predicted_packet_loss,
                "confidence": prediction.confidence
            },
            "adjusted_phi": adjusted_phi,
            "recommendations": prediction.recommendations
        }
        
        logger.info(
            f"🧠 FL-enhanced analysis: anomaly={prediction.anomaly_score:.3f}, "
            f"phi={consciousness_metrics.phi_ratio:.3f} → {adjusted_phi:.3f}"
        )
        
        return enhanced
    
    def enhance_plan_directives(
        self,
        directives: Dict[str, Any],
        fl_prediction: Optional[FLPrediction]
    ) -> Dict[str, Any]:
        """
        Enhance Plan phase directives with FL predictions.
        
        Args:
            directives: Current directives from Consciousness Engine
            fl_prediction: FL prediction (if available)
            
        Returns:
            Enhanced directives
        """
        if not fl_prediction:
            return directives
        
        enhanced = directives.copy()
        
        # Add FL-based recommendations
        if fl_prediction.anomaly_score > 0.7:
            enhanced["enable_aggressive_healing"] = True
            enhanced["fl_triggered_healing"] = True
        
        if fl_prediction.predicted_latency > 500:
            enhanced["route_preference"] = "low_latency"
            enhanced["fl_route_optimization"] = True
        
        if fl_prediction.predicted_packet_loss > 5.0:
            enhanced["preemptive_healing"] = True
            enhanced["fl_preemptive_action"] = True
        
        # Add FL recommendations to directives
        if fl_prediction.recommendations:
            enhanced["fl_recommendations"] = fl_prediction.recommendations
        
        logger.info(
            f"📋 FL-enhanced directives: "
            f"aggressive_healing={enhanced.get('enable_aggressive_healing', False)}, "
            f"route_pref={enhanced.get('route_preference', 'balanced')}"
        )
        
        return enhanced

