"""
MaaS Node Management (Production) — x0tta6bl4
============================================

SQLAlchemy-backed node registration and admission control.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import User, MeshNode, MeshInstance, get_db
from src.api.maas_auth import require_role
from src.api.maas_security import token_signer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Nodes"])

class NodeRegisterRequest(BaseModel):
    node_id: Optional[str] = None
    enrollment_token: str
    device_class: str = "edge"
    hardware_id: Optional[str] = None

@router.post("/{mesh_id}/nodes/register")
async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    db: Session = Depends(get_db)
):
    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    if req.enrollment_token != instance.join_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    node_id = req.node_id or f"node-{uuid.uuid4().hex[:6]}"
    
    # Check if node already exists
    existing = db.query(MeshNode).filter(MeshNode.id == node_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Node ID already registered")

    node = MeshNode(
        id=node_id,
        mesh_id=mesh_id,
        device_class=req.device_class,
        hardware_id=req.hardware_id,
        status="pending"
    )
    db.add(node)
    db.commit()
    
    logger.info(f"🆕 Node {node_id} registered (pending) for mesh {mesh_id}")
    return {"status": "pending_approval", "node_id": node_id}

@router.get("/{mesh_id}/nodes/pending")
def list_pending(
    mesh_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator"))
):
    return db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id, MeshNode.status == "pending").all()

from src.database import User, MeshNode, MeshInstance, ACLPolicy, get_db

@router.get("/{mesh_id}/node-config/{node_id}")
def get_node_config(mesh_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    Called by Agent to fetch its allowed policies and peer tags.
    This is the core of local enforcement.
    """
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Fetch all policies for this mesh
    policies = db.query(ACLPolicy).filter(ACLPolicy.mesh_id == mesh_id).all()
    
    # Fetch all approved peers
    peers = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id, MeshNode.status == "approved").all()
    
    # Simple tag-based evaluation logic
    allowed_peers = []
    denied_peers = []
    
    # In this MVP version, we return all data and let the agent enforce.
    # In Enterprise version, we return pre-calculated allow/deny lists.
    
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "acl_profile": node.acl_profile,
        "policies": [
            {"source_tag": p.source_tag, "target_tag": p.target_tag, "action": p.action}
            for p in policies
        ],
        "peers": [
            {"id": p.id, "class": p.device_class}
            for p in peers if p.id != node_id
        ],
        "enforcement": "tag-based",
        "global_mode": "zero-trust"
    }

@router.get("/{mesh_id}/nodes/all")
def list_all_nodes(
    mesh_id: str,
    node_status: Optional[str] = None,
    current_user: User = Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    query = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id)
    if node_status:
        query = query.filter(MeshNode.status == node_status)
    
    nodes = query.all()
    return {
        "mesh_id": mesh_id,
        "nodes": nodes,
        "count": len(nodes)
    }

@router.post("/{mesh_id}/nodes/{node_id}/revoke")
async def revoke_node(
    mesh_id: str,
    node_id: str,
    current_user: User = Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.status = "revoked"
    db.commit()
    return {"status": "revoked", "node_id": node_id}

@router.post("/{mesh_id}/nodes/{node_id}/approve")
async def approve_node(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator"))
):
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.status = "approved"
    db.commit()
    
    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    signed = token_signer.sign_token(instance.join_token, mesh_id)
    
    return {
        "status": "approved",
        "join_token": signed
    }
