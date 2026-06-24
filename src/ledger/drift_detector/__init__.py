"""Drift detection package."""
from __future__ import annotations
from .models import DriftResult
from .core import LedgerDriftDetector

def get_drift_detector() -> LedgerDriftDetector:
    """Получить singleton instance LedgerDriftDetector"""
    global _drift_detector_instance
    if _drift_detector_instance is None:
        _drift_detector_instance = LedgerDriftDetector()
    return _drift_detector_instance

