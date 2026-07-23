"""
src.core.config — Settings, feature flags, lazy import helpers.
"""
from __future__ import annotations

from src.core.config.feature_flags import FeatureFlags
from src.core.config.lazy_imports import LazyModule
from src.core.config.settings import settings

__all__ = [
    "settings",
    "FeatureFlags",
    "LazyModule",
]

