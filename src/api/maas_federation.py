"""
Mesh Federation API — x0tta6bl4
================================

Enables multi-region and inter-tenant mesh connectivity.
Federation allows two separate mesh instances to exchange routes and trust,
creating a secure bridge between isolated environments.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.database import get_db, MeshInstance, MeshFederation, User
from src.api.maas_auth import get_current_user_from_maas, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/federation", tags=["federation"])

class FederationRequest(BaseModel):
    target_mesh_id: str = Field(..., description="ID of the mesh to federate with")
    policy: str = Field(default="allow_all", description="Access policy for the federation link")

class FederationResponse(BaseModel):
    id: str
    source_mesh_id: str
    target_mesh_id: str
    status: str
    policy: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/{mesh_id}/link", response_model=FederationResponse)
async def create_federation_link(
    mesh_id: str,
    req: FederationRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """
    Request a federation link with another mesh instance.
    If the meshes belong to the same tenant/owner, it auto-approves.
    Otherwise, it requires approval from the target mesh owner.
    """
    source_mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not source_mesh:
        raise HTTPException(status_code=404, detail="Source mesh not found")
        
    if source_mesh.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to modify this mesh")

    target_mesh = db.query(MeshInstance).filter(MeshInstance.id == req.target_mesh_id).first()
    if not target_mesh:
        raise HTTPException(status_code=404, detail="Target mesh not found")

    # Check if already federated
    existing = db.query(MeshFederation).filter(
        ((MeshFederation.source_mesh_id == mesh_id) & (MeshFederation.target_mesh_id == req.target_mesh_id)) |
        ((MeshFederation.source_mesh_id == req.target_mesh_id) & (MeshFederation.target_mesh_id == mesh_id))
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Federation link already exists")

    # Determine initial status
    link_status = "active" if source_mesh.tenant_id == target_mesh.tenant_id else "pending"

    federation = MeshFederation(
        id=f"fed-{uuid.uuid4().hex[:12]}",
        source_mesh_id=mesh_id,
        target_mesh_id=req.target_mesh_id,
        status=link_status,
        policy=req.policy
    )
    db.add(federation)
    db.commit()
    db.refresh(federation)
    
    logger.info(f"🔗 Federation link created: {mesh_id} -> {req.target_mesh_id} (Status: {link_status})")
    
    return federation

@router.get("/{mesh_id}/links", response_model=List[FederationResponse])
async def list_federations(
    mesh_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """List all federation links for a given mesh."""
    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not mesh:
        raise HTTPException(status_code=404, detail="Mesh not found")
        
    if mesh.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    links = db.query(MeshFederation).filter(
        (MeshFederation.source_mesh_id == mesh_id) | (MeshFederation.target_mesh_id == mesh_id)
    ).all()
    
    return links

@router.post("/{federation_id}/approve", response_model=FederationResponse)
async def approve_federation(
    federation_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Approve a pending federation request."""
    federation = db.query(MeshFederation).filter(MeshFederation.id == federation_id).first()
    if not federation:
        raise HTTPException(status_code=404, detail="Federation link not found")
        
    target_mesh = db.query(MeshInstance).filter(MeshInstance.id == federation.target_mesh_id).first()
    if not target_mesh or (target_mesh.owner_id != current_user.id and current_user.role != "admin"):
        raise HTTPException(status_code=403, detail="Not authorized to approve this link")
        
    if federation.status != "pending":
        raise HTTPException(status_code=400, detail=f"Link is already {federation.status}")

    federation.status = "active"
    db.commit()
    db.refresh(federation)
    
    logger.info(f"✅ Federation link approved: {federation_id}")
    return federation

@router.delete("/{federation_id}")
async def revoke_federation(
    federation_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
):
    """Revoke/Delete a federation link."""
    federation = db.query(MeshFederation).filter(MeshFederation.id == federation_id).first()
    if not federation:
        raise HTTPException(status_code=404, detail="Federation link not found")
        
    source_mesh = db.query(MeshInstance).filter(MeshInstance.id == federation.source_mesh_id).first()
    target_mesh = db.query(MeshInstance).filter(MeshInstance.id == federation.target_mesh_id).first()
    
    # Allow either side to revoke
    is_owner = False
    if source_mesh and source_mesh.owner_id == current_user.id:
        is_owner = True
    if target_mesh and target_mesh.owner_id == current_user.id:
        is_owner = True
        
    if not is_owner and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to revoke this link")

    federation.status = "revoked"
    db.commit()
    
    logger.info(f"🚫 Federation link revoked: {federation_id}")
    return {"status": "success", "message": "Federation link revoked"}