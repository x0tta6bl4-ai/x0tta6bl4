"""
Hybrid Anomaly Detection System

Combines:
- Production Anomaly Detector (adaptive thresholds, seasonality)
- Ensemble Methods (multiple algorithms + voting)
For superior anomaly detection accuracy
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from src.ml.production_anomaly_detector import (
    ProductionAnomalyDetector,
    AnomalySeverity
)
from src.ml.ensemble_anomaly_detector import (
    EnsembleAnomalyDetector,
    EnsembleVotingStrategy
)

logger = logging.getLogger(__name__)


class HybridDetectionMode(Enum):
    """Hybrid detection modes"""
    PRODUCTION_ONLY = "production_only"
    ENSEMBLE_ONLY = "ensemble_only"
    HYBRID = "hybrid"
    CONSENSUS = "consensus"


@dataclass
class HybridDetectionResult:
    """Result from hybrid detection"""
    timestamp: datetime
    component: str
    metric_name: str
    value: float
    is_anomaly: bool
    severity: Optional[AnomalySeverity]
    confidence: float
    
    production_detection: Optional[bool] = None
    production_confidence: Optional[float] = None
    
    ensemble_detection: Optional[bool] = None
    ensemble_confidence: Optional[float] = None
    ensemble_votes: Optional[Dict[str, bool]] = None
    
    agreement: bool = False
    detection_method: str = ""
    reasoning: str = ""


class HybridAnomalySystem:
    """Hybrid anomaly detection system"""
    
    def __init__(self, mode: HybridDetectionMode = HybridDetectionMode.HYBRID):
        self.mode = mode
        self.production_detector = ProductionAnomalyDetector(sensitivity=2.5)
        self.ensemble_detector = EnsembleAnomalyDetector(EnsembleVotingStrategy.WEIGHTED)
        
        self.detections: List[HybridDetectionResult] = []
        self.agreement_ratio = 0.0
        self.component_agreement: Dict[str, float] = {}
    
    def record_metric(self, component: str, metric_name: str, 
                     value: float) -> Optional[HybridDetectionResult]:
        """Record metric and perform hybrid detection"""
        
        full_metric = f"{component}_{metric_name}"
        
        prod_result = None
        ensemble_result = None
        
        if self.mode in (HybridDetectionMode.PRODUCTION_ONLY, HybridDetectionMode.HYBRID, 
                         HybridDetectionMode.CONSENSUS):
            prod_result = self.production_detector.record_metric(component, metric_name, value)
        
        if self.mode in (HybridDetectionMode.ENSEMBLE_ONLY, HybridDetectionMode.HYBRID,
                         HybridDetectionMode.CONSENSUS):
            self.ensemble_detector.fit(full_metric, 
                                      list(self.production_detector.metric_history.get(full_metric, []))[-100:])
            ensemble_result = self.ensemble_detector.predict(full_metric, value)
        
        return self._combine_results(
            component, metric_name, value,
            prod_result, ensemble_result
        )
    
    def _combine_results(self, component: str, metric_name: str, value: float,
                        prod_result, ensemble_result) -> Optional[HybridDetectionResult]:
        """Combine production and ensemble detection results"""
        
        timestamp = datetime.utcnow()
        full_metric = f"{component}_{metric_name}"
        
        is_anomaly = False
        confidence = 0.0
        severity = None
        agreement = False
        detection_method = ""
        reasoning = ""
        
        if self.mode == HybridDetectionMode.PRODUCTION_ONLY:
            if prod_result:
                is_anomaly = True
                severity = prod_result.severity
                confidence = prod_result.confidence
                detection_method = "PRODUCTION"
                reasoning = prod_result.description
            else:
                return None
        
        elif self.mode == HybridDetectionMode.ENSEMBLE_ONLY:
            if ensemble_result:
                is_anomaly = ensemble_result.is_anomaly
                confidence = ensemble_result.confidence
                detection_method = "ENSEMBLE"
                reasoning = ensemble_result.detection_reason
                severity = self._estimate_severity_from_confidence(confidence)
            else:
                return None
        
        elif self.mode == HybridDetectionMode.HYBRID:
            prod_anom = prod_result is not None
            ensemble_anom = ensemble_result and ensemble_result.is_anomaly
            
            agreement = prod_anom == ensemble_anom
            
            if prod_anom or ensemble_anom:
                is_anomaly = True
                
                prod_conf = prod_result.confidence if prod_result else 0.0
                ensemble_conf = ensemble_result.confidence if ensemble_result else 0.0
                
                confidence = (prod_conf + ensemble_conf) / 2.0
                
                if agreement:
                    detection_method = "HYBRID_AGREED"
                    reasoning = f"Both methods detected anomaly. Production: {prod_conf:.2f}, Ensemble: {ensemble_conf:.2f}"
                else:
                    detection_method = "HYBRID_SPLIT"
                    reasoning = f"Methods disagreed. Production: {prod_anom}, Ensemble: {ensemble_anom}"
                
                severity = prod_result.severity if prod_result else self._estimate_severity_from_confidence(confidence)
        
        elif self.mode == HybridDetectionMode.CONSENSUS:
            prod_anom = prod_result is not None
            ensemble_anom = ensemble_result and ensemble_result.is_anomaly
            
            if prod_anom and ensemble_anom:
                is_anomaly = True
                agreement = True
                confidence = min(
                    prod_result.confidence if prod_result else 0.0,
                    ensemble_result.confidence if ensemble_result else 0.0
                )
                detection_method = "CONSENSUS"
                reasoning = "Both methods confirm anomaly (consensus)"
                severity = prod_result.severity if prod_result else AnomalySeverity.MEDIUM
            else:
                return None
        
        result = HybridDetectionResult(
            timestamp=timestamp,
            component=component,
            metric_name=metric_name,
            value=value,
            is_anomaly=is_anomaly,
            severity=severity,
            confidence=confidence,
            production_detection=prod_result is not None if prod_result else None,
            production_confidence=prod_result.confidence if prod_result else None,
            ensemble_detection=ensemble_result.is_anomaly if ensemble_result else None,
            ensemble_confidence=ensemble_result.confidence if ensemble_result else None,
            ensemble_votes=ensemble_result.algorithm_votes if ensemble_result else None,
            agreement=agreement,
            detection_method=detection_method,
            reasoning=reasoning
        )
        
        self.detections.append(result)
        self._update_agreement_ratio(component)
        
        return result
    
    def _estimate_severity_from_confidence(self, confidence: float) -> AnomalySeverity:
        """Estimate severity from confidence score"""
        if confidence > 0.9:
            return AnomalySeverity.CRITICAL
        elif confidence > 0.75:
            return AnomalySeverity.HIGH
        elif confidence > 0.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    def _update_agreement_ratio(self, component: str) -> None:
        """Update agreement ratio for component"""
        component_detections = [
            d for d in self.detections if d.component == component
        ]
        
        if not component_detections:
            return
        
        agreed = sum(1 for d in component_detections if d.agreement)
        self.component_agreement[component] = agreed / len(component_detections) if component_detections else 0.0
        
        all_agreed = sum(1 for d in self.detections if d.agreement)
        self.agreement_ratio = all_agreed / len(self.detections) if self.detections else 0.0
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get hybrid system health"""
        return {
            "mode": self.mode.value,
            "total_detections": len(self.detections),
            "agreement_ratio": self.agreement_ratio,
            "component_agreement": self.component_agreement,
            "production_health": self.production_detector.get_anomaly_summary(),
            "ensemble_health": self.ensemble_detector.get_detector_health(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_component_analysis(self, component: str) -> Dict[str, Any]:
        """Analyze component with hybrid system"""
        component_detections = [
            d for d in self.detections if d.component == component
        ]
        
        anomalies = [d for d in component_detections if d.is_anomaly]
        
        return {
            "component": component,
            "total_records": len(component_detections),
            "anomaly_count": len(anomalies),
            "anomaly_rate": len(anomalies) / len(component_detections) if component_detections else 0.0,
            "agreement_ratio": self.component_agreement.get(component, 0.0),
            "avg_confidence": sum(d.confidence for d in anomalies) / len(anomalies) if anomalies else 0.0,
            "severity_distribution": self._get_severity_distribution(anomalies),
            "detection_methods": self._get_detection_methods(anomalies),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_severity_distribution(self, anomalies: List[HybridDetectionResult]) -> Dict[str, int]:
        """Get distribution of severity levels"""
        dist = {}
        for anom in anomalies:
            if anom.severity:
                key = anom.severity.value
                dist[key] = dist.get(key, 0) + 1
        return dist
    
    def _get_detection_methods(self, anomalies: List[HybridDetectionResult]) -> Dict[str, int]:
        """Get distribution of detection methods"""
        methods = {}
        for anom in anomalies:
            methods[anom.detection_method] = methods.get(anom.detection_method, 0) + 1
        return methods


_hybrid_system = None

def get_hybrid_anomaly_system(mode: HybridDetectionMode = HybridDetectionMode.HYBRID) -> HybridAnomalySystem:
    """Get or create singleton hybrid system"""
    global _hybrid_system
    if _hybrid_system is None:
        _hybrid_system = HybridAnomalySystem(mode)
    return _hybrid_system


__all__ = [
    "HybridDetectionMode",
    "HybridDetectionResult",
    "HybridAnomalySystem",
    "get_hybrid_anomaly_system",
]
