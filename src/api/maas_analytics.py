"""Compatibility wrapper for the modular MaaS analytics endpoint."""

import sys

import logging
import os
from typing import Any, Dict

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.maas_auth import require_permission
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import User, get_db
from src.services.maas_analytics_service import MaaSAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/analytics", tags=["MaaS Analytics"])

# Redis for real-time telemetry (optional)
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    _redis_client = redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    _redis_client.ping()
except Exception:
    _redis_client = None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnalyticsSummary(BaseModel):
    mesh_id: str
    cost_maas_total: float
    cost_aws_estimate: float
    savings_pct: float
    pqc_status: bool
    nodes_total: int
    nodes_online: int
    health_score: float


def _analytics_db_session_available(db: Any) -> bool:
    return hasattr(db, "query")


def _analytics_readiness_status(db: Any) -> Dict[str, Any]:
    analytics_db_ready = _analytics_db_session_available(db)
    analytics_service_ready = callable(MaaSAnalyticsService)
    realtime_telemetry_ready = _redis_client is not None
    analytics_runtime_ready = analytics_db_ready and analytics_service_ready

    degraded_dependencies = []
    if not analytics_db_ready:
        degraded_dependencies.append("database")
    if not analytics_service_ready:
        degraded_dependencies.append("analytics_service")
    if not realtime_telemetry_ready:
        degraded_dependencies.append("redis_telemetry")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "analytics_runtime_ready": analytics_runtime_ready,
        "analytics_db_ready": analytics_db_ready,
        "analytics_service_ready": analytics_service_ready,
        "realtime_telemetry_ready": realtime_telemetry_ready,
        "redis_url_configured": bool(_REDIS_URL),
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Analytics summary, timeseries, and ROI queries require "
                "database-backed mesh, node, invoice, and listing state."
            ),
            "analytics_service": (
                "MaaSAnalyticsService performs the DB aggregation and cost/health "
                "calculation used by all analytics routes."
            ),
            "redis_telemetry": (
                "Redis adds real-time traffic and latency telemetry; DB-only "
                "analytics still works without it but is degraded."
            ),
        },
        "claim_boundary": (
            "Analytics readiness distinguishes route availability from database "
            "aggregation and real-time Redis telemetry. It does not prove that "
            "any particular mesh has fresh samples, paid invoices, or marketplace "
            "listings."
        ),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/readiness")
async def analytics_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _analytics_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/{mesh_id}/summary", response_model=AnalyticsSummary)
async def get_mesh_analytics(
    mesh_id: str,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    service = MaaSAnalyticsService(db, _redis_client)
    result = service.get_mesh_summary(mesh_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Mesh not found")
    return AnalyticsSummary(**result)


@router.get("/{mesh_id}/timeseries")
async def get_mesh_timeseries(
    mesh_id: str,
    time_range: str = "24h",
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    service = MaaSAnalyticsService(db, _redis_client)
    result = service.get_mesh_timeseries(mesh_id, current_user.id, time_range)
    if not result:
        raise HTTPException(status_code=404, detail="Mesh not found")
    return result


@router.get("/{mesh_id}/marketplace-roi")
async def get_marketplace_roi(
    mesh_id: str,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    service = MaaSAnalyticsService(db, _redis_client)
    return service.get_marketplace_roi(mesh_id, current_user.id)
