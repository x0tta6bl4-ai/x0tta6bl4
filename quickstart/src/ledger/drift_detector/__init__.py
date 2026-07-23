"""Drift detection package."""
from __future__ import annotations
from typing import Optional

from .models import DriftResult
from .core import LedgerDriftDetector
from .graph import CONTINUITY_FILE, PROJECT_ROOT
from .checkers import find_metrics

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Singleton instance
_drift_detector_instance: Optional[LedgerDriftDetector] = None

def get_drift_detector() -> LedgerDriftDetector:
    """Получить singleton instance LedgerDriftDetector"""
    global _drift_detector_instance
    if _drift_detector_instance is None:
        _drift_detector_instance = LedgerDriftDetector()
    return _drift_detector_instance
