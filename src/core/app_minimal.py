"""
x0tta6bl4 Minimal App for Scenario Testing
Stripped of SPIFFE dependencies for basic mesh testing.
"""
from __future__ import annotations

import asyncio
import logging
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

app = FastAPI(title="x0tta6bl4-minimal", version="3.0.0", docs_url="/docs")

# --- In-Memory State for Testing ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []

# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []

class RouteRequest(BaseModel):
    destination: str
    payload: str

# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "3.0.0", "node_id": node_id}

@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """Receive beacon from another node."""
    beacon = {
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time()
    }
    beacons_received.append(beacon)
    
    # Register peer
    peers[req.node_id] = {
        "last_seen": time.time(),
        "neighbors": req.neighbors
    }
    
    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers)
    }

@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers."""
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peers
    }

@app.get("/mesh/status")
async def get_status():
    """Get mesh status."""
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "beacons_received": len(beacons_received),
        "uptime": time.time()
    }

@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """Route a message to destination."""
    if req.destination == node_id:
        return {
            "status": "delivered",
            "hops": 0,
            "latency_ms": 0
        }
    
    # Simple routing: check if destination is a known peer
    if req.destination in peers:
        # Simulate routing
        latency = random.uniform(10, 50)
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": latency,
            "path": [node_id, req.destination]
        }
    
    # Check neighbors of peers
    for peer_id, peer_info in peers.items():
        if req.destination in peer_info.get("neighbors", []):
            latency = random.uniform(20, 80)
            return {
                "status": "delivered",
                "hops": 2,
                "latency_ms": latency,
                "path": [node_id, peer_id, req.destination]
            }
    
    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}"
    }

@app.get("/mesh/route/{destination}")
async def get_route(destination: str):
    """Get route to destination."""
    if destination == node_id:
        return {"path": [node_id], "hops": 0}
    
    if destination in peers:
        return {"path": [node_id, destination], "hops": 1}
    
    for peer_id, peer_info in peers.items():
        if destination in peer_info.get("neighbors", []):
            return {"path": [node_id, peer_id, destination], "hops": 2}
    
    raise HTTPException(status_code=404, detail=f"No route to {destination}")

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics."""
    import os
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_bytes = mem_info.rss
    except:
        memory_bytes = 0
    
    metrics_str = f"""# HELP mesh_peers_count Number of known peers
# TYPE mesh_peers_count gauge
mesh_peers_count {len(peers)}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str

@app.on_event("startup")
async def startup():
    global node_id
    import os
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal started as {node_id}")

if __name__ == "__main__":
    import uvicorn
    from src.core.settings import settings
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

