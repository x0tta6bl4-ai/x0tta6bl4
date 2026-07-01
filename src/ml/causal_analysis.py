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
    def __init__(self, incident_id: str = "", event_type: str = "", data: dict | None = None):
        self.incident_id = incident_id
        self.event_type = event_type
        self.data = data or {}


class CausalAnalysisVisualizer:
    """Causal analysis visualizer stub."""
    def generate_report(self, analysis: dict) -> str:
        return "causal_report"
