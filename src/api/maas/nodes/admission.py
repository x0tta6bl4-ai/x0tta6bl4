"""
MaaS Node Admission - registration, approval, and lifecycle management.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.database import MeshInstance, MeshNode, User
from src.api.maas_security import token_signer
from .security import MeshOperator, ensure_mesh_visibility

logger = logging.getLogger(__name__)


def register_node(
    mesh_id: str,
    enrollment_token: str,
    db: Session,
    node_id: Optional[str] = None,
    device_class: str = "edge",
    hardware_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new node (pending approval)."""
    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    if not instance.join_token:
        raise HTTPException(status_code=503, detail="Mesh enrollment token is not configured")
    if instance.join_token_expires_at and instance.join_token_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Enrollment token expired")

    if not hmac.compare_digest(enrollment_token, instance.join_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    node_id = node_id or f"node-{uuid.uuid4().hex[:6]}"
    
    # Check if node already exists
    existing = db.query(MeshNode).filter(MeshNode.id == node_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Node ID already registered")

    node = MeshNode(
        id=node_id,
        mesh_id=mesh_id,
        device_class=device_class,
        hardware_id=hardware_id,
        status="pending"
    )
    db.add(node)
    db.commit()
    
    logger.info(f"🆕 Node {node_id} registered (pending) for mesh {mesh_id}")
    return {"status": "pending_approval", "node_id": node_id}


def list_pending_nodes(
    mesh_id: str,
    current_user: User,
    db: Session,
) -> List[MeshNode]:
    """List nodes awaiting approval."""
    ensure_mesh_visibility(mesh_id, current_user, db)
    return db.query(MeshNode).filter(
        MeshNode.mesh_id == mesh_id, 
        MeshNode.status == "pending"
    ).all()


def approve_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
    attestation_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Approve a pending node to join the mesh."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Hardware Attestation Enforcement
    if node.enclave_enabled:
        if not attestation_data:
            raise HTTPException(status_code=400, detail="Hardware attestation required for this node")
        
        from src.security.tee_attestation import TEEValidator, TEEAttestation
        tee_validator = TEEValidator(dev_mode=True)
        
        att = TEEAttestation(
            provider=attestation_data.get("provider", "mock"),
            report_data=attestation_data.get("report_data", "").encode(),
            quote=attestation_data.get("quote", "").encode() if attestation_data.get("quote") else None
        )
        
        if not tee_validator.verify_report(att):
            logger.error(f"❌ TEE Attestation failed for node {node_id}")
            raise HTTPException(status_code=403, detail="Invalid hardware attestation report")
        
        logger.info(f"✅ TEE Attestation verified for node {node_id}")

    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    if not instance.join_token:
        raise HTTPException(status_code=503, detail="Mesh enrollment token is not configured")
    if instance.join_token_expires_at and instance.join_token_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=409, detail="Mesh enrollment token expired")

    node_status = (node.status or "").lower()
    if node_status == "approved":
        signed = token_signer.sign_token(instance.join_token, mesh_id)
        return {
            "status": "approved",
            "join_token": signed,
            "already_approved": True,
        }
    if node_status not in {"pending", "pending_approval"}:
        raise HTTPException(
            status_code=409,
            detail=f"Node cannot be approved from status '{node.status}'",
        )

    node.status = "approved"
    db.commit()

    signed = token_signer.sign_token(instance.join_token, mesh_id)
    
    logger.info(f"✅ Node {node_id} approved by user {current_user.id}")
    return {
        "status": "approved",
        "join_token": signed
    }


def revoke_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
) -> Dict[str, str]:
    """Revoke a node's access."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.status = "revoked"
    db.commit()
    logger.info(f"🔒 Node {node_id} revoked by user {current_user.id}")
    return {"status": "revoked", "node_id": node_id}


def delete_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
) -> Dict[str, str]:
    """Permanently delete a node."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    db.delete(node)
    db.commit()
    logger.info(f"🗑️ Node {node_id} deleted by user {current_user.id}")
    return {"status": "deleted", "node_id": node_id}
