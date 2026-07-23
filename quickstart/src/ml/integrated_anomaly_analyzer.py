"""Integrated anomaly analyzer — processes node anomalies with GNN-enhanced detection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeAnomalyResult:
    """Result of a node anomaly analysis."""
    is_anomaly: bool = False
    anomaly_score: float = 0.0
    anomaly_confidence: float = 0.0
    node_id: str = ""
    service_id: str = ""
    features: dict = field(default_factory=dict)
    neighbors: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


class IntegratedAnomalyAnalyzer:
    """Analyzes node-level anomalies using a detector and knowledge base."""

    def __init__(self, detector: Any = None, knowledge_base: Any = None) -> None:
        self.detector = detector
        self.knowledge_base = knowledge_base
        self._results: list[NodeAnomalyResult] = []

    def process_node_anomaly(
        self,
        node_id: str,
        node_features: dict,
        neighbors: list | None = None,
        service_id: str = "",
    ) -> NodeAnomalyResult:
        """Process and analyze a potential node anomaly."""
        if self.detector and hasattr(self.detector, 'predict_enhanced'):
            pred = self.detector.predict_enhanced(features=node_features)
        else:
            pred = {"is_anomaly": False, "anomaly_score": 0.0, "anomaly_confidence": 0.0}

        result = NodeAnomalyResult(
            is_anomaly=pred.get("is_anomaly", False),
            anomaly_score=pred.get("anomaly_score", 0.0),
            anomaly_confidence=pred.get("anomaly_confidence", 0.0),
            node_id=node_id,
            service_id=service_id,
            features=node_features,
            neighbors=neighbors or [],
        )
        self._results.append(result)
        return result

    def analyze(self, data: Any) -> dict:
        return {"anomaly_score": 0.0, "is_anomaly": False}

    def get_thinking_status(self) -> dict[str, Any]:
        """Get redacted status for AI thinking."""
        return {
            "thinking": {
                "profile": {"role": "monitoring"},
                "state": "active",
                "recent_analyses": len(self._results),
            }
        }
