"""
MaaS Nodes Endpoints - Node registration and management.

Provides REST API endpoints for node registration, heartbeats, and revocation.
"""

import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth import UserContext, get_current_user, require_mesh_access
from ..models import NodeHeartbeatRequest, NodeRegisterRequest, NodeRegisterResponse
from ..registry import (
    add_pending_node,
    get_mesh,
    get_node_telemetry,
    get_pending_nodes,
    is_node_revoked,
    update_node_telemetry,
)
from ..services import MeshProvisioner
from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

router = APIRouter( tags=["nodes"])

_MODULAR_NODE_REGISTRATION_SOURCE_AGENT = "maas-modular-node-registration"
_MODULAR_NODE_HEARTBEAT_SOURCE_AGENT = "maas-modular-node-heartbeat"
_MODULAR_NODE_READ_SOURCE_AGENT = "maas-modular-node-read"
_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT = "maas-modular-node-lifecycle"
_MODULAR_NODE_REGISTRATION_LAYER = "api_modular_node_registration_control_action"
_MODULAR_NODE_HEARTBEAT_LAYER = "api_modular_node_heartbeat_observed_state"
_MODULAR_NODE_READ_LAYER = "api_modular_node_observed_state"
_MODULAR_NODE_LIFECYCLE_LAYER = "api_modular_node_lifecycle_control_action"
_MODULAR_NODE_CLAIM_BOUNDARY = (
    "Modular MaaS node endpoint evidence only. It records local request "
    "validation, mesh access checks, registry/provisioner calls, telemetry "
    "store writes/reads, external telemetry export status, and bounded output "
    "shape; it does not prove live dataplane reachability, node identity "
    "attestation, SPIFFE authentication, credential installation, or that a "
    "node executed an approved/reissued credential."
)

try:
    from src.api.maas_telemetry import _set_telemetry as _set_external_telemetry
except Exception:
    _set_external_telemetry = None


# Service instance
_provisioner: Optional[MeshProvisioner] = None


def _node_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize modular MaaS node EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _safe_count(value: Any, *, max_value: int = 1_000_000) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return min(int(value), max_value)
    return None


def _safe_float(value: Any, *, max_value: float = 1_000_000_000.0) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return round(min(float(value), max_value), 3)
    return None


def _device_class_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"edge", "robot", "drone", "gateway", "sensor", "server"} else "other"


def _node_status_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {
        "approved",
        "denied",
        "failed",
        "not_found",
        "ok",
        "pending",
        "revoked",
        "success",
        "telemetry_missing",
        "validation_failed",
    }:
        return text
    return "unknown" if not text else "other"


def _capability_summary(values: Any) -> Dict[str, Any]:
    if not isinstance(values, list):
        return {"count": 0, "known": []}
    known = {
        str(value).strip().lower()
        for value in values
        if str(value).strip().lower()
        in {"edge", "routing", "compute", "storage", "gateway", "sensor"}
    }
    return {"count": len(values), "known": sorted(known)}


def _metadata_shape(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"keys_count": 0, "payloads_redacted": True}
    return {"keys_count": len(value), "payloads_redacted": True}


def _node_event_source_quality(operation: str, status_value: str) -> str:
    if operation == "register_node":
        if status_value == "success":
            return "local_pending_node_registration_recorded"
        if status_value == "revoked":
            return "local_revocation_gate_rejected"
        return "local_node_registration_rejected_before_mutation"
    if operation == "node_heartbeat":
        return (
            "local_heartbeat_telemetry_recorded"
            if status_value == "success"
            else "local_heartbeat_telemetry_failed"
        )
    if operation == "list_pending_nodes":
        return (
            "local_pending_node_read"
            if status_value == "success"
            else "local_pending_node_read_failed"
        )
    if operation == "get_telemetry":
        if status_value == "success":
            return "local_node_telemetry_observed_state"
        if status_value == "telemetry_missing":
            return "local_node_telemetry_missing"
        return "local_node_telemetry_read_failed"
    if operation == "approve_node":
        return (
            "local_node_approval_control_action"
            if status_value == "success"
            else "local_node_approval_failed"
        )
    if operation == "revoke_node":
        return (
            "local_node_revocation_control_action"
            if status_value == "success"
            else "local_node_revocation_failed"
        )
    if operation == "request_reissue":
        return (
            "local_reissue_token_created"
            if status_value == "success"
            else "local_reissue_token_failed"
        )
    return "modular_node_local_event"


def _node_lifecycle_evidence(
    *,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    result_summary: Dict[str, Any],
    read_only: bool,
) -> Dict[str, Any]:
    source_quality = _node_event_source_quality(operation, status_value)
    mutation_attempted = stage in {
        "heartbeat_telemetry_update",
        "node_approval",
        "node_revocation",
        "pending_node_mutation",
        "reissue_token_store",
    }
    mutation_committed = bool(
        status_value == "success"
        and operation
        in {
            "approve_node",
            "node_heartbeat",
            "register_node",
            "request_reissue",
            "revoke_node",
        }
    )
    return {
        "decision_basis": source_quality,
        "source_quality": source_quality,
        "stage": stage,
        "operation": operation,
        "duration_ms": round(duration_ms, 3),
        "read_only": read_only,
        "dataplane_confirmed": False,
        "node_identity_attested": False,
        "spiffe_authenticated": False,
        "credential_installation_confirmed": False,
        "registry_mutation": {
            "attempted": mutation_attempted,
            "committed": mutation_committed,
            "payloads_redacted": True,
        },
        "telemetry_store": {
            "attempted": operation in {"node_heartbeat", "get_telemetry"},
            "committed": operation == "node_heartbeat" and status_value == "success",
            "read": operation == "get_telemetry",
            "payloads_redacted": True,
        },
        "output_summary": {
            **result_summary,
            "status": status_value,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _node_result_summary(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "payload_type": type(result).__name__[:40],
            "payload_field_count": None,
        }
    return {
        "payload_type": "dict",
        "payload_field_count": len(result),
        "status": _node_status_bucket(result.get("status")),
        "node_id_present": bool(result.get("node_id")),
        "mesh_id_present": bool(result.get("mesh_id")),
        "token_present": bool(result.get("reissue_token") or result.get("join_token")),
        "telemetry_exported": result.get("telemetry_exported")
        if isinstance(result.get("telemetry_exported"), bool)
        else None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _telemetry_shape_summary(telemetry: Any) -> Dict[str, Any]:
    if not isinstance(telemetry, dict):
        return {
            "payload_type": type(telemetry).__name__[:40],
            "payload_field_count": None,
        }
    custom_metrics = telemetry.get("custom_metrics")
    return {
        "payload_type": "dict",
        "payload_field_count": len(telemetry),
        "mesh_id_present": bool(telemetry.get("mesh_id")),
        "cpu_present": telemetry.get("cpu_percent") is not None
        or telemetry.get("cpu_usage") is not None,
        "memory_present": telemetry.get("memory_percent") is not None
        or telemetry.get("memory_usage") is not None,
        "neighbors_count": _safe_count(telemetry.get("neighbors_count")),
        "routing_table_size": _safe_count(telemetry.get("routing_table_size")),
        "uptime_present": telemetry.get("uptime") is not None,
        "custom_metrics_count": len(custom_metrics) if isinstance(custom_metrics, dict) else None,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _pending_nodes_summary(pending: Any) -> Dict[str, Any]:
    if not isinstance(pending, dict):
        return {
            "payload_type": type(pending).__name__[:40],
            "payload_field_count": None,
            "nodes_count": None,
        }
    device_classes = {
        _device_class_bucket(data.get("device_class"))
        for data in pending.values()
        if isinstance(data, dict) and data.get("device_class")
    }
    return {
        "payload_type": "dict",
        "payload_field_count": len(pending),
        "nodes_count": len(pending),
        "device_class_buckets": sorted(device_classes),
        "metadata_payloads_redacted": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _registration_summary(request: NodeRegisterRequest) -> Dict[str, Any]:
    return {
        "payload_type": "NodeRegisterRequest",
        "mesh_id_present": bool(request.mesh_id),
        "node_id_present": bool(request.node_id),
        "device_class": _device_class_bucket(request.device_class),
        "capabilities": _capability_summary(request.capabilities),
        "labels_count": len(request.labels or {}),
        "metadata": _metadata_shape(request.metadata),
        "public_key_present": bool(request.public_key),
        "pqc_public_key_present": bool((request.public_keys or {}).get("pqc")),
        "hardware_id_present": bool(request.hardware_id),
        "attestation_present": bool(request.attestation_data),
        "enclave_enabled": bool(request.enclave_enabled),
        "enrollment_token_present": bool(request.enrollment_token),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _heartbeat_request_summary(request: NodeHeartbeatRequest) -> Dict[str, Any]:
    return {
        "payload_type": "NodeHeartbeatRequest",
        "mesh_id_present": bool(request.mesh_id),
        "node_id_present": bool(request.node_id),
        "cpu_present": request.cpu_percent is not None or request.cpu_usage is not None,
        "memory_present": request.memory_percent is not None
        or request.memory_usage is not None,
        "neighbors_count": _safe_count(request.neighbors_count),
        "routing_table_size": _safe_count(request.routing_table_size),
        "uptime": _safe_float(request.uptime),
        "custom_metrics_count": len(request.custom_metrics or {}),
        "pheromones_present": bool(request.pheromones),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _publish_node_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    operation: str,
    stage: str,
    status_value: str,
    duration_ms: float,
    http_status_code: int,
    user: UserContext | None = None,
    mesh_id: str | None = None,
    node_id: str | None = None,
    result_summary: Dict[str, Any] | None = None,
    reason: str = "",
    read_only: bool = False,
    control_action: bool = True,
    event_type: EventType = EventType.PIPELINE_STAGE_END,
) -> str | None:
    event_bus = _node_event_bus_from_request(request)
    if event_bus is None:
        return None
    result = result_summary or {}
    node_evidence = _node_lifecycle_evidence(
        operation=operation,
        stage=stage,
        status_value=status_value,
        duration_ms=duration_ms,
        result_summary=result,
        read_only=read_only,
    )
    payload = {
        "component": "api.maas.endpoints.nodes",
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "operation": operation,
        "stage": stage,
        "status": status_value,
        "duration_ms": round(duration_ms, 3),
        "http_status_code": http_status_code,
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "user_id", None)),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_present": bool(mesh_id),
        "node_id_present": bool(node_id),
        "source_quality": node_evidence["source_quality"],
        "node_lifecycle_evidence": node_evidence,
        "result_summary": result,
        "control_action": control_action,
        "read_only": read_only,
        "dataplane_confirmed": False,
        "node_identity_attested": False,
        "spiffe_authenticated": False,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "raw_request_payload_redacted": True,
        "raw_token_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _MODULAR_NODE_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, source_agent, payload, priority=6)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS node event: %s", exc)
        return None


def get_provisioner() -> MeshProvisioner:
    """Get or create the mesh provisioner."""
    global _provisioner
    if _provisioner is None:
        _provisioner = MeshProvisioner()
    return _provisioner


async def _resolve_mesh_for_user(mesh_id: str, user: UserContext) -> Any:
    """Resolve mesh and validate access (owner or ACL)."""
    instance = get_mesh(mesh_id)
    if instance is None:
        await require_mesh_access(mesh_id, user)
        instance = get_mesh(mesh_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mesh {mesh_id} not found",
            )

    if instance.owner_id != user.user_id:
        await require_mesh_access(mesh_id, user)

    return instance


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_external_telemetry_payload(request: NodeHeartbeatRequest, timestamp_iso: str) -> Dict[str, Any]:
    latency = _to_optional_float((request.custom_metrics or {}).get("latency_ms"))
    traffic = _to_optional_float((request.custom_metrics or {}).get("traffic_mbps"))
    payload: Dict[str, Any] = {
        "mesh_id": request.mesh_id,
        "node_id": request.node_id,
        "status": "healthy",
        "timestamp": timestamp_iso,
        "last_seen": timestamp_iso,
        "cpu_percent": (
            request.cpu_percent
            if request.cpu_percent is not None
            else request.cpu_usage
        ),
        "memory_percent": (
            request.memory_percent
            if request.memory_percent is not None
            else request.memory_usage
        ),
        "active_connections": (
            request.active_connections
            if request.active_connections is not None
            else request.neighbors_count
        ),
        "cpu_usage": request.cpu_usage,
        "memory_usage": request.memory_usage,
        "neighbors_count": request.neighbors_count,
        "routing_table_size": request.routing_table_size,
        "uptime": request.uptime,
        "custom_metrics": request.custom_metrics,
    }
    if latency is not None and latency >= 0:
        payload["latency_ms"] = latency
    if traffic is not None and traffic >= 0:
        payload["traffic_mbps"] = traffic
    return payload


def _export_external_telemetry(node_id: str, payload: Dict[str, Any]) -> bool:
    if _set_external_telemetry is None:
        return False
    try:
        _set_external_telemetry(node_id, payload)
        return True
    except Exception as exc:
        logger.warning("Failed to export modular heartbeat telemetry (node=%s): %s", node_id, exc)
        return False


@router.post(
    "/register",
    response_model=NodeRegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new node",
    description="Submit a node registration request for approval.",
)
async def register_node(
    request: NodeRegisterRequest,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> NodeRegisterResponse:
    """
    Register a new node with the mesh.

    The node will be in pending state until approved by the mesh owner.
    """
    started = time.monotonic()

    if not request.mesh_id:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
            layer=_MODULAR_NODE_REGISTRATION_LAYER,
            operation="register_node",
            stage="registration_validate",
            status_value="validation_failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            node_id=request.node_id,
            result_summary=_registration_summary(request),
            reason="missing_mesh_id",
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mesh_id is required",
        )

    if not request.node_id:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
            layer=_MODULAR_NODE_REGISTRATION_LAYER,
            operation="register_node",
            stage="registration_validate",
            status_value="validation_failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            mesh_id=request.mesh_id,
            result_summary=_registration_summary(request),
            reason="missing_node_id",
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="node_id is required",
        )

    try:
        await _resolve_mesh_for_user(request.mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
            layer=_MODULAR_NODE_REGISTRATION_LAYER,
            operation="register_node",
            stage="registration_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=request.mesh_id,
            node_id=request.node_id,
            result_summary=_registration_summary(request),
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    # Check if node is revoked
    if is_node_revoked(request.mesh_id, request.node_id):
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
            layer=_MODULAR_NODE_REGISTRATION_LAYER,
            operation="register_node",
            stage="registration_revocation_check",
            status_value="revoked",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_403_FORBIDDEN,
            user=user,
            mesh_id=request.mesh_id,
            node_id=request.node_id,
            result_summary=_registration_summary(request),
            reason="node_revoked",
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Node {request.node_id} is revoked",
        )

    # Add to pending nodes
    try:
        add_pending_node(request.mesh_id, request.node_id, {
            "public_key": request.public_key or request.public_keys.get("pqc"),
            "public_keys": request.public_keys,
            "capabilities": request.capabilities or [request.device_class],
            "metadata": request.metadata,
            "labels": request.labels,
            "hardware_id": request.hardware_id,
            "attestation_data": request.attestation_data,
            "enclave_enabled": request.enclave_enabled,
            "requested_at": datetime.utcnow().isoformat(),
            "requested_by": user.user_id,
            "enrollment_token_present": bool(request.enrollment_token),
        })
    except Exception as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
            layer=_MODULAR_NODE_REGISTRATION_LAYER,
            operation="register_node",
            stage="pending_node_mutation",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user=user,
            mesh_id=request.mesh_id,
            node_id=request.node_id,
            result_summary={
                **_registration_summary(request),
                "error_type": exc.__class__.__name__[:80],
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise

    response = NodeRegisterResponse(
        node_id=request.node_id,
        mesh_id=request.mesh_id,
        status="pending",
        message="Node registration submitted for approval",
    )
    _publish_node_event(
        http_request,
        source_agent=_MODULAR_NODE_REGISTRATION_SOURCE_AGENT,
        layer=_MODULAR_NODE_REGISTRATION_LAYER,
        operation="register_node",
        stage="pending_node_mutation",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_202_ACCEPTED,
        user=user,
        mesh_id=request.mesh_id,
        node_id=request.node_id,
        result_summary={
            **_registration_summary(request),
            "status": response.status,
        },
        reason="registration_pending",
    )
    return response


@router.post(
    "/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Submit node heartbeat",
    description="Submit telemetry data from a node.",
)
async def node_heartbeat(
    request: NodeHeartbeatRequest,
    http_request: Request = None,
) -> Dict[str, Any]:
    """
    Submit a node heartbeat.

    This endpoint is called by nodes themselves, not users.
    In production, this would use node authentication (SPIFFE SVID).
    """
    started = time.monotonic()
    # Update telemetry
    now = datetime.utcnow().isoformat()
    cpu_percent = (
        request.cpu_percent
        if request.cpu_percent is not None
        else request.cpu_usage
    )
    memory_percent = (
        request.memory_percent
        if request.memory_percent is not None
        else request.memory_usage
    )

    telemetry_payload = {
        "mesh_id": request.mesh_id,
        "node_id": request.node_id,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "active_connections": (
            request.active_connections
            if request.active_connections is not None
            else request.neighbors_count
        ),
        "cpu_usage": request.cpu_usage,
        "memory_usage": request.memory_usage,
        "neighbors_count": request.neighbors_count,
        "routing_table_size": request.routing_table_size,
        "uptime": request.uptime,
        "timestamp": now,
        "custom_metrics": request.custom_metrics,
    }

    try:
        update_node_telemetry(request.node_id, telemetry_payload)
        external_payload = _build_external_telemetry_payload(request, now)
        telemetry_exported = _export_external_telemetry(request.node_id, external_payload)
    except Exception as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_HEARTBEAT_SOURCE_AGENT,
            layer=_MODULAR_NODE_HEARTBEAT_LAYER,
            operation="node_heartbeat",
            stage="heartbeat_telemetry_update",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            mesh_id=request.mesh_id,
            node_id=request.node_id,
            result_summary={
                **_heartbeat_request_summary(request),
                "error_type": exc.__class__.__name__[:80],
            },
            reason=exc.__class__.__name__,
            read_only=False,
            control_action=False,
            event_type=EventType.TASK_FAILED,
        )
        raise

    response = {
        "status": "ok",
        "node_id": request.node_id,
        "timestamp": now,
        "telemetry_exported": telemetry_exported,
    }
    _publish_node_event(
        http_request,
        source_agent=_MODULAR_NODE_HEARTBEAT_SOURCE_AGENT,
        layer=_MODULAR_NODE_HEARTBEAT_LAYER,
        operation="node_heartbeat",
        stage="heartbeat_telemetry_update",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        mesh_id=request.mesh_id,
        node_id=request.node_id,
        result_summary={
            **_heartbeat_request_summary(request),
            "status": response["status"],
            "telemetry_exported": telemetry_exported,
        },
        reason="heartbeat_recorded",
        read_only=False,
        control_action=False,
    )
    return response


@router.get(
    "/{mesh_id}/pending",
    summary="List pending nodes",
    description="Get all nodes pending approval for a mesh.",
)
async def list_pending_nodes(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> List[Dict[str, Any]]:
    """List all pending node registrations for a mesh."""
    started = time.monotonic()
    try:
        await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
            layer=_MODULAR_NODE_READ_LAYER,
            operation="list_pending_nodes",
            stage="pending_nodes_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            result_summary={"mesh_id_present": bool(mesh_id)},
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    pending = get_pending_nodes(mesh_id)

    response = [
        {
            "node_id": node_id,
            "mesh_id": mesh_id,
            **data,
        }
        for node_id, data in pending.items()
    ]
    _publish_node_event(
        http_request,
        source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
        layer=_MODULAR_NODE_READ_LAYER,
        operation="list_pending_nodes",
        stage="pending_nodes_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        result_summary=_pending_nodes_summary(pending),
        reason="pending_nodes_read",
        read_only=True,
        control_action=False,
    )
    return response


@router.post(
    "/{mesh_id}/{node_id}/approve",
    summary="Approve node registration",
    description="Approve a pending node registration.",
)
async def approve_node(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> Dict[str, Any]:
    """Approve a pending node registration."""
    started = time.monotonic()
    try:
        await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="approve_node",
            stage="node_approval_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={"mesh_id_present": True, "node_id_present": True},
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    provisioner = get_provisioner()

    try:
        result = await provisioner.approve_node(
            mesh_id=mesh_id,
            node_id=node_id,
            actor=user.user_id,
        )
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="approve_node",
            stage="node_approval",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary=_node_result_summary(result),
            reason="node_approved",
        )
        return result

    except ValueError as e:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="approve_node",
            stage="node_approval",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "node_id_present": True,
                "mesh_id_present": True,
                "error_type": e.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=e.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{mesh_id}/{node_id}/revoke",
    summary="Revoke node",
    description="Revoke a node from the mesh.",
)
async def revoke_node(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
    reason: str = Query(..., description="Revocation reason"),
    http_request: Request = None,
) -> Dict[str, Any]:
    """Revoke a node from the mesh."""
    started = time.monotonic()
    try:
        await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="revoke_node",
            stage="node_revocation_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                "mesh_id_present": True,
                "node_id_present": True,
                "reason_present": bool(reason),
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    provisioner = get_provisioner()

    try:
        result = await provisioner.revoke_node(
            mesh_id=mesh_id,
            node_id=node_id,
            actor=user.user_id,
            reason=reason,
        )
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="revoke_node",
            stage="node_revocation",
            status_value="success",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_200_OK,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                **_node_result_summary(result),
                "reason_present": bool(reason),
            },
            reason="node_revoked",
        )
        return result

    except ValueError as e:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="revoke_node",
            stage="node_revocation",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_400_BAD_REQUEST,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "node_id_present": True,
                "mesh_id_present": True,
                "reason_present": bool(reason),
                "error_type": e.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=e.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{mesh_id}/{node_id}/telemetry",
    summary="Get node telemetry",
    description="Get latest telemetry data for a node.",
)
async def get_telemetry(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> Dict[str, Any]:
    """Get telemetry data for a node."""
    started = time.monotonic()
    try:
        await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
            layer=_MODULAR_NODE_READ_LAYER,
            operation="get_telemetry",
            stage="node_telemetry_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={"mesh_id_present": True, "node_id_present": True},
            reason=exc.__class__.__name__,
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    telemetry = get_node_telemetry(node_id)

    if not telemetry:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
            layer=_MODULAR_NODE_READ_LAYER,
            operation="get_telemetry",
            stage="node_telemetry_read",
            status_value="telemetry_missing",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_404_NOT_FOUND,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={"mesh_id_present": True, "node_id_present": True},
            reason="telemetry_missing",
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for node {node_id}",
        )

    telemetry_mesh_id = telemetry.get("mesh_id")
    if telemetry_mesh_id and telemetry_mesh_id != mesh_id:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
            layer=_MODULAR_NODE_READ_LAYER,
            operation="get_telemetry",
            stage="node_telemetry_mesh_check",
            status_value="telemetry_missing",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_404_NOT_FOUND,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                **_telemetry_shape_summary(telemetry),
                "telemetry_mesh_matches": False,
            },
            reason="telemetry_mesh_mismatch",
            read_only=True,
            control_action=False,
            event_type=EventType.TASK_BLOCKED,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for node {node_id} in mesh {mesh_id}",
        )

    _publish_node_event(
        http_request,
        source_agent=_MODULAR_NODE_READ_SOURCE_AGENT,
        layer=_MODULAR_NODE_READ_LAYER,
        operation="get_telemetry",
        stage="node_telemetry_read",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        node_id=node_id,
        result_summary={
            **_telemetry_shape_summary(telemetry),
            "telemetry_mesh_matches": True,
        },
        reason="telemetry_read",
        read_only=True,
        control_action=False,
    )
    return telemetry


@router.post(
    "/{mesh_id}/{node_id}/reissue",
    summary="Request credential reissue",
    description="Request a one-time token for credential reissue.",
)
async def request_reissue(
    mesh_id: str,
    node_id: str,
    user: UserContext = Depends(get_current_user),
    http_request: Request = None,
) -> Dict[str, Any]:
    """
    Request a credential reissue token.

    Returns a one-time token that can be used to reissue credentials
    for a compromised or expired node certificate.
    """
    import secrets
    from ..registry import add_reissue_token

    started = time.monotonic()
    try:
        await _resolve_mesh_for_user(mesh_id, user)
    except HTTPException as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="request_reissue",
            stage="reissue_access_check",
            status_value=(
                "not_found"
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else "denied"
            ),
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=exc.status_code,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={"mesh_id_present": True, "node_id_present": True},
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_BLOCKED,
        )
        raise

    # Generate one-time token
    token = f"reissue_{secrets.token_urlsafe(32)}"

    # Store token
    try:
        add_reissue_token(mesh_id, token, {
            "node_id": node_id,
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "used": False,
            "issued_by": user.user_id,
        })
    except Exception as exc:
        _publish_node_event(
            http_request,
            source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
            layer=_MODULAR_NODE_LIFECYCLE_LAYER,
            operation="request_reissue",
            stage="reissue_token_store",
            status_value="failed",
            duration_ms=(time.monotonic() - started) * 1000,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user=user,
            mesh_id=mesh_id,
            node_id=node_id,
            result_summary={
                "payload_type": "error",
                "payload_field_count": None,
                "node_id_present": True,
                "mesh_id_present": True,
                "token_present": True,
                "error_type": exc.__class__.__name__[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            },
            reason=exc.__class__.__name__,
            event_type=EventType.TASK_FAILED,
        )
        raise

    response = {
        "node_id": node_id,
        "mesh_id": mesh_id,
        "reissue_token": token,
        "expires_in": 3600,
    }
    _publish_node_event(
        http_request,
        source_agent=_MODULAR_NODE_LIFECYCLE_SOURCE_AGENT,
        layer=_MODULAR_NODE_LIFECYCLE_LAYER,
        operation="request_reissue",
        stage="reissue_token_store",
        status_value="success",
        duration_ms=(time.monotonic() - started) * 1000,
        http_status_code=status.HTTP_200_OK,
        user=user,
        mesh_id=mesh_id,
        node_id=node_id,
        result_summary=_node_result_summary(response),
        reason="reissue_token_created",
    )
    return response


__all__ = ["router"]
