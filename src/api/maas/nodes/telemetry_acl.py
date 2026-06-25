"""
MaaS Node Telemetry and ACL - telemetry readback and server-side ACL.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import ACLPolicy, MeshInstance, MeshNode, User
from src.core.security.rbac import MeshPermission
from .security import (
    ensure_mesh_visibility,
)

logger = logging.getLogger(__name__)

# --- External Telemetry Helpers (mocked or imported) ---
try:
    from src.api.maas.endpoints.telemetry import (_get_telemetry as _read_external_telemetry,
                                      _get_telemetry_history as _read_external_telemetry_history)
except ImportError:
    _read_external_telemetry = lambda x: {}
    _read_external_telemetry_history = lambda x, limit=20: []


def _ensure_owner_or_admin_access(
    mesh_id: str,
    current_user: User,
    db: Session,
    required_permission: MeshPermission,
    *,
    allow_admin_without_mesh: bool = False,
) -> Optional[MeshInstance]:
    """Enforce owner-scoped visibility for sensitive node routes."""
    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not mesh:
        if allow_admin_without_mesh and current_user.role == "admin":
            return None
        if allow_admin_without_mesh:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: mesh metadata unavailable",
            )
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    if current_user.role == "admin":
        return mesh
        
    if mesh.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mesh not found")
        
    return mesh


def get_node_telemetry_data(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
    history_limit: int = 20,
) -> Dict[str, Any]:
    """Return node telemetry snapshot + recent history."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    _ensure_owner_or_admin_access(
        mesh_id,
        current_user,
        db,
        MeshPermission.TELEMETRY_READ,
        allow_admin_without_mesh=True,
    )

    snapshot = _read_external_telemetry(node_id)
    history = _read_external_telemetry_history(node_id, limit=history_limit)

    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "node_status": node.status,
        "last_seen": node.last_seen.isoformat() if node.last_seen else None,
        "snapshot": snapshot,
        "history": history,
        "history_count": len(history),
    }


class AccessCheckRequest(BaseModel):
    source_node_id: str
    target_node_id: str


def check_node_access(
    mesh_id: str,
    req: AccessCheckRequest,
    db: Session,
    current_user: User,
) -> Dict[str, Any]:
    """Server-side ACL enforcement."""
    src_node = db.query(MeshNode).filter(
        MeshNode.id == req.source_node_id, MeshNode.mesh_id == mesh_id
    ).first()
    tgt_node = db.query(MeshNode).filter(
        MeshNode.id == req.target_node_id, MeshNode.mesh_id == mesh_id
    ).first()

    if not src_node or not tgt_node:
        raise HTTPException(status_code=404, detail="One or both nodes not found in this mesh")

    _ensure_owner_or_admin_access(
        mesh_id,
        current_user,
        db,
        MeshPermission.ACL_READ,
        allow_admin_without_mesh=True,
    )

    # Only approved nodes are allowed to pass ACL checks.
    if src_node.status != "approved" or tgt_node.status != "approved":
        return {
            "verdict": "deny",
            "policy_id": None,
            "source_tag": src_node.acl_profile or "default",
            "target_tag": tgt_node.acl_profile or "default",
            "reason": "source or target node is not approved",
        }

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


def get_node_agent_config(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User | None = None,
) -> Dict[str, Any]:
    """Fetch allowed policies and peer tags for an agent."""
    if current_user is not None:
        ensure_mesh_visibility(mesh_id, current_user, db)
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Fetch all policies for this mesh
    policies = db.query(ACLPolicy).filter(ACLPolicy.mesh_id == mesh_id).all()
    
    # Fetch all approved peers
    peers = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id, MeshNode.status == "approved").all()
    
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


def list_all_mesh_nodes(
    mesh_id: str,
    db: Session,
    current_user: User,
    node_status: Optional[str] = None,
) -> Dict[str, Any]:
    """List all nodes in a mesh with optional status filter."""
    ensure_mesh_visibility(mesh_id, current_user, db)
    query = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id)
    if node_status:
        query = query.filter(MeshNode.status == node_status)
    
    nodes = query.all()
    return {
        "mesh_id": mesh_id,
        "nodes": nodes,
        "count": len(nodes)
    }
