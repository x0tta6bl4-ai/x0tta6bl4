"""
MaaS Advanced Analytics (Production) — x0tta6bl4
================================================

DB-backed metrics: node health, cost comparison, and time-series aggregation.
All values are derived from real DB state (MeshNode.last_seen, invoices).
Redis telemetry is used for real-time traffic/latency when available.
"""

import hashlib
import logging
import os
import time
from typing import Any, Dict, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import require_permission
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import User, get_db
from src.services.maas_analytics_service import MaaSAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter( tags=["MaaS Analytics"])

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


_ANALYTICS_SUMMARY_SOURCE_AGENT = "maas-analytics-summary-read"
_ANALYTICS_SUMMARY_LAYER = "api_analytics_summary_observed_state"
_ANALYTICS_TIMESERIES_SOURCE_AGENT = "maas-analytics-timeseries-read"
_ANALYTICS_TIMESERIES_LAYER = "api_analytics_timeseries_observed_state"
_ANALYTICS_ROI_SOURCE_AGENT = "maas-analytics-roi-read"
_ANALYTICS_ROI_LAYER = "api_analytics_roi_observed_state"
_ANALYTICS_CLAIM_BOUNDARY = (
    "MaaS analytics evidence records bounded read-only metadata from "
    "MaaSAnalyticsService DB aggregation and optional Redis telemetry surfaces. "
    "It does not expose raw emails, user IDs, mesh IDs, node IDs, listing IDs, "
    "invoice IDs, API keys, session tokens, or prove live dataplane freshness."
)


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _analytics_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS analytics EventBus: %s", exc)
        return None


def _analytics_actor_summary(user: Any) -> Dict[str, Any]:
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", "") or "")[:40],
        "actor_plan": str(getattr(user, "plan", "") or "")[:40],
    }


def _safe_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _publish_analytics_read_event(
    request: Optional[Request],
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    current_user: Any,
    mesh_id: Any,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    time_range: Optional[str] = None,
    http_status_code: Optional[int] = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _analytics_event_bus_from_request(request)
    if event_bus is None:
        return None

    result_map = result if isinstance(result, dict) else {}
    data_points = result_map.get("data") if isinstance(result_map.get("data"), list) else []
    listings = result_map.get("listings") if isinstance(result_map.get("listings"), dict) else {}
    revenue = result_map.get("revenue") if isinstance(result_map.get("revenue"), dict) else {}

    payload: Dict[str, Any] = {
        "component": "api.maas_analytics",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_analytics_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "analytics_service_used": True,
        "redis_telemetry_configured": bool(_REDIS_URL),
        "redis_telemetry_ready": _redis_client is not None,
        "result_present": bool(result_map),
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _ANALYTICS_CLAIM_BOUNDARY,
    }

    if source_agent == _ANALYTICS_SUMMARY_SOURCE_AGENT:
        payload.update(
            {
                "nodes_total": _safe_non_negative_int(result_map.get("nodes_total")),
                "nodes_online": _safe_non_negative_int(result_map.get("nodes_online")),
                "pqc_status": bool(result_map.get("pqc_status")),
                "health_score": _safe_float(result_map.get("health_score")),
                "cost_maas_total": _safe_float(result_map.get("cost_maas_total")),
                "cost_aws_estimate": _safe_float(result_map.get("cost_aws_estimate")),
                "savings_pct": _safe_float(result_map.get("savings_pct")),
            }
        )
    elif source_agent == _ANALYTICS_TIMESERIES_SOURCE_AGENT:
        payload.update(
            {
                "time_range": str(time_range or result_map.get("range") or "")[:20],
                "points_count": len(data_points),
                "nodes_total": _safe_non_negative_int(result_map.get("nodes_total")),
                "telemetry_points_bounded": True,
            }
        )
    elif source_agent == _ANALYTICS_ROI_SOURCE_AGENT:
        payload.update(
            {
                "listings_total": _safe_non_negative_int(listings.get("total")),
                "listings_available": _safe_non_negative_int(listings.get("available")),
                "listings_rented": _safe_non_negative_int(listings.get("rented")),
                "listings_in_escrow": _safe_non_negative_int(listings.get("in_escrow")),
                "hourly_revenue_cents": _safe_non_negative_int(
                    revenue.get("hourly_cents")
                ),
                "hourly_revenue_usd": _safe_float(revenue.get("hourly_usd")),
                "monthly_estimate_usd": _safe_float(
                    revenue.get("monthly_estimate_usd")
                ),
                "economy_projection": True,
            }
        )

    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            source_agent,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS analytics read event: %s", exc)
        return None


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
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_analytics_readiness"
        ),
        "claim_boundary": (
            "Analytics readiness distinguishes route availability from database "
            "aggregation and real-time Redis telemetry. It does not prove that "
            "any particular mesh has fresh samples, paid invoices, or marketplace "
            "listings."
        ),
    }


@router.get("/readiness")
async def analytics_readiness(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    payload = _analytics_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/{mesh_id}/summary", response_model=AnalyticsSummary)
async def get_mesh_analytics(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
) -> AnalyticsSummary:
    started = time.monotonic()
    service = MaaSAnalyticsService(db, _redis_client)
    try:
        result = service.get_mesh_summary(mesh_id, current_user.id)
    except Exception as exc:
        _publish_analytics_read_event(
            request,
            source_agent=_ANALYTICS_SUMMARY_SOURCE_AGENT,
            layer=_ANALYTICS_SUMMARY_LAYER,
            stage="analytics_summary_read",
            operation="maas_analytics_summary_read",
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            result=None,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    if not result:
        _publish_analytics_read_event(
            request,
            source_agent=_ANALYTICS_SUMMARY_SOURCE_AGENT,
            layer=_ANALYTICS_SUMMARY_LAYER,
            stage="analytics_summary_read",
            operation="maas_analytics_summary_read",
            current_user=current_user,
            mesh_id=mesh_id,
            status="denied",
            result=None,
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="mesh_not_found",
        )
        raise HTTPException(status_code=404, detail="Mesh not found")
    _publish_analytics_read_event(
        request,
        source_agent=_ANALYTICS_SUMMARY_SOURCE_AGENT,
        layer=_ANALYTICS_SUMMARY_LAYER,
        stage="analytics_summary_read",
        operation="maas_analytics_summary_read",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        result=result,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="summary_read",
    )
    return AnalyticsSummary(**result)


@router.get("/{mesh_id}/timeseries")
async def get_mesh_timeseries(
    mesh_id: str,
    request: Request,
    time_range: str = "24h",
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    started = time.monotonic()
    service = MaaSAnalyticsService(db, _redis_client)
    try:
        result = service.get_mesh_timeseries(mesh_id, current_user.id, time_range)
    except Exception as exc:
        _publish_analytics_read_event(
            request,
            source_agent=_ANALYTICS_TIMESERIES_SOURCE_AGENT,
            layer=_ANALYTICS_TIMESERIES_LAYER,
            stage="analytics_timeseries_read",
            operation="maas_analytics_timeseries_read",
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            result=None,
            time_range=time_range,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    if not result:
        _publish_analytics_read_event(
            request,
            source_agent=_ANALYTICS_TIMESERIES_SOURCE_AGENT,
            layer=_ANALYTICS_TIMESERIES_LAYER,
            stage="analytics_timeseries_read",
            operation="maas_analytics_timeseries_read",
            current_user=current_user,
            mesh_id=mesh_id,
            status="denied",
            result=None,
            time_range=time_range,
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="mesh_not_found",
        )
        raise HTTPException(status_code=404, detail="Mesh not found")
    _publish_analytics_read_event(
        request,
        source_agent=_ANALYTICS_TIMESERIES_SOURCE_AGENT,
        layer=_ANALYTICS_TIMESERIES_LAYER,
        stage="analytics_timeseries_read",
        operation="maas_analytics_timeseries_read",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        result=result,
        time_range=time_range,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="timeseries_read",
    )
    return result


@router.get("/{mesh_id}/marketplace-roi")
async def get_marketplace_roi(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    started = time.monotonic()
    service = MaaSAnalyticsService(db, _redis_client)
    try:
        result = service.get_marketplace_roi(mesh_id, current_user.id)
    except Exception as exc:
        _publish_analytics_read_event(
            request,
            source_agent=_ANALYTICS_ROI_SOURCE_AGENT,
            layer=_ANALYTICS_ROI_LAYER,
            stage="analytics_roi_read",
            operation="maas_analytics_roi_read",
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            result=None,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    _publish_analytics_read_event(
        request,
        source_agent=_ANALYTICS_ROI_SOURCE_AGENT,
        layer=_ANALYTICS_ROI_LAYER,
        stage="analytics_roi_read",
        operation="maas_analytics_roi_read",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        result=result,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="marketplace_roi_read",
    )
    return result
