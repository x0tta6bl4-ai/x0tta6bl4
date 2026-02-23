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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import User, MeshInstance, MeshNode, get_db
from src.api.maas_auth import get_current_user_from_maas, require_role
from src.ai.dynamic_pricing import pricing_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Core"])

_PRICING_AGENT_INTERVAL_SECONDS = max(
    5,
    int(os.getenv("MAAS_PRICING_AGENT_INTERVAL_SECONDS", "60")),
)
_pricing_agent_lock = threading.Lock()
_last_pricing_agent_attempt_at: Optional[datetime] = None


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
    id: str
    name: str
    status: str
    nodes_count: int
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/deploy", response_model=MeshResponse)
async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
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
        "created_at": instance.created_at
    }

@router.get("/list", response_model=List[MeshResponse])
def list_meshes(
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
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
        }
        for row in mesh_rows
    ]

@router.delete("/{mesh_id}")
async def terminate_mesh(
    mesh_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id, MeshInstance.owner_id == current_user.id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    instance.status = "terminated"
    db.commit()
    return {"status": "terminated", "mesh_id": mesh_id}
