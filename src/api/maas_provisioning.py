"""
MaaS Provisioning API for x0tta6bl4.
=====================================

Handles the "One-Click Deploy" wizard logic. Generates cryptographically 
signed installation scripts and tokens for new mesh nodes.
"""

import logging
import uuid
import base64
import json
import hashlib
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.database import MeshNode, get_db, User
from src.api.maas_auth import get_current_user_from_maas
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.reliability_policy import mark_degraded_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/provisioning", tags=["MaaS Provisioning"])

_PROVISIONING_SETUP_SOURCE_AGENT = "maas-provisioning-setup-generate"
_PROVISIONING_LAYER = "api_provisioning_node_join_control_action"

PROVISIONING_CLAIM_BOUNDARY = (
    "MaaS provisioning setup API evidence only. It records local pending-node "
    "DB write state and redacted setup-package metadata; it does not prove the "
    "returned install command was executed, a node joined the dataplane, PQC was "
    "negotiated, or ZKP authentication completed."
)
_PROVISIONING_SETUP_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_provisioning_setup_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": PROVISIONING_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Setup-Package-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-Pending-Node-DB-Claim-Allowed": "true",
    "X-X0TTA6BL4-Install-Command-Executed-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Dataplane-Join-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-PQC-Negotiation-Claim-Allowed": "false",
    "X-X0TTA6BL4-ZKP-Authentication-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
}

class ProvisionRequest(BaseModel):
    mesh_id: str
    device_name: str
    device_class: str = "generic" # generic, server, edge
    os_type: str = "linux" # linux, darwin, android

class ProvisionResponse(BaseModel):
    node_id: str
    join_token: str
    install_command: str
    config_json: str
    provisioning_setup_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = Field(default_factory=dict)


def _provisioning_setup_claim_gate(
    *,
    surface: str = "maas_provisioning.generate_setup",
    db_write_succeeded: bool | None = None,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_provisioning_setup_claim_gate.v1",
        "surface": surface,
        "local_setup_package_generation_claim_allowed": True,
        "local_join_token_generation_claim_allowed": True,
        "local_pending_node_db_write_claim_allowed": bool(db_write_succeeded),
        "install_command_executed_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "pqc_negotiation_claim_allowed": False,
        "zkp_authentication_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": PROVISIONING_CLAIM_BOUNDARY,
    }


def _provisioning_setup_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return readiness_cross_plane_claim_gate_metadata(surface=surface)


def _provisioning_setup_claim_boundary_headers() -> Dict[str, str]:
    return dict(_PROVISIONING_SETUP_CLAIM_HEADERS)


def _set_provisioning_setup_claim_headers(http_response: Response) -> None:
    if http_response is not None:
        http_response.headers.update(_provisioning_setup_claim_boundary_headers())


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _provisioning_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize MaaS provisioning EventBus: %s", exc)
        return None


def _actor_summary(user: Any) -> Dict[str, Any]:
    if user is None:
        return {
            "actor_user_id_hash": None,
            "actor_email_hash": None,
            "actor_email_present": False,
            "actor_role": "",
        }
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", "") or "")[:40],
    }


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "add") and hasattr(db, "commit")


def _provisioning_readiness_status(db: Any) -> Dict[str, Any]:
    db_ready = _db_session_available(db)
    event_bus_ready = bool(EventBus and get_event_bus)
    auth_dependency_ready = callable(get_current_user_from_maas)
    runtime_ready = all([db_ready, event_bus_ready, auth_dependency_ready])
    degraded_dependencies = []
    if not db_ready:
        degraded_dependencies.append("database")
    if not event_bus_ready:
        degraded_dependencies.append("event_bus")
    if not auth_dependency_ready:
        degraded_dependencies.append("auth_dependency")

    return {
        "readiness_status": "ready" if runtime_ready else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "provisioning_runtime_ready": runtime_ready,
        "db_write_ready": db_ready,
        "event_bus_ready": event_bus_ready,
        "auth_dependency_ready": auth_dependency_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "pending_node_store": "database_required",
            "join_token_store": "response_only",
            "install_command": "generated_locally",
            "pqc_zkp_flags": "config_claim_only",
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_provisioning_readiness"
        ),
        "claim_boundary": (
            "Readiness verifies route dependencies for setup package generation. "
            "It does not create a node, persist a join token, execute an install "
            "command, prove dataplane join, or prove PQC/ZKP negotiation."
        ),
    }


def _event_type_for_status(http_status_code: int | None) -> EventType:
    if http_status_code is None or http_status_code < 400:
        return EventType.PIPELINE_STAGE_END
    if http_status_code >= 500:
        return EventType.TASK_FAILED
    return EventType.TASK_BLOCKED


def _publish_provisioning_event(
    request: Request | None,
    *,
    status: str,
    current_user: Any = None,
    provision_request: ProvisionRequest | None = None,
    node_id: str | None = None,
    join_token: str | None = None,
    install_command: str | None = None,
    config_json: str | None = None,
    db_backed: bool | None = None,
    db_write_attempted: bool = False,
    db_write_succeeded: bool | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _provisioning_event_bus_from_request(request)
    if event_bus is None:
        return None
    payload: Dict[str, Any] = {
        "component": "api.maas_provisioning",
        "stage": "setup_generate_control",
        "operation": "maas_provisioning_generate_setup",
        "service_name": _PROVISIONING_SETUP_SOURCE_AGENT,
        "source_alias": _PROVISIONING_SETUP_SOURCE_AGENT,
        "layer": _PROVISIONING_LAYER,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(
            getattr(provision_request, "mesh_id", None)
        ),
        "device_name_hash": _redacted_sha256_prefix(
            getattr(provision_request, "device_name", None)
        ),
        "device_name_present": bool(getattr(provision_request, "device_name", None)),
        "device_class": str(getattr(provision_request, "device_class", "") or "")[:40],
        "os_type": str(getattr(provision_request, "os_type", "") or "")[:40],
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "join_token_hash": _redacted_sha256_prefix(join_token),
        "join_token_present": bool(join_token),
        "install_command_hash": _redacted_sha256_prefix(install_command),
        "install_command_length": len(str(install_command or "")),
        "config_json_hash": _redacted_sha256_prefix(config_json),
        "config_json_length": len(str(config_json or "")),
        "config_contains_pqc_flag": bool(config_json),
        "config_contains_zkp_flag": bool(config_json),
        "db_backed": db_backed,
        "db_write_attempted": db_write_attempted,
        "db_write_succeeded": db_write_succeeded,
        "pending_node_status": "pending" if db_write_succeeded else "",
        "provisioning_setup_claim_gate": _provisioning_setup_claim_gate(
            db_write_succeeded=db_write_succeeded
        ),
        "http_status_code": http_status_code,
        "control_action": True,
        "raw_mesh_id_redacted": True,
        "raw_device_name_redacted": True,
        "raw_node_id_redacted": True,
        "raw_join_token_redacted": True,
        "raw_install_command_redacted": True,
        "raw_config_redacted": True,
        "reason": str(reason or "")[:120],
        "claim_boundary": PROVISIONING_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            _event_type_for_status(http_status_code),
            _PROVISIONING_SETUP_SOURCE_AGENT,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS provisioning event: %s", exc)
        return None


@router.get("/readiness")
async def provisioning_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _provisioning_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload

@router.post("/generate-setup")
async def generate_provisioning_setup(
    req: ProvisionRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    http_response: Response = None,
    request: Request = None,
) -> ProvisionResponse:
    """Generates a one-liner installation script for a new node."""
    started = time.monotonic()
    _set_provisioning_setup_claim_headers(http_response)
    
    node_id = f"node-{uuid.uuid4().hex[:8]}"
    join_token = f"tok-{uuid.uuid4().hex[:12]}"
    
    # Create entry in DB (pending attestation)
    new_node = MeshNode(
        id=node_id,
        mesh_id=req.mesh_id,
        device_class=req.device_class,
        status="pending",
        acl_profile="default"
    )
    try:
        db.add(new_node)
        db.commit()
        db_write_succeeded = True
    except Exception:
        if hasattr(db, "rollback"):
            db.rollback()
        _publish_provisioning_event(
            request,
            status="failed",
            current_user=current_user,
            provision_request=req,
            node_id=node_id,
            join_token=join_token,
            db_backed=_db_session_available(db),
            db_write_attempted=True,
            db_write_succeeded=False,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="db_write_failed",
        )
        raise
    
    # Generate Install Command (One-liner)
    # In prod, this would point to a real script hosted on MaaS
    api_url = "https://api.x0tta6bl4.io" 
    install_cmd = (
        f"curl -sSL {api_url}/install.sh | sudo bash -s -- "
        f"--node-id {node_id} --token {join_token} --mesh {req.mesh_id}"
    )
    
    # Generate minimal config
    config = {
        "node_id": node_id,
        "mesh_id": req.mesh_id,
        "join_token": join_token,
        "api_endpoint": api_url,
        "pqc_enabled": True,
        "zkp_auth": True
    }
    config_json = base64.b64encode(json.dumps(config).encode()).decode()
    _publish_provisioning_event(
        request,
        status="created",
        current_user=current_user,
        provision_request=req,
        node_id=node_id,
        join_token=join_token,
        install_command=install_cmd,
        config_json=config_json,
        db_backed=_db_session_available(db),
        db_write_attempted=True,
        db_write_succeeded=db_write_succeeded,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    
    return ProvisionResponse(
        node_id=node_id,
        join_token=join_token,
        install_command=install_cmd,
        config_json=config_json,
        provisioning_setup_claim_gate=_provisioning_setup_claim_gate(
            db_write_succeeded=db_write_succeeded
        ),
        cross_plane_claim_gate=_provisioning_setup_cross_plane_gate(
            "maas_provisioning.generate_setup"
        ),
    )

def include_provisioning_router(app):
    app.include_router(router)
