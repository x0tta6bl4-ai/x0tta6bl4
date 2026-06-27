"""Drift detection models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
@dataclass

class DriftResult:
    """Результат обнаружения расхождений"""

    drift_type: str  # "code_drift", "metrics_drift", "doc_drift", "config_drift"
    severity: str  # "low", "medium", "high", "critical"
    description: str
    section: str
    detected_at: str
    recommendations: List[str]
    metadata: Dict[str, Any] = None


