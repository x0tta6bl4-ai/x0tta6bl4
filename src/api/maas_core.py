"""
MaaS Core (Production) — x0tta6bl4
==================================

Handles mesh lifecycle (deploy, list, terminate) using SQLAlchemy.
Includes Autonomous Market Regulation via PricingAgent.
"""

import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import User, MeshInstance, MeshNode, get_db
from src.api.maas_auth import get_current_user_from_maas, require_role
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.ai.dynamic_pricing import pricing_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Core"])

_MAAS_CORE_LIFECYCLE_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
_MAAS_CORE_LIFECYCLE_CLAIM_BOUNDARY = (
    "MaaS core lifecycle responses expose local database lifecycle records only. "
    "Mesh status values such as active, healthy node seed rows, listed, or "
    "terminated do not prove infrastructure provisioning, node reachability, "
    "dataplane delivery, routing convergence, production SLOs, customer traffic, "
    "external DPI bypass, settlement finality, or production readiness."
)
_MAAS_CORE_LIFECYCLE_CLAIM_HEADERS = {
    "X-X0TTA6BL4-Claim-Gate-Schema": "x0tta6bl4.maas_core_lifecycle_claim_gate.v1",
    "X-X0TTA6BL4-Claim-Boundary": _MAAS_CORE_LIFECYCLE_CLAIM_BOUNDARY,
    "X-X0TTA6BL4-Local-Mesh-Lifecycle-Claim-Allowed": "true",
    "X-X0TTA6BL4-Local-DB-Lifecycle-Claim-Allowed": "true",
    "X-X0TTA6BL4-Infrastructure-Provisioning-Claim-Allowed": "false",
    "X-X0TTA6BL4-Node-Reachability-Claim-Allowed": "false",
    "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Traffic-Delivery-Claim-Allowed": "false",
    "X-X0TTA6BL4-Customer-Traffic-Claim-Allowed": "false",
    "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed": "false",
    "X-X0TTA6BL4-Settlement-Finality-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-Readiness-Claim-Allowed": "false",
    "X-X0TTA6BL4-Production-SLO-Claim-Allowed": "false",
    "X-X0TTA6BL4-Routing-Convergence-Claim-Allowed": "false",
}

_PRICING_AGENT_INTERVAL_SECONDS = max(
    5,
    int(os.getenv("MAAS_PRICING_AGENT_INTERVAL_SECONDS", "60")),
)
_pricing_agent_lock = threading.Lock()
_last_pricing_agent_attempt_at: Optional[datetime] = None


def _maas_core_lifecycle_claim_gate(
    surface: str = "maas_core.lifecycle",
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_core_lifecycle_claim_gate.v1",
        "surface": surface,
        "local_mesh_lifecycle_claim_allowed": True,
        "local_db_lifecycle_claim_allowed": True,
        "infrastructure_provisioning_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "claim_boundary": _MAAS_CORE_LIFECYCLE_CLAIM_BOUNDARY,
    }


def _maas_core_lifecycle_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        _MAAS_CORE_LIFECYCLE_CROSS_PLANE_CLAIMS,
        surface=surface,
    )


def _maas_core_lifecycle_claim_boundary_headers() -> Dict[str, str]:
    return dict(_MAAS_CORE_LIFECYCLE_CLAIM_HEADERS)


def _set_maas_core_lifecycle_claim_headers(http_response: Response) -> None:
    if http_response is not None:
        http_response.headers.update(_maas_core_lifecycle_claim_boundary_headers())


def _maybe_run_pricing_agent(db: Session) -> None:
    """Run pricing regulation at most once per interval per process."""
    global _last_pricing_agent_attempt_at

    now = datetime.utcnow()
    last_attempt = _last_pricing_agent_attempt_at
    if last_attempt and (now - last_attempt).total_seconds() < _PRICING_AGENT_INTERVAL_SECONDS:
        return

    with _pricing_agent_lock:
        now = datetime.utcnow()
        last_attempt = _last_pricing_agent_attempt_at
        if last_attempt and (now - last_attempt).total_seconds() < _PRICING_AGENT_INTERVAL_SECONDS:
            return
        _last_pricing_agent_attempt_at = now

        try:
            pricing_agent.analyze_and_propose(db)
        except Exception:
            logger.exception("AI Pricing failed")

class MeshDeployRequest(BaseModel):
    name: str = Field(..., min_length=3)
    nodes: int = Field(default=5, ge=1)
    billing_plan: str = Field(default="starter")

class MeshResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    nodes_count: int
    created_at: datetime

@router.post("/deploy", response_model=MeshResponse)
async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    http_response: Response = None,
):
    _set_maas_core_lifecycle_claim_headers(http_response)

    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    join_token = secrets.token_urlsafe(32)
    
    instance = MeshInstance(
        id=mesh_id,
        name=req.name,
        owner_id=current_user.id,
        plan=req.billing_plan,
        join_token=join_token,
        join_token_expires_at=datetime.utcnow() + timedelta(days=7),
        status="active"
    )
    db.add(instance)
    
    # Provision initial nodes
    for i in range(req.nodes):
        node = MeshNode(
            id=f"{mesh_id}-node-{i}",
            mesh_id=mesh_id,
            status="healthy",
            device_class="edge"
        )
        db.add(node)
        
    db.commit()
    db.refresh(instance)
    
    return {
        "id": instance.id,
        "name": instance.name,
        "status": instance.status,
        "nodes_count": req.nodes,
        "created_at": instance.created_at,
        "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
            "maas_core.lifecycle.deploy"
        ),
        "cross_plane_claim_gate": _maas_core_lifecycle_cross_plane_gate(
            "maas_core.lifecycle.deploy"
        ),
    }

@router.get("/list", response_model=List[MeshResponse])
def list_meshes(
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    http_response: Response = None,
):
    _set_maas_core_lifecycle_claim_headers(http_response)

    # Trigger market regulation lazily, but avoid re-running on every request.
    _maybe_run_pricing_agent(db)

    mesh_rows = (
        db.query(
            MeshInstance.id.label("id"),
            MeshInstance.name.label("name"),
            MeshInstance.status.label("status"),
            MeshInstance.created_at.label("created_at"),
            func.count(MeshNode.id).label("nodes_count"),
        )
        .outerjoin(MeshNode, MeshNode.mesh_id == MeshInstance.id)
        .filter(MeshInstance.owner_id == current_user.id)
        .group_by(
            MeshInstance.id,
            MeshInstance.name,
            MeshInstance.status,
            MeshInstance.created_at,
        )
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "nodes_count": int(row.nodes_count or 0),
            "created_at": row.created_at,
            "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
                "maas_core.lifecycle.list"
            ),
            "cross_plane_claim_gate": _maas_core_lifecycle_cross_plane_gate(
                "maas_core.lifecycle.list"
            ),
        }
        for row in mesh_rows
    ]

@router.delete("/{mesh_id}")
async def terminate_mesh(
    mesh_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
    http_response: Response = None,
):
    _set_maas_core_lifecycle_claim_headers(http_response)

    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id, MeshInstance.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    instance.status = "terminated"
    db.commit()
    return {
        "status": "terminated",
        "mesh_id": mesh_id,
        "maas_core_lifecycle_claim_gate": _maas_core_lifecycle_claim_gate(
            "maas_core.lifecycle.terminate"
        ),
        "cross_plane_claim_gate": _maas_core_lifecycle_cross_plane_gate(
            "maas_core.lifecycle.terminate"
        ),
    }
