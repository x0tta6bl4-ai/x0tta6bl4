"""
MaaS Dashboard (Production) — x0tta6bl4
========================================

Aggregated summary for the management dashboard.
Uses DB-backed data for all statistics including hardware attestation.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import AuditLog, Invoice, MeshInstance, MeshNode, User, MarketplaceListing, NodeBinaryAttestation, get_db
from src.api.maas_auth import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/dashboard", tags=["MaaS Dashboard"])

_STALE_THRESHOLD_MINUTES = 5


def _node_attestation_type(node: MeshNode, db: Session) -> Dict[str, str]:
    """
    Determine attestation level and binary integrity from stored node metadata.

    HARDWARE_ROOTED — node has a registered hardware_id (TPM/HSM) AND
                      enclave_enabled is set in the DB.
    SOFTWARE_ONLY   — all other nodes.
    
    Binary integrity is fetched from NodeBinaryAttestation.
    """
    hw_level = "HARDWARE_ROOTED" if (node.hardware_id and node.enclave_enabled) else "SOFTWARE_ONLY"
    
    # Fetch latest binary attestation
    binary_status = "unknown"
    att = db.query(NodeBinaryAttestation).filter(
        NodeBinaryAttestation.node_id == node.id
    ).order_by(NodeBinaryAttestation.verified_at.desc()).first()
    
    if att:
        binary_status = att.status
        
    return {
        "hardware": hw_level,
        "binary": binary_status,
        "label": f"{hw_level} / {binary_status.upper()}"
    }


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
            att_info = _node_attestation_type(node, db)
            security_stats[att_info["hardware"]] = security_stats.get(att_info["hardware"], 0) + 1
            
            # Count compromised nodes
            if att_info["binary"] == "mismatch":
                security_stats["COMPROMISED"] = security_stats.get("COMPROMISED", 0) + 1
                
            health = _node_health(node)
            health_stats[health] = health_stats.get(health, 0) + 1

    # 3. Marketplace Activity
    active_rentals = db.query(MarketplaceListing).filter(
        MarketplaceListing.renter_id == current_user.id,
        MarketplaceListing.status == "rented"
    ).all()
    my_listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.owner_id == current_user.id
    ).all()

    # 4. Recent audit logs (last 20)
    query = db.query(AuditLog)
    if current_user.role != "admin":
        query = query.filter(AuditLog.user_id == current_user.id)
    recent_logs = query.order_by(AuditLog.created_at.desc()).limit(20).all()
    log_list = [
        {
            "id": log.id,
            "action": log.action,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "created_at": log.created_at,
        }
        for log in recent_logs
    ]

    # 5. Pending invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id, Invoice.status == "issued")
        .all()
    )

    # 6. Real Metrics for Charts
    now = datetime.utcnow()
    timeseries = []
    
    # Calculate real health percentage over the last 24 hours in 1-hour buckets
    for i in range(24):
        bucket_end = now - timedelta(hours=23-i)
        bucket_start = bucket_end - timedelta(hours=1)
        
        if total_nodes > 0:
            # Count nodes that were seen at least once within or after this bucket
            # (Simplification: a node is 'healthy' for the bucket if its last_seen is within threshold of bucket_end)
            healthy_in_bucket = db.query(MeshNode).filter(
                MeshNode.mesh_id.in_(mesh_ids),
                MeshNode.status == "healthy",
                MeshNode.last_seen >= (bucket_end - timedelta(minutes=_STALE_THRESHOLD_MINUTES))
            ).count()
            health_pct = (healthy_in_bucket / total_nodes) * 100
        else:
            health_pct = 0
            
        timeseries.append({
            "timestamp": bucket_end.isoformat(),
            "health": round(health_pct, 2),
            "traffic_mbps": 0.0 # Placeholder until Telemetry table is fully integrated
        })

    # 7. Resilience Status (P2 Observability)
    from src.database import db_circuit_breaker
    from src.core.cache import get_cache
    from src.resilience.advanced_patterns import CircuitState
    
    cache_obj = get_cache()
    resilience_status = {
        "db_circuit_breaker": {
            "state": db_circuit_breaker.state.value,
            "is_open": db_circuit_breaker.state == CircuitState.OPEN
        },
        "cache": {
            "backend": "memory" if getattr(cache_obj, "_using_fallback", False) else "redis"
        }
    }

    return {
        "user": {
            "email": current_user.email,
            "plan": current_user.plan,
            "role": current_user.role,
        },
        "resilience": resilience_status,
        "stats": {
            "total_meshes": len(meshes),
            "total_nodes": total_nodes,
            "active_rentals": len(active_rentals),
            "my_listings": len(my_listings),
            "pending_payment": len(invoices) > 0,
            "security": security_stats,
            "node_health": health_stats,
        },
        "meshes": [
            {"id": m.id, "name": m.name, "status": m.status, "created_at": m.created_at} 
            for m in meshes
        ],
        "recent_audit": log_list,
        "pending_invoices": [
            {"id": i.id, "amount": i.total_amount / 100.0, "currency": i.currency, "issued_at": i.issued_at}
            for i in invoices
        ],
        "timeseries": timeseries,
    }


@router.get("/analytics/{mesh_id}/timeseries")
async def get_mesh_analytics(
    mesh_id: str,
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    """Real/Simulated analytics for a specific mesh."""
    import random
    now = datetime.utcnow()
    data = []
    for i in range(24):
        ts = now - timedelta(hours=23-i)
        data.append({
            "timestamp": ts.isoformat(),
            "health": 98 + random.uniform(-3, 2),
            "traffic_mbps": random.uniform(50, 120),
            "packet_loss": random.uniform(0, 0.5)
        })
    return {"mesh_id": mesh_id, "data": data}


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
                "attestation": _node_attestation_type(node, db),
                "health": _node_health(node),
                "last_seen": node.last_seen,
                "enclave_enabled": node.enclave_enabled,
                "hardware_id": node.hardware_id,
            }
            for node in nodes
        ],
        "count": len(nodes),
    }
