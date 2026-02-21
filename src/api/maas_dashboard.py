
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from src.database import User, MeshInstance, Invoice, AuditLog, get_db
from src.api.maas_auth import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/dashboard", tags=["MaaS Dashboard"])

@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(require_permission("mesh:view")),
    db: Session = Depends(get_db)
):
    """
    Aggregated summary for the MaaS Dashboard.
    Returns meshes, recent audit logs, and billing status.
    """
    # 1. Get user's meshes
    meshes = db.query(MeshInstance).filter(MeshInstance.owner_id == current_user.id).all()
    mesh_list = []
    security_stats = {"HARDWARE_ROOTED": 0, "SOFTWARE_ONLY": 0}
    
    # Try to access in-memory registry for real-time node data
    try:
        from src.api.maas_legacy import mesh_provisioner
    except ImportError:
        mesh_provisioner = None

    for m in meshes:
        nodes_data = []
        if mesh_provisioner:
            instance = mesh_provisioner.get(m.id)
            if instance:
                for nid, n in instance.node_instances.items():
                    sec_level = n.get("pqc_profile", {}).get("security_level", 0) # Use profile for now
                    # Or check for attestation explicitly if stored
                    sec_type = n.get("security_level", "SOFTWARE_ONLY")
                    security_stats[sec_type] = security_stats.get(sec_type, 0) + 1

        mesh_list.append({
            "id": m.id,
            "name": m.name,
            "status": m.status,
            "created_at": m.created_at
        })

    # 2. Get recent audit logs (last 10)
    # If user is admin, show all logs. If user, show only their logs.
    query = db.query(AuditLog)
    if current_user.role != "admin":
        query = query.filter(AuditLog.user_id == current_user.id)
    
    recent_logs = query.order_by(AuditLog.created_at.desc()).limit(10).all()
    log_list = []
    for log in recent_logs:
        log_list.append({
            "id": log.id,
            "action": log.action,
            "status_code": log.status_code,
            "created_at": log.created_at
        })

    # 3. Get pending invoices
    invoices = db.query(Invoice).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == "issued"
    ).all()
    invoice_list = []
    for inv in invoices:
        invoice_list.append({
            "id": inv.id,
            "amount": inv.total_amount / 100.0,
            "currency": inv.currency,
            "issued_at": inv.issued_at
        })

    return {
        "user": {
            "email": current_user.email,
            "plan": current_user.plan,
            "role": current_user.role
        },
        "meshes": mesh_list,
        "recent_audit": log_list,
        "pending_invoices": invoice_list,
        "stats": {
            "total_meshes": len(mesh_list),
            "pending_payment": len(invoice_list) > 0,
            "security": security_stats
        }
    }
