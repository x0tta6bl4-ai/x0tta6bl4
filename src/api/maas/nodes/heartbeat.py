"""
MaaS Node Heartbeat - status updates and telemetry collection.
"""

import hashlib
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import MarketplaceEscrow, MarketplaceListing, MeshNode
from src.coordination.events import EventType, get_event_bus
from src.services.marketplace_events import publish_marketplace_escrow_event

logger = logging.getLogger(__name__)

_TELEMETRY_SOURCE_AGENT = "maas-telemetry"
_HEARTBEAT_ESCROW_SOURCE_AGENT = "maas-nodes-heartbeat"
_HEARTBEAT_TELEMETRY_EVENT_ID_LIMIT = 10
_HEARTBEAT_OBSERVED_LAYER = "api_mesh_to_commerce"

try:
    from src.api.maas_telemetry import _set_telemetry as _set_external_telemetry
except Exception:
    _set_external_telemetry = None


class HeartbeatRequest(BaseModel):
    status: str = Field(default="healthy", pattern="^(healthy|degraded|unhealthy)$")
    cpu_percent: Optional[float] = None
    mem_percent: Optional[float] = None
    latency_ms: Optional[float] = None
    traffic_mbps: Optional[float] = None
    active_connections: Optional[int] = None
    dataplane_probe_target: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern=r"^[A-Za-z0-9_.:%-]+$",
    )
    custom_metrics: Optional[Dict[str, Any]] = None


def _normalize_dataplane_probe_target(value: Any) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _build_analytics_telemetry_payload(
    mesh_id: str,
    node_id: str,
    req: HeartbeatRequest,
    timestamp_iso: str,
) -> Dict[str, Any]:
    custom_metrics = req.custom_metrics or {}
    latency = _to_optional_float(
        req.latency_ms
        if req.latency_ms is not None
        else custom_metrics.get("latency_ms")
    )
    traffic = _to_optional_float(
        req.traffic_mbps
        if req.traffic_mbps is not None
        else custom_metrics.get("traffic_mbps")
    )

    payload: Dict[str, Any] = {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "status": req.status,
        "timestamp": timestamp_iso,
        "last_seen": timestamp_iso,
        "cpu_percent": req.cpu_percent,
        "mem_percent": req.mem_percent,
        "active_connections": req.active_connections,
        "custom_metrics": custom_metrics,
    }
    if latency is not None and latency >= 0:
        payload["latency_ms"] = latency
    if traffic is not None and traffic >= 0:
        payload["traffic_mbps"] = traffic
    return payload


def _export_analytics_telemetry(
    node_id: str,
    payload: Dict[str, Any],
    request: Optional[Request] = None,
) -> bool:
    exporter = _set_external_telemetry
    api_package = sys.modules.get("src.api")
    package_module = getattr(api_package, "maas_nodes", None) if api_package else None
    compat_module = sys.modules.get("src.api.maas_nodes")
    legacy_module = sys.modules.get("src.api.maas_nodes_legacy")
    for module in (package_module, compat_module, legacy_module):
        if module is None or not hasattr(module, "_set_external_telemetry"):
            continue
        candidate = getattr(module, "_set_external_telemetry")
        if candidate is not _set_external_telemetry:
            exporter = candidate
            break
        exporter = candidate

    if exporter is None:
        return False
    try:
        state = getattr(request, "state", None) if request else None
        event_bus = getattr(state, "event_bus", None) if state else None
        project_root = getattr(state, "event_project_root", ".") if state else "."

        telemetry_kwargs = {}
        if event_bus:
            telemetry_kwargs["event_bus"] = event_bus
        if project_root:
            telemetry_kwargs["event_project_root"] = project_root

        mesh_id = payload.get("mesh_id")
        if mesh_id is not None:
            telemetry_kwargs["mesh_id"] = mesh_id

        try:
            if telemetry_kwargs:
                exporter(node_id, payload, **telemetry_kwargs)
            else:
                exporter(node_id, payload)
        except TypeError:
            exporter(node_id, payload)
        return True
    except Exception as exc:
        logger.warning("Failed to export node telemetry for analytics (node=%s): %s", node_id, exc)
        return False


def _latest_heartbeat_telemetry_event_ids(
    event_bus: Any,
    *,
    node_id: Any,
    mesh_id: Any,
) -> List[str]:
    if event_bus is None or not hasattr(event_bus, "get_event_history"):
        return []

    node_hash = _redacted_sha256_prefix(node_id)
    mesh_hash = _redacted_sha256_prefix(mesh_id)
    try:
        events = event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=_TELEMETRY_SOURCE_AGENT,
            limit=1000,
        )
    except Exception:
        return []

    event_ids = []
    for event in events:
        data = event.data if isinstance(event.data, dict) else {}
        if data.get("operation") != "telemetry_snapshot_write":
            continue
        if node_hash is not None and data.get("node_id_hash") != node_hash:
            continue
        if mesh_hash is not None and data.get("mesh_id_hash") != mesh_hash:
            continue
        event_ids.append(event.event_id)
    return event_ids[-_HEARTBEAT_TELEMETRY_EVENT_ID_LIMIT:]


def _heartbeat_request_summary(req: HeartbeatRequest) -> Dict[str, Any]:
    custom_metrics = req.custom_metrics if isinstance(req.custom_metrics, dict) else {}
    dataplane_probe_target = _normalize_dataplane_probe_target(
        req.dataplane_probe_target
    )
    return {
        "requested_status": req.status,
        "cpu_percent_present": req.cpu_percent is not None,
        "mem_percent_present": req.mem_percent is not None,
        "latency_ms_present": req.latency_ms is not None,
        "traffic_mbps_present": req.traffic_mbps is not None,
        "active_connections_present": req.active_connections is not None,
        "dataplane_probe_target_present": dataplane_probe_target is not None,
        "dataplane_probe_target_sha256_prefix": _redacted_sha256_prefix(
            dataplane_probe_target
        ),
        "custom_metrics_count": len(custom_metrics),
        "custom_metrics_numeric_count": sum(
            1
            for value in custom_metrics.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ),
        "raw_metric_values_redacted": True,
    }


def _publish_node_heartbeat_evidence(
    event_bus: Any,
    *,
    stage: str,
    status: str,
    mesh_id: Any,
    node_id: Any,
    req: HeartbeatRequest,
    db_node_found: bool,
    node_approved: bool,
    db_committed: bool,
    status_before: Any = None,
    status_after: Any = None,
    telemetry_exported: bool = False,
    telemetry_event_ids: Optional[List[str]] = None,
    escrow_release_attempted: bool = False,
    escrow_released: bool = False,
    marketplace_event_id: Optional[str] = None,
    settlement_evidence: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
    read_only: bool = False,
    reason: str = "",
) -> Optional[str]:
    if event_bus is None:
        return None

    settlement_evidence = settlement_evidence or {}
    telemetry_event_ids = list(telemetry_event_ids or [])[
        -_HEARTBEAT_TELEMETRY_EVENT_ID_LIMIT:
    ]
    upstream_event_ids = list(telemetry_event_ids)
    if marketplace_event_id:
        upstream_event_ids.append(marketplace_event_id)

    payload = {
        "component": "api.maas_nodes",
        "operation": "node_heartbeat",
        "stage": stage,
        "service_name": _HEARTBEAT_ESCROW_SOURCE_AGENT,
        "source_alias": _HEARTBEAT_ESCROW_SOURCE_AGENT,
        "layer": _HEARTBEAT_OBSERVED_LAYER,
        "status": status,
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "read_only": bool(read_only),
        "safe_actuator": False,
        "heartbeat_summary": {
            "db_node_found": bool(db_node_found),
            "node_approved": bool(node_approved),
            "db_committed": bool(db_committed),
            "status_before": str(status_before or "")[:40] or None,
            "status_after": str(status_after or "")[:40] or None,
            **_heartbeat_request_summary(req),
        },
        "telemetry_summary": {
            "telemetry_exported": bool(telemetry_exported),
            "source_agents": [_TELEMETRY_SOURCE_AGENT] if telemetry_event_ids else [],
            "event_ids": telemetry_event_ids,
            "events_total": len(telemetry_event_ids),
            "event_ids_limit": _HEARTBEAT_TELEMETRY_EVENT_ID_LIMIT,
            "payloads_redacted": True,
        },
        "settlement_summary": {
            "escrow_release_attempted": bool(escrow_release_attempted),
            "escrow_released": bool(escrow_released),
            "marketplace_event_id": marketplace_event_id,
            "decision_basis": settlement_evidence.get("decision_basis"),
            "source_quality": settlement_evidence.get("source_quality"),
            "dataplane_confirmed": settlement_evidence.get("dataplane_confirmed"),
            "threshold_met": settlement_evidence.get("threshold_met"),
            "payloads_redacted": True,
        },
        "upstream_event_ids": upstream_event_ids[: _HEARTBEAT_TELEMETRY_EVENT_ID_LIMIT + 1],
        "upstream_events_total": len(upstream_event_ids),
        "duration_ms": (
            round(float(duration_ms), 3) if duration_ms is not None else None
        ),
        "reason": reason,
        "claim_boundary": (
            "MaaS DB-backed node heartbeat evidence only. It records local node "
            "lookup, approval gate, status update, DB commit, telemetry export, "
            "and optional marketplace escrow auto-release linkage with hashed "
            "identifiers. It does not prove live dataplane reachability or external "
            "settlement finality."
        ),
    }
    try:
        event = event_bus.publish(EventType.PIPELINE_STAGE_END, _HEARTBEAT_ESCROW_SOURCE_AGENT, payload, priority=7)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish node heartbeat evidence: %s", exc)
        return None


def process_heartbeat(
    mesh_id: str,
    node_id: str,
    req: HeartbeatRequest,
    db: Session,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """Process a node heartbeat, updating DB and exporting telemetry."""
    start_time = time.time()
    
    # 1. Resolve node
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        _publish_node_heartbeat_evidence(
            None, # Fix later
            stage="resolution_failed", status="error", mesh_id=mesh_id, node_id=node_id,
            req=req, db_node_found=False, node_approved=False, db_committed=False,
            reason="Node not found"
        )
        raise HTTPException(status_code=404, detail="Node not found")

    if node.status != "approved":
        raise HTTPException(status_code=403, detail="Node is not approved for heartbeat")

    status_before = node.status
    
    # 2. Update DB status
    node.last_seen = datetime.utcnow()
    dataplane_probe_target = _normalize_dataplane_probe_target(
        req.dataplane_probe_target
    )
    if dataplane_probe_target is not None:
        node.ip_address = dataplane_probe_target
    # If heartbeat is unhealthy, mark node as degraded (don't auto-revoke here)
    if req.status != "healthy":
        node.status = "degraded"
    else:
        node.status = "approved"
    
    status_after = node.status
    db.commit()

    # 3. Export Telemetry
    timestamp_iso = node.last_seen.isoformat()
    telemetry_payload = _build_analytics_telemetry_payload(mesh_id, node_id, req, timestamp_iso)
    telemetry_exported = _export_analytics_telemetry(node_id, telemetry_payload, request)

    # 4. Handle Marketplace Escrow Auto-Release (if applicable)
    released_escrow = None
    if req.status == "healthy":
        listing = (
            db.query(MarketplaceListing)
            .filter(
                MarketplaceListing.node_id == node_id,
                MarketplaceListing.status == "escrow",
            )
            .first()
        )
        if listing:
            escrow = (
                db.query(MarketplaceEscrow)
                .filter(
                    MarketplaceEscrow.listing_id == listing.id,
                    MarketplaceEscrow.status == "held",
                )
                .first()
            )
            if escrow:
                escrow.status = "released"
                escrow.released_at = datetime.utcnow()
                listing.status = "rented"
                released_escrow = escrow.id
                db.commit()
    
    return {
        "status": "ok",
        "node_id": node_id,
        "mesh_id": mesh_id,
        "node_status": node.status,
        "last_seen": timestamp_iso,
        "last_heartbeat": timestamp_iso,
        "escrow_released": released_escrow,
        "telemetry_exported": telemetry_exported,
        "dataplane_probe_target_registered": dataplane_probe_target is not None,
        "dataplane_probe_target_sha256_prefix": _redacted_sha256_prefix(
            dataplane_probe_target
        ),
        "raw_dataplane_probe_target_redacted": dataplane_probe_target is not None,
    }
