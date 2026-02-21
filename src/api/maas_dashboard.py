"""
MaaS Dashboard (Production) — x0tta6bl4
========================================

Aggregated summary for the management dashboard.
Uses DB-backed data for all statistics including hardware attestation.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import AuditLog, Invoice, MeshInstance, MeshNode, User, get_db
from src.api.maas_auth import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/dashboard", tags=["MaaS Dashboard"])

_STALE_THRESHOLD_MINUTES = 5


def _node_attestation_type(node: MeshNode) -> str:
    """
    Determine attestation level from stored node metadata.

    HARDWARE_ROOTED — node has a registered hardware_id (TPM/HSM) AND
                      enclave_enabled is set in the DB.
    SOFTWARE_ONLY   — all other nodes.
    """
    if node.hardware_id and node.enclave_enabled:
        return "HARDWARE_ROOTED"
    return "SOFTWARE_ONLY"


def _node_health(node: MeshNode) -> str:
    """
    Return 'healthy', 'stale', or 'offline' based on last_seen timestamp.
    A node without last_seen is treated as 'unknown'.
    """
    if node.last_seen is None:
        return "unknown"
    age = datetime.utcnow() - node.last_seen
    if age <= timedelta(minutes=_STALE_THRESHOLD_MINUTES):
        return "healthy"
    if age <= timedelta(minutes=30):
        return "stale"
    return "offline"


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(require_permission("mesh:view")),
    db: Session = Depends(get_db),
):
    """
    Aggregated summary for the MaaS Dashboard.
    Returns meshes, node attestation stats, recent audit logs, and billing status.
    """
    # 1. Meshes owned by this user
    meshes = db.query(MeshInstance).filter(MeshInstance.owner_id == current_user.id).all()
    mesh_ids = [m.id for m in meshes]

    # 2. Node stats across all meshes (DB-backed)
    security_stats: Dict[str, int] = {"HARDWARE_ROOTED": 0, "SOFTWARE_ONLY": 0}
    health_stats: Dict[str, int] = {"healthy": 0, "stale": 0, "offline": 0, "unknown": 0}
    total_nodes = 0

    if mesh_ids:
        nodes = (
            db.query(MeshNode)
            .filter(MeshNode.mesh_id.in_(mesh_ids), MeshNode.status != "revoked")
            .all()
        )
        for node in nodes:
            total_nodes += 1
            att = _node_attestation_type(node)
            security_stats[att] = security_stats.get(att, 0) + 1
            health = _node_health(node)
            health_stats[health] = health_stats.get(health, 0) + 1

    mesh_list = [
        {
            "id": m.id,
            "name": m.name,
            "status": m.status,
            "pqc_enabled": m.pqc_enabled,
            "created_at": m.created_at,
        }
        for m in meshes
    ]

    # 3. Recent audit logs (last 10)
    query = db.query(AuditLog)
    if current_user.role != "admin":
        query = query.filter(AuditLog.user_id == current_user.id)
    recent_logs = query.order_by(AuditLog.created_at.desc()).limit(10).all()
    log_list = [
        {
            "id": log.id,
            "action": log.action,
            "status_code": log.status_code,
            "created_at": log.created_at,
        }
        for log in recent_logs
    ]

    # 4. Pending invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id, Invoice.status == "issued")
        .all()
    )
    invoice_list = [
        {
            "id": inv.id,
            "amount": inv.total_amount / 100.0,
            "currency": inv.currency,
            "issued_at": inv.issued_at,
        }
        for inv in invoices
    ]

    return {
        "user": {
            "email": current_user.email,
            "plan": current_user.plan,
            "role": current_user.role,
        },
        "meshes": mesh_list,
        "recent_audit": log_list,
        "pending_invoices": invoice_list,
        "stats": {
            "total_meshes": len(mesh_list),
            "total_nodes": total_nodes,
            "pending_payment": len(invoice_list) > 0,
            "security": security_stats,
            "node_health": health_stats,
        },
    }


@router.get("/nodes/{mesh_id}")
async def get_mesh_nodes_summary(
    mesh_id: str,
    current_user: User = Depends(require_permission("mesh:view")),
    db: Session = Depends(get_db),
):
    """Per-mesh node listing with attestation and health details."""
    mesh = db.query(MeshInstance).filter(
        MeshInstance.id == mesh_id,
        MeshInstance.owner_id == current_user.id,
    ).first()
    if not mesh:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Mesh not found")

    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    return {
        "mesh_id": mesh_id,
        "mesh_name": mesh.name,
        "nodes": [
            {
                "id": node.id,
                "status": node.status,
                "device_class": node.device_class,
                "attestation": _node_attestation_type(node),
                "health": _node_health(node),
                "last_seen": node.last_seen,
                "enclave_enabled": node.enclave_enabled,
                "hardware_id": node.hardware_id,
            }
            for node in nodes
        ],
        "count": len(nodes),
    }
