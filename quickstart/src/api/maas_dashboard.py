"""
MaaS Dashboard (Production) — x0tta6bl4
========================================

Aggregated summary for the management dashboard.
Uses DB-backed data for all statistics including hardware attestation.
"""
from __future__ import annotations

import hashlib
import logging
import time
import importlib
from datetime import datetime, timedelta
from typing import Any, Dict

from src.coordination.events import EventBus, EventType, get_event_bus

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import AuditLog, Invoice, MeshInstance, MeshNode, User, MarketplaceListing, get_db
from src.api.maas_auth import require_permission
from src.services.maas_analytics_service import MaaSAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/dashboard", tags=["MaaS Dashboard"])

_STALE_THRESHOLD_MINUTES = 5
_DASHBOARD_SUMMARY_SOURCE_AGENT = "maas-dashboard-summary-read"
_DASHBOARD_SUMMARY_LAYER = "api_dashboard_summary_observed_state"
_DASHBOARD_ANALYTICS_SOURCE_AGENT = "maas-dashboard-analytics-read"
_DASHBOARD_ANALYTICS_LAYER = "api_dashboard_analytics_observed_state"
_DASHBOARD_NODES_SOURCE_AGENT = "maas-dashboard-node-read"
_DASHBOARD_NODES_LAYER = "api_dashboard_node_observed_state"
_DASHBOARD_CLAIM_BOUNDARY = (
    "MaaS dashboard evidence records bounded read-only metadata from local DB, "
    "analytics-service, and resilience surfaces only. It does not expose raw "
    "emails, mesh IDs, node IDs, hardware IDs, invoice IDs, audit details, or "
    "prove live dataplane state."
)


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _dashboard_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize MaaS dashboard EventBus: %s", exc)
        return None


def _dashboard_actor_summary(user: Any) -> Dict[str, Any]:
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", ""))[:40],
        "actor_plan": str(getattr(user, "plan", ""))[:40],
    }


def _known_count_map(values: list[str], known_values: tuple[str, ...]) -> Dict[str, int]:
    counts = {name: 0 for name in known_values}
    counts["other"] = 0
    for value in values:
        key = str(value or "").strip()
        if key in counts and key != "other":
            counts[key] += 1
        else:
            counts["other"] += 1
    return counts


def _publish_dashboard_summary_event(
    request: Request | None,
    *,
    current_user: Any,
    meshes_count: int = 0,
    total_nodes: int = 0,
    active_rentals_count: int = 0,
    my_listings_count: int = 0,
    audit_logs_count: int = 0,
    pending_invoices_count: int = 0,
    timeseries_points: int = 0,
    security_stats: Dict[str, int] | None = None,
    health_stats: Dict[str, int] | None = None,
    cache_backend: str = "",
    db_circuit_open: bool | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _dashboard_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_dashboard",
        "stage": "dashboard_summary_read",
        "operation": "maas_dashboard_summary_read",
        "service_name": _DASHBOARD_SUMMARY_SOURCE_AGENT,
        "source_alias": _DASHBOARD_SUMMARY_SOURCE_AGENT,
        "layer": _DASHBOARD_SUMMARY_LAYER,
        "status": "success",
        "duration_ms": round(duration_ms, 3),
        **_dashboard_actor_summary(current_user),
        "meshes_count": max(0, int(meshes_count)),
        "total_nodes": max(0, int(total_nodes)),
        "active_rentals_count": max(0, int(active_rentals_count)),
        "my_listings_count": max(0, int(my_listings_count)),
        "audit_logs_count": max(0, int(audit_logs_count)),
        "pending_invoices_count": max(0, int(pending_invoices_count)),
        "timeseries_points": max(0, int(timeseries_points)),
        "security_stats": dict(security_stats or {}),
        "health_stats": dict(health_stats or {}),
        "analytics_service_used": True,
        "cache_backend": cache_backend if cache_backend in {"memory", "redis"} else "unknown",
        "db_circuit_open": db_circuit_open,
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _DASHBOARD_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _DASHBOARD_SUMMARY_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS dashboard summary event: %s", exc)
        return None


def _publish_dashboard_analytics_event(
    request: Request | None,
    *,
    current_user: Any,
    mesh_id: Any,
    status: str,
    result: Dict[str, Any] | None = None,
    time_range: str = "24h",
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _dashboard_event_bus_from_request(request)
    if event_bus is None:
        return None

    data = (result or {}).get("data") or []
    payload = {
        "component": "api.maas_dashboard",
        "stage": "dashboard_analytics_read",
        "operation": "maas_dashboard_analytics_read",
        "service_name": _DASHBOARD_ANALYTICS_SOURCE_AGENT,
        "source_alias": _DASHBOARD_ANALYTICS_SOURCE_AGENT,
        "layer": _DASHBOARD_ANALYTICS_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        **_dashboard_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "time_range": str(time_range or "")[:20],
        "analytics_service_used": True,
        "result_present": bool(result),
        "points_count": len(data) if isinstance(data, list) else 0,
        "nodes_total": max(0, int((result or {}).get("nodes_total") or 0)),
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _DASHBOARD_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _DASHBOARD_ANALYTICS_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS dashboard analytics event: %s", exc)
        return None


def _publish_dashboard_nodes_event(
    request: Request | None,
    *,
    current_user: Any,
    mesh_id: Any,
    status: str,
    mesh_found: bool = False,
    nodes: list[Any] | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _dashboard_event_bus_from_request(request)
    if event_bus is None:
        return None

    node_list = list(nodes or [])
    attestations = [_node_attestation_type(node) for node in node_list]
    health_values = [_node_health(node) for node in node_list]
    device_classes = [str(getattr(node, "device_class", "") or "")[:40] for node in node_list]
    payload = {
        "component": "api.maas_dashboard",
        "stage": "dashboard_nodes_read",
        "operation": "maas_dashboard_nodes_read",
        "service_name": _DASHBOARD_NODES_SOURCE_AGENT,
        "source_alias": _DASHBOARD_NODES_SOURCE_AGENT,
        "layer": _DASHBOARD_NODES_LAYER,
        "status": status,
        "duration_ms": round(duration_ms, 3),
        **_dashboard_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "mesh_found": mesh_found,
        "nodes_count": len(node_list),
        "attestation_counts": _known_count_map(
            attestations,
            ("HARDWARE_ROOTED", "SOFTWARE_ONLY"),
        ),
        "health_counts": _known_count_map(
            health_values,
            ("healthy", "stale", "offline", "unknown"),
        ),
        "device_class_counts": _known_count_map(
            device_classes,
            ("gateway", "edge", "sensor", "mobile", "server"),
        ),
        "hardware_id_present_count": sum(
            1 for node in node_list if bool(getattr(node, "hardware_id", None))
        ),
        "enclave_enabled_count": sum(
            1 for node in node_list if bool(getattr(node, "enclave_enabled", None))
        ),
        "http_status_code": http_status_code,
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "control_action": False,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _DASHBOARD_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _DASHBOARD_NODES_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS dashboard nodes event: %s", exc)
        return None


def _node_attestation_type(node: MeshNode) -> str:
    """
    Determine attestation level from stored node metadata.

    HARDWARE_ROOTED — node has a registered hardware_id (TPM/HSM) AND
                      enclave_enabled is set in the DB.
    SOFTWARE_ONLY   — all other nodes.
    """
    if node.hardware_id and node.enclave_enabled:
        return "HARDWARE_ROOTED"
    return "SOFTWARE_ONLY"


def _node_health(node: MeshNode) -> str:
    """
    Return 'healthy', 'stale', or 'offline' based on last_seen timestamp.
    A node without last_seen is treated as 'unknown'.
    """
    if node.last_seen is None:
        return "unknown"
    age = datetime.utcnow() - node.last_seen
    age_seconds = max(0, int(age.total_seconds()))
    if age_seconds <= _STALE_THRESHOLD_MINUTES * 60:
        return "healthy"
    if age_seconds <= 30 * 60:
        return "stale"
    return "offline"


def _safe_non_negative_float(value) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed >= 0 else 0.0


def _dashboard_db_session_available(db: Any) -> bool:
    return hasattr(db, "query")


def _dashboard_models_available() -> bool:
    required_model_attrs = (
        (MeshInstance, ("id", "owner_id", "name", "status", "created_at")),
        (
            MeshNode,
            (
                "id",
                "mesh_id",
                "status",
                "device_class",
                "last_seen",
                "hardware_id",
                "enclave_enabled",
            ),
        ),
        (MarketplaceListing, ("renter_id", "owner_id", "status")),
        (AuditLog, ("id", "user_id", "action", "method", "path", "status_code", "created_at")),
        (Invoice, ("id", "user_id", "status", "total_amount", "currency", "issued_at")),
        (User, ("id", "email", "plan", "role")),
    )
    return all(
        hasattr(model, attr)
        for model, attrs in required_model_attrs
        for attr in attrs
    )


def _dashboard_auth_dependency_available() -> bool:
    return callable(require_permission)


def _dashboard_analytics_service_available() -> bool:
    return callable(MaaSAnalyticsService) and callable(
        getattr(MaaSAnalyticsService, "get_mesh_timeseries", None)
    )


def _dashboard_resilience_imports_available() -> bool:
    try:
        database_module = importlib.import_module("src.database")
        cache_module = importlib.import_module("src.core.cache")
        resilience_module = importlib.import_module("src.resilience.advanced_patterns")
    except Exception:
        return False
    return (
        hasattr(database_module, "db_circuit_breaker")
        and callable(getattr(cache_module, "get_cache", None))
        and hasattr(resilience_module, "CircuitState")
    )


def _dashboard_readiness_status(db: Any) -> Dict[str, Any]:
    dashboard_db_ready = _dashboard_db_session_available(db)
    dashboard_models_ready = _dashboard_models_available()
    dashboard_auth_ready = _dashboard_auth_dependency_available()
    dashboard_analytics_ready = _dashboard_analytics_service_available()
    dashboard_resilience_ready = _dashboard_resilience_imports_available()
    dashboard_runtime_ready = (
        dashboard_db_ready
        and dashboard_models_ready
        and dashboard_auth_ready
        and dashboard_analytics_ready
        and dashboard_resilience_ready
    )

    degraded_dependencies = []
    if not dashboard_db_ready:
        degraded_dependencies.append("database")
    if not dashboard_models_ready:
        degraded_dependencies.append("dashboard_models")
    if not dashboard_auth_ready:
        degraded_dependencies.append("auth")
    if not dashboard_analytics_ready:
        degraded_dependencies.append("analytics_service")
    if not dashboard_resilience_ready:
        degraded_dependencies.append("resilience_imports")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "dashboard_runtime_ready": dashboard_runtime_ready,
        "dashboard_db_ready": dashboard_db_ready,
        "dashboard_models_ready": dashboard_models_ready,
        "dashboard_auth_ready": dashboard_auth_ready,
        "dashboard_analytics_ready": dashboard_analytics_ready,
        "dashboard_resilience_ready": dashboard_resilience_ready,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/api/v1/maas/dashboard",
            "boundary": (
                "Dashboard routes use the fixed /api/v1/maas/dashboard prefix. "
                "The legacy MaaS router is registered earlier, but its dynamic "
                "mesh routes do not match /dashboard/summary, "
                "/dashboard/analytics/{mesh_id}/timeseries, or "
                "/dashboard/nodes/{mesh_id}."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Summary and node views read meshes, nodes, marketplace listings, "
                "audit logs, invoices, and user state through SQLAlchemy query."
            ),
            "dashboard_models": (
                "Dashboard responses depend on MeshInstance, MeshNode, "
                "MarketplaceListing, AuditLog, Invoice, and User columns."
            ),
            "auth": (
                "Summary and node routes require mesh:view; analytics timeseries "
                "requires analytics:view."
            ),
            "analytics_service": (
                "Traffic charts use MaaSAnalyticsService.get_mesh_timeseries."
            ),
            "resilience_imports": (
                "Summary resilience status imports db_circuit_breaker, get_cache, "
                "and CircuitState lazily at request time."
            ),
        },
        "claim_boundary": (
            "Dashboard readiness proves route availability and local dependency "
            "surfaces only. It does not query dashboard data, validate user "
            "permissions for a real principal, call Redis, or prove chart data is "
            "fresh."
        ),
    }


@router.get("/readiness")
async def dashboard_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _dashboard_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


def _dashboard_traffic_by_bucket(
    db: Session,
    mesh_ids: list[str],
    owner_id: str,
    *,
    buckets: int = 24,
) -> list[float]:
    """
    Build dashboard traffic series from the production analytics service.

    The service uses Redis heartbeat telemetry when available and falls back to
    DB-backed marketplace bandwidth, so the dashboard does not hard-code chart
    traffic to zero.
    """
    totals = [0.0 for _ in range(buckets)]
    if not mesh_ids:
        return totals

    service = MaaSAnalyticsService(db, None)
    for mesh_id in mesh_ids:
        try:
            result = service.get_mesh_timeseries(mesh_id, owner_id, "24h")
        except Exception as exc:
            logger.warning("Failed to load dashboard traffic for mesh %s: %s", mesh_id, exc)
            continue
        data = (result or {}).get("data") or []
        recent = data[-buckets:]
        start_index = buckets - len(recent)
        for offset, point in enumerate(recent):
            if isinstance(point, dict):
                totals[start_index + offset] += _safe_non_negative_float(
                    point.get("traffic_mbps")
                )
    return [round(value, 1) for value in totals]


@router.get("/summary")
async def get_dashboard_summary(
    request: Request,
    current_user: User = Depends(require_permission("mesh:view")),
    db: Session = Depends(get_db),
):
    """
    Aggregated summary for the MaaS Dashboard.
    Returns meshes, node attestation stats, recent audit logs, and billing status.
    """
    started = time.monotonic()
    # 1. Meshes owned by this user
    meshes = db.query(MeshInstance).filter(MeshInstance.owner_id == current_user.id).all()
    mesh_ids = [m.id for m in meshes]

    # 2. Node stats across all meshes (DB-backed)
    security_stats: Dict[str, int] = {"HARDWARE_ROOTED": 0, "SOFTWARE_ONLY": 0}
    health_stats: Dict[str, int] = {"healthy": 0, "stale": 0, "offline": 0, "unknown": 0}
    total_nodes = 0

    if mesh_ids:
        nodes = (
            db.query(MeshNode)
            .filter(MeshNode.mesh_id.in_(mesh_ids), MeshNode.status != "revoked")
            .all()
        )
        for node in nodes:
            total_nodes += 1
            att = _node_attestation_type(node)
            security_stats[att] = security_stats.get(att, 0) + 1
            health = _node_health(node)
            health_stats[health] = health_stats.get(health, 0) + 1

    # 3. Marketplace Activity
    active_rentals = db.query(MarketplaceListing).filter(
        MarketplaceListing.renter_id == current_user.id,
        MarketplaceListing.status == "rented"
    ).all()
    my_listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.owner_id == current_user.id
    ).all()

    # 4. Recent audit logs (last 20)
    query = db.query(AuditLog)
    if current_user.role != "admin":
        query = query.filter(AuditLog.user_id == current_user.id)
    recent_logs = query.order_by(AuditLog.created_at.desc()).limit(20).all()
    log_list = [
        {
            "id": log.id,
            "action": log.action,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "created_at": log.created_at,
        }
        for log in recent_logs
    ]

    # 5. Pending invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id, Invoice.status == "issued")
        .all()
    )

    # 6. Real Metrics for Charts
    now = datetime.utcnow()
    timeseries = []
    traffic_by_bucket = _dashboard_traffic_by_bucket(db, mesh_ids, current_user.id)
    
    # Calculate real health percentage over the last 24 hours in 1-hour buckets
    for i in range(24):
        bucket_end = now - timedelta(hours=23-i)
        bucket_start = bucket_end - timedelta(hours=1)
        
        if total_nodes > 0:
            # Count nodes that were seen at least once within or after this bucket
            # (Simplification: a node is 'healthy' for the bucket if its last_seen is within threshold of bucket_end)
            healthy_in_bucket = db.query(MeshNode).filter(
                MeshNode.mesh_id.in_(mesh_ids),
                MeshNode.status == "healthy",
                MeshNode.last_seen >= (bucket_end - timedelta(minutes=_STALE_THRESHOLD_MINUTES))
            ).count()
            health_pct = (healthy_in_bucket / total_nodes) * 100
        else:
            health_pct = 0
            
        timeseries.append({
            "timestamp": bucket_end.isoformat(),
            "health": round(health_pct, 2),
            "traffic_mbps": traffic_by_bucket[i],
        })

    # 7. Resilience Status (P2 Observability)
    from src.database import db_circuit_breaker
    from src.core.cache import get_cache
    from src.resilience.advanced_patterns import CircuitState
    
    cache_obj = get_cache()
    resilience_status = {
        "db_circuit_breaker": {
            "state": db_circuit_breaker.state.value,
            "is_open": db_circuit_breaker.state == CircuitState.OPEN
        },
        "cache": {
            "backend": "memory" if getattr(cache_obj, "_using_fallback", False) else "redis"
        }
    }

    payload = {
        "user": {
            "email": current_user.email,
            "plan": current_user.plan,
            "role": current_user.role,
        },
        "resilience": resilience_status,
        "stats": {
            "total_meshes": len(meshes),
            "total_nodes": total_nodes,
            "active_rentals": len(active_rentals),
            "my_listings": len(my_listings),
            "pending_payment": len(invoices) > 0,
            "security": security_stats,
            "node_health": health_stats,
        },
        "meshes": [
            {"id": m.id, "name": m.name, "status": m.status, "created_at": m.created_at} 
            for m in meshes
        ],
        "recent_audit": log_list,
        "pending_invoices": [
            {"id": i.id, "amount": i.total_amount / 100.0, "currency": i.currency, "issued_at": i.issued_at}
            for i in invoices
        ],
        "timeseries": timeseries,
    }
    _publish_dashboard_summary_event(
        request,
        current_user=current_user,
        meshes_count=len(meshes),
        total_nodes=total_nodes,
        active_rentals_count=len(active_rentals),
        my_listings_count=len(my_listings),
        audit_logs_count=len(recent_logs),
        pending_invoices_count=len(invoices),
        timeseries_points=len(timeseries),
        security_stats=security_stats,
        health_stats=health_stats,
        cache_backend=resilience_status["cache"]["backend"],
        db_circuit_open=resilience_status["db_circuit_breaker"]["is_open"],
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="summary_read",
    )
    return payload


@router.get("/analytics/{mesh_id}/timeseries")
async def get_mesh_analytics(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    """DB-backed dashboard analytics for a specific mesh."""
    started = time.monotonic()
    service = MaaSAnalyticsService(db, None)
    try:
        result = service.get_mesh_timeseries(mesh_id, current_user.id, "24h")
    except Exception as exc:
        _publish_dashboard_analytics_event(
            request,
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            result=None,
            time_range="24h",
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
        )
        raise
    if not result:
        _publish_dashboard_analytics_event(
            request,
            current_user=current_user,
            mesh_id=mesh_id,
            status="denied",
            result=None,
            time_range="24h",
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="mesh_not_found",
        )
        raise HTTPException(status_code=404, detail="Mesh not found")
    _publish_dashboard_analytics_event(
        request,
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        result=result,
        time_range=str(result.get("range") or "24h"),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="timeseries_read",
    )
    return result


@router.get("/nodes/{mesh_id}")
async def get_mesh_nodes_summary(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_permission("mesh:view")),
    db: Session = Depends(get_db),
):
    """Per-mesh node listing with attestation and health details."""
    started = time.monotonic()
    mesh = db.query(MeshInstance).filter(
        MeshInstance.id == mesh_id,
        MeshInstance.owner_id == current_user.id,
    ).first()
    if not mesh:
        _publish_dashboard_nodes_event(
            request,
            current_user=current_user,
            mesh_id=mesh_id,
            status="denied",
            mesh_found=False,
            nodes=[],
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="mesh_not_found",
        )
        raise HTTPException(status_code=404, detail="Mesh not found")

    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    payload = {
        "mesh_id": mesh_id,
        "mesh_name": mesh.name,
        "nodes": [
            {
                "id": node.id,
                "status": node.status,
                "device_class": node.device_class,
                "attestation": _node_attestation_type(node),
                "health": _node_health(node),
                "last_seen": node.last_seen,
                "enclave_enabled": node.enclave_enabled,
                "hardware_id": node.hardware_id,
            }
            for node in nodes
        ],
        "count": len(nodes),
    }
    _publish_dashboard_nodes_event(
        request,
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        mesh_found=True,
        nodes=nodes,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="nodes_read",
    )
    return payload

