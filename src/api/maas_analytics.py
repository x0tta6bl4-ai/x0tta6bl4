"""
MaaS Advanced Analytics (Production) — x0tta6bl4
================================================

DB-backed metrics: node health, cost comparison, and time-series aggregation.
All values are derived from real DB state (MeshNode.last_seen, invoices).
Redis telemetry is used for real-time traffic/latency when available.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import User, get_db
from src.services.maas_analytics_service import MaaSAnalyticsService
from src.api.maas_auth import require_permission

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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
