"""
MaaS Telemetry (Production - Redis backed) — x0tta6bl4
======================================================

High-frequency telemetry storage using Redis for scalability.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import MeshNode, MeshInstance, get_db
from src.api.maas_auth import get_current_user_from_maas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Telemetry"])

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    r_client = redis.from_url(REDIS_URL, decode_responses=True)
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to memory.")
    r_client = {}
    REDIS_AVAILABLE = False

class NodeHeartbeatRequest(BaseModel):
    node_id: str
    cpu_usage: float
    memory_usage: float
    neighbors_count: int
    routing_table_size: int
    uptime: float
    pheromones: Optional[Dict[str, Dict[str, float]]] = None

def _set_telemetry(node_id: str, data: Dict):
    key = f"maas:telemetry:{node_id}"
    if REDIS_AVAILABLE:
        r_client.setex(key, 300, json.dumps(data)) # 5 min TTL
    else:
        r_client[key] = data

def _get_telemetry(node_id: str) -> Dict:
    key = f"maas:telemetry:{node_id}"
    if REDIS_AVAILABLE:
        raw = r_client.get(key)
        return json.loads(raw) if raw else {}
    return r_client.get(key, {})

@router.post("/heartbeat")
async def heartbeat(
    req: NodeHeartbeatRequest,
    db: Session = Depends(get_db)
):
    node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
    if not node:
        logger.warning(f"🚨 UNKNOWN NODE HEARTBEAT: {req.node_id}")
        raise HTTPException(status_code=404, detail="Node not registered")
    
    # Fast DB update
    node.status = "healthy"
    db.commit()
    
    # Store high-frequency data in Redis
    telemetry_data = {
        "cpu": req.cpu_usage,
        "mem": req.memory_usage,
        "neighbors": req.neighbors_count,
        "uptime": req.uptime,
        "last_seen": datetime.utcnow().isoformat()
    }
    _set_telemetry(req.node_id, telemetry_data)
    
    return {"status": "ack", "mesh_id": node.mesh_id}

@router.get("/{mesh_id}/topology")
async def get_topology(
    mesh_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_maas)
):
    """Returns nodes and links for the D3.js dashboard from Redis."""
    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    
    result_nodes = []
    for n in nodes:
        telemetry = _get_telemetry(n.id)
        result_nodes.append({
            "id": n.id,
            "class": n.device_class,
            "status": "healthy" if telemetry else "offline",
            "telemetry": telemetry
        })
        
    return {"nodes": result_nodes, "links": []}
