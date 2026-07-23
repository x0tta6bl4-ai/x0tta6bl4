"""Causal analysis — stub for test compatibility."""

from __future__ import annotations

from typing import Any
from enum import Enum


class IncidentSeverity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class CausalAnalysisEngine:
    """Causal analysis engine stub."""
    def __init__(self):
        self.incidents: dict[str, Any] = {}

    def analyze(self, incident_id: str) -> dict[str, Any]:
        return {"incident_id": incident_id, "cause": "unknown", "confidence": 0.5}


class CausalAnalysisResult:
    """Causal analysis result stub."""
    def __init__(self, incident_id: str = "", cause: str = "unknown"):
        self.incident_id = incident_id
        self.cause = cause


class IncidentEvent:
    """Incident event stub."""
    def __init__(
        self,
        incident_id: str = "",
        event_type: str = "",
        data: dict | None = None,
        event_id: str = "",
        timestamp: Any = None,
        node_id: str = "",
        service_id: str | None = None,
        anomaly_type: str = "",
        severity: Any = None,
        metrics: dict | None = None,
        detected_by: str = "",
        anomaly_score: float = 0.0,
        **kwargs: Any,
    ):
        self.incident_id = incident_id or event_id
        self.event_id = event_id or incident_id
        self.event_type = event_type or anomaly_type
        self.timestamp = timestamp
        self.node_id = node_id
        self.service_id = service_id
        self.anomaly_type = anomaly_type
        self.severity = severity
        self.metrics = metrics or {}
        self.detected_by = detected_by
        self.anomaly_score = anomaly_score
        self.data = data or {}
        for k, v in kwargs.items():
            self.data[k] = v


class CausalAnalysisVisualizer:
    """Causal analysis visualizer stub."""
    def generate_report(self, analysis: dict) -> str:
        return "causal_report"
