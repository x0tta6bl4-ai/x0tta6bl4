"""
MaaS Core (Production) — x0tta6bl4
==================================

Handles mesh lifecycle (deploy, list, terminate) using SQLAlchemy.
Includes Autonomous Market Regulation via PricingAgent.
"""

import logging
import uuid
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import User, MeshInstance, MeshNode, get_db
from src.api.maas_auth import get_current_user_from_maas, require_role
from src.ai.dynamic_pricing import pricing_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Core"])

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
    # 🤖 Autonomous Market Regulation
    # Triggered on user activity to ensure market prices are fair
    try:
        pricing_agent.analyze_and_propose(db)
    except Exception as e:
        logger.error(f"AI Pricing failed: {e}")

    meshes = db.query(MeshInstance).filter(MeshInstance.owner_id == current_user.id).all()
    results = []
    for m in meshes:
        count = db.query(MeshNode).filter(MeshNode.mesh_id == m.id).count()
        results.append({
            "id": m.id,
            "name": m.name,
            "status": m.status,
            "nodes_count": count,
            "created_at": m.created_at
        })
    return results

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
