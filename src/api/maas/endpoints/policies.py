"""
MaaS ACL Policies (Production) — x0tta6bl4
=========================================

Zero-trust policy management backed by SQLAlchemy.
"""
from __future__ import annotations

import logging
import uuid
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import require_role
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import ACLPolicy, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MaaS Policies"])

_POLICY_LIST_SOURCE_AGENT = "maas-policies-list-read"
_POLICY_LIST_LAYER = "api_policy_acl_observed_state"
_POLICY_CREATE_SOURCE_AGENT = "maas-policies-create"
_POLICY_CREATE_LAYER = "api_policy_acl_control_action"
_POLICY_DELETE_SOURCE_AGENT = "maas-policies-delete"
_POLICY_DELETE_LAYER = "api_policy_acl_control_action"
_POLICY_CLAIM_BOUNDARY = (
    "MaaS policy evidence records bounded metadata for the DB-backed ACLPolicy "
    "router only. GET/POST /{mesh_id}/policies are shadowed by the legacy router "
    "in the current app route order; DELETE remains DB-backed here. Evidence does "
    "not expose raw emails, user IDs, mesh IDs, policy IDs, policy tags, API keys, "
    "session tokens, or prove dataplane enforcement."
)


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _policy_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize MaaS policies EventBus: %s", exc)
        return None


def _policy_actor_summary(user: Any) -> Dict[str, Any]:
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", "") or "")[:40],
    }


def _policy_action_bucket(value: Any) -> str:
    action = str(value or "").strip().lower()
    return action if action in {"allow", "deny"} else "other"


def _publish_policy_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    current_user: Any,
    mesh_id: Any,
    status: str,
    policy_id: Any = None,
    source_tag: Any = None,
    target_tag: Any = None,
    action: Any = None,
    policies: list[Any] | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
    route_shadowed_by_legacy: bool = False,
) -> str | None:
    event_bus = _policy_event_bus_from_request(request)
    if event_bus is None:
        return None

    policy_list = list(policies or [])
    action_counts = {"allow": 0, "deny": 0, "other": 0}
    for policy in policy_list:
        action_counts[_policy_action_bucket(getattr(policy, "action", None))] += 1

    payload = {
        "component": "api.maas_policies",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_policy_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "policy_id_hash": _redacted_sha256_prefix(policy_id),
        "source_tag_hash": _redacted_sha256_prefix(source_tag),
        "target_tag_hash": _redacted_sha256_prefix(target_tag),
        "source_tag_present": bool(str(source_tag or "").strip()),
        "target_tag_present": bool(str(target_tag or "").strip()),
        "action_bucket": _policy_action_bucket(action),
        "policies_count": len(policy_list),
        "policy_action_counts": action_counts,
        "db_backed_acl_policy": True,
        "route_shadowed_by_legacy": route_shadowed_by_legacy,
        "http_status_code": http_status_code,
        "read_only": source_agent == _POLICY_LIST_SOURCE_AGENT,
        "observed_state": source_agent == _POLICY_LIST_SOURCE_AGENT,
        "safe_actuator": False,
        "control_action": source_agent != _POLICY_LIST_SOURCE_AGENT,
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _POLICY_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            source_agent,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS policy event: %s", exc)
        return None

class PolicyRequest(BaseModel):
    source_tag: str = Field(..., min_length=1)
    target_tag: str = Field(..., min_length=1)
    action: str = Field(default="allow", pattern="^(allow|deny)$")

class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mesh_id: str
    source_tag: str
    target_tag: str
    action: str
    created_at: datetime


def _policy_db_session_available(db: Any) -> bool:
    return all(
        hasattr(db, attr)
        for attr in ("query", "add", "commit", "delete")
    )


def _acl_policy_model_available() -> bool:
    return all(
        hasattr(ACLPolicy, attr)
        for attr in ("id", "mesh_id", "source_tag", "target_tag", "action")
    )


def _policy_readiness_status(db: Any) -> Dict[str, Any]:
    policy_db_ready = _policy_db_session_available(db)
    acl_policy_model_ready = _acl_policy_model_available()
    rbac_dependency_ready = callable(require_role)
    policy_runtime_ready = (
        policy_db_ready
        and acl_policy_model_ready
        and rbac_dependency_ready
    )

    degraded_dependencies = []
    if not policy_db_ready:
        degraded_dependencies.append("database")
    if not acl_policy_model_ready:
        degraded_dependencies.append("acl_policy_model")
    if not rbac_dependency_ready:
        degraded_dependencies.append("rbac")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "policy_runtime_ready": policy_runtime_ready,
        "policy_db_ready": policy_db_ready,
        "acl_policy_model_ready": acl_policy_model_ready,
        "rbac_dependency_ready": rbac_dependency_ready,
        "legacy_route_shadowing": {
            "get_post_shadowed_by_legacy": True,
            "db_backed_delete_route_active": True,
            "boundary": (
                "Legacy maas router is registered before maas_policies, so "
                "GET/POST /{mesh_id}/policies are handled by legacy in-memory "
                "policy routes while DELETE remains DB-backed here."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "DB-backed policy CRUD requires query/add/delete/commit support "
                "for ACLPolicy rows."
            ),
            "acl_policy_model": (
                "ACLPolicy maps mesh source/target tags to allow/deny actions."
            ),
            "rbac": (
                "Policy routes depend on role checks from maas_auth.require_role."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_policy_readiness"
        ),
        "claim_boundary": (
            "Policy readiness distinguishes this DB-backed ACL policy router from "
            "legacy in-memory policy handlers that shadow GET and POST by route "
            "order. It does not prove that every mesh policy is enforced by data "
            "plane components."
        ),
    }


@router.get("/policies/readiness")
async def policy_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _policy_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.get("/{mesh_id}/policies", response_model=List[PolicyResponse])
def list_policies(
    mesh_id: str,
    request: Request,
    current_user: User = Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    started = time.monotonic()
    # In a real app, we'd verify current_user owns the mesh_id
    policies = db.query(ACLPolicy).filter(ACLPolicy.mesh_id == mesh_id).all()
    _publish_policy_event(
        request,
        source_agent=_POLICY_LIST_SOURCE_AGENT,
        layer=_POLICY_LIST_LAYER,
        stage="policy_list_read",
        operation="maas_policies_list_read",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        policies=policies,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="db_backed_policy_list_read",
        route_shadowed_by_legacy=True,
    )
    return policies

@router.post("/{mesh_id}/policies", response_model=PolicyResponse)
async def create_policy(
    mesh_id: str,
    req: PolicyRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    started = time.monotonic()
    policy = ACLPolicy(
        id=f"pol-{uuid.uuid4().hex[:6]}",
        mesh_id=mesh_id,
        source_tag=req.source_tag,
        target_tag=req.target_tag,
        action=req.action
    )
    try:
        db.add(policy)
        db.commit()
        db.refresh(policy)
    except Exception as exc:
        _publish_policy_event(
            request,
            source_agent=_POLICY_CREATE_SOURCE_AGENT,
            layer=_POLICY_CREATE_LAYER,
            stage="policy_create_control",
            operation="maas_policies_create",
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            policy_id=getattr(policy, "id", None),
            source_tag=req.source_tag,
            target_tag=req.target_tag,
            action=req.action,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
            route_shadowed_by_legacy=True,
        )
        raise
    _publish_policy_event(
        request,
        source_agent=_POLICY_CREATE_SOURCE_AGENT,
        layer=_POLICY_CREATE_LAYER,
        stage="policy_create_control",
        operation="maas_policies_create",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        policy_id=getattr(policy, "id", None),
        source_tag=req.source_tag,
        target_tag=req.target_tag,
        action=req.action,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="db_backed_policy_create",
        route_shadowed_by_legacy=True,
    )
    logger.info(f"🛡️ Policy {policy.id} created for mesh {mesh_id}")
    return policy

@router.delete("/{mesh_id}/policies/{policy_id}")
async def delete_policy(
    mesh_id: str,
    policy_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    started = time.monotonic()
    policy = db.query(ACLPolicy).filter(ACLPolicy.id == policy_id, ACLPolicy.mesh_id == mesh_id).first()
    if not policy:
        _publish_policy_event(
            request,
            source_agent=_POLICY_DELETE_SOURCE_AGENT,
            layer=_POLICY_DELETE_LAYER,
            stage="policy_delete_control",
            operation="maas_policies_delete",
            current_user=current_user,
            mesh_id=mesh_id,
            status="denied",
            policy_id=policy_id,
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="policy_not_found",
            route_shadowed_by_legacy=False,
        )
        raise HTTPException(status_code=404, detail="Policy not found")

    action = getattr(policy, "action", None)
    source_tag = getattr(policy, "source_tag", None)
    target_tag = getattr(policy, "target_tag", None)
    try:
        db.delete(policy)
        db.commit()
    except Exception as exc:
        _publish_policy_event(
            request,
            source_agent=_POLICY_DELETE_SOURCE_AGENT,
            layer=_POLICY_DELETE_LAYER,
            stage="policy_delete_control",
            operation="maas_policies_delete",
            current_user=current_user,
            mesh_id=mesh_id,
            status="failed",
            policy_id=policy_id,
            source_tag=source_tag,
            target_tag=target_tag,
            action=action,
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=type(exc).__name__,
            route_shadowed_by_legacy=False,
        )
        raise
    _publish_policy_event(
        request,
        source_agent=_POLICY_DELETE_SOURCE_AGENT,
        layer=_POLICY_DELETE_LAYER,
        stage="policy_delete_control",
        operation="maas_policies_delete",
        current_user=current_user,
        mesh_id=mesh_id,
        status="success",
        policy_id=policy_id,
        source_tag=source_tag,
        target_tag=target_tag,
        action=action,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="db_backed_policy_delete",
        route_shadowed_by_legacy=False,
    )
    return {"status": "deleted", "policy_id": policy_id}

