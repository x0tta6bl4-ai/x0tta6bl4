"""
src.core.health — Health checks, status collection, dependency monitoring.
"""
from __future__ import annotations

from src.core.health.dependency_health import DependencyHealthChecker, check_dependencies_health
from src.core.health.health import get_health, get_health_with_dependencies
from src.core.health.health_check import (
    CheckResult,
    HealthChecker,
    HealthCheckResponse,
    HealthStatus,
)
from src.core.health.status_collector import get_current_status

__all__ = [
    "get_health",
    "get_health_with_dependencies",
    "HealthChecker",
    "HealthCheckResponse",
    "HealthStatus",
    "CheckResult",
    "DependencyHealthChecker",
    "check_dependencies_health",
    "get_current_status",
]

