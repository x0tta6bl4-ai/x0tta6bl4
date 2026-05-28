"""
MaaS ACL Policies (Production) — x0tta6bl4
=========================================

Zero-trust policy management backed by SQLAlchemy.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import require_role
from src.core.reliability_policy import mark_degraded_dependency
from src.database import ACLPolicy, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Policies"])

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
    current_user: User = Depends(require_role("operator")), 
    db: Session = Depends(get_db)
):
    # In a real app, we'd verify current_user owns the mesh_id
    return db.query(ACLPolicy).filter(ACLPolicy.mesh_id == mesh_id).all()

@router.post("/{mesh_id}/policies", response_model=PolicyResponse)
async def create_policy(
    mesh_id: str,
    req: PolicyRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    policy = ACLPolicy(
        id=f"pol-{uuid.uuid4().hex[:6]}",
        mesh_id=mesh_id,
        source_tag=req.source_tag,
        target_tag=req.target_tag,
        action=req.action
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    logger.info(f"🛡️ Policy {policy.id} created for mesh {mesh_id}")
    return policy

@router.delete("/{mesh_id}/policies/{policy_id}")
async def delete_policy(
    mesh_id: str,
    policy_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    policy = db.query(ACLPolicy).filter(ACLPolicy.id == policy_id, ACLPolicy.mesh_id == mesh_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    return {"status": "deleted", "policy_id": policy_id}
