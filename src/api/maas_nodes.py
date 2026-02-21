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

from src.database import ACLPolicy, MarketplaceEscrow, MarketplaceListing, MeshInstance, MeshNode, User, get_db
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


class HeartbeatRequest(BaseModel):
    status: str = Field(default="healthy", pattern="^(healthy|degraded|unhealthy)$")
    cpu_percent: Optional[float] = None
    mem_percent: Optional[float] = None


@router.post("/{mesh_id}/nodes/{node_id}/heartbeat")
async def node_heartbeat(
    mesh_id: str,
    node_id: str,
    req: HeartbeatRequest,
    db: Session = Depends(get_db),
):
    """
    Called by node agents at regular intervals.  Updates last_seen timestamp
    and auto-releases any marketplace escrow waiting on this node's health.
    """
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    node.last_seen = datetime.utcnow()
    if req.status == "healthy":
        node.status = "approved"
    elif req.status == "unhealthy":
        node.status = "degraded"

    released_escrow = None
    if req.status == "healthy":
        # Find a marketplace listing for this node whose escrow is held
        listing = (
            db.query(MarketplaceListing)
            .filter(MarketplaceListing.node_id == node_id, MarketplaceListing.status == "escrow")
            .first()
        )
        if listing:
            escrow = (
                db.query(MarketplaceEscrow)
                .filter(MarketplaceEscrow.listing_id == listing.id, MarketplaceEscrow.status == "held")
                .first()
            )
            if escrow:
                escrow.status = "released"
                escrow.released_at = datetime.utcnow()
                listing.status = "rented"
                released_escrow = escrow.id
                logger.info(
                    "✅ Heartbeat auto-released escrow %s for node %s (listing %s)",
                    escrow.id, node_id, listing.id,
                )

    db.commit()

    return {
        "status": "ok",
        "node_id": node_id,
        "mesh_id": mesh_id,
        "node_status": node.status,
        "last_seen": node.last_seen.isoformat(),
        "escrow_released": released_escrow,
    }


class AccessCheckRequest(BaseModel):
    source_node_id: str
    target_node_id: str


@router.post("/{mesh_id}/nodes/check-access")
def check_access(
    mesh_id: str,
    req: AccessCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Server-side ACL enforcement.  Returns allow/deny based on the tags of
    both nodes and the active policies for the mesh.
    """
    src_node = db.query(MeshNode).filter(
        MeshNode.id == req.source_node_id, MeshNode.mesh_id == mesh_id
    ).first()
    tgt_node = db.query(MeshNode).filter(
        MeshNode.id == req.target_node_id, MeshNode.mesh_id == mesh_id
    ).first()

    if not src_node or not tgt_node:
        raise HTTPException(status_code=404, detail="One or both nodes not found in this mesh")

    src_tag = src_node.acl_profile or "default"
    tgt_tag = tgt_node.acl_profile or "default"

    policies = (
        db.query(ACLPolicy)
        .filter(ACLPolicy.mesh_id == mesh_id)
        .all()
    )

    # Evaluate policies in creation order (first match wins).
    for policy in policies:
        src_match = policy.source_tag in (src_tag, "*")
        tgt_match = policy.target_tag in (tgt_tag, "*")
        if src_match and tgt_match:
            return {
                "verdict": policy.action,
                "policy_id": policy.id,
                "source_tag": src_tag,
                "target_tag": tgt_tag,
            }

    # Default zero-trust: deny if no explicit allow policy
    return {
        "verdict": "deny",
        "policy_id": None,
        "source_tag": src_tag,
        "target_tag": tgt_tag,
        "reason": "no matching policy (zero-trust default)",
    }


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
