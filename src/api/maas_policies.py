"""
MaaS ACL Policies (Production) — x0tta6bl4
=========================================

Zero-trust policy management backed by SQLAlchemy.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import User, ACLPolicy, get_db
from src.api.maas_auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Policies"])

class PolicyRequest(BaseModel):
    source_tag: str = Field(..., min_length=1)
    target_tag: str = Field(..., min_length=1)
    action: str = Field(default="allow", pattern="^(allow|deny)$")

class PolicyResponse(BaseModel):
    id: str
    mesh_id: str
    source_tag: str
    target_tag: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True

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
