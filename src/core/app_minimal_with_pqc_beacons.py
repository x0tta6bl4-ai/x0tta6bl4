"""
x0tta6bl4 Minimal App with PQC Beacon Signatures
Enhanced version with Dilithium signatures for Byzantine fault tolerance.
"""
from __future__ import annotations

import asyncio
import logging
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

# Try to import liboqs for PQC signatures
try:
    from oqs import Signature
    LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs available - PQC signatures enabled")
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - beacon signatures disabled")

app = FastAPI(title="x0tta6bl4-minimal-pqc", version="3.0.0", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0
HEALTH_CHECK_INTERVAL = 5.0

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: set = set()

# PQC Signature keys (if liboqs available)
_sig_public_key: Optional[bytes] = None
_sig_private_key: Optional[bytes] = None
_peer_public_keys: Dict[str, bytes] = {}  # peer_id -> public_key

# Initialize PQC signature if available
if LIBOQS_AVAILABLE:
    try:
        sig = Signature("Dilithium3")
        _sig_public_key, _sig_private_key = sig.generate_keypair()
        logger.info("✅ PQC signature keypair generated (Dilithium3)")
    except Exception as e:
        logger.error(f"Failed to generate PQC keys: {e}")
        LIBOQS_AVAILABLE = False

# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []
    signature: Optional[str] = None  # Hex-encoded signature
    public_key: Optional[str] = None  # Hex-encoded public key (first beacon only)

class RouteRequest(BaseModel):
    destination: str
    payload: str

# --- PQC Functions ---

def sign_beacon(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        sig = Signature("Dilithium3")
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

def verify_beacon(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        sig = Signature("Dilithium3")
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def get_beacon_data(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

# --- Background Tasks ---

async def health_check_loop():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "node_id": node_id,
        "pqc_enabled": LIBOQS_AVAILABLE,
        "peers_count": len(peers)
    }

@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon from another node with PQC signature verification.
    
    Byzantine Fault Tolerance: Verifies signature before accepting beacon.
    """
    global peers, dead_peers, _peer_public_keys
    
    # Serialize beacon data for verification
    beacon_data = get_beacon_data(
        req.node_id,
        req.timestamp,
        req.neighbors or []
    )
    
    # Verify signature if PQC is available
    if LIBOQS_AVAILABLE:
        if not req.signature or not req.public_key:
            logger.warning(f"⚠️ Beacon from {req.node_id} has no signature - rejecting")
            raise HTTPException(
                status_code=400,
                detail="Beacon must include signature and public_key when PQC is enabled"
            )
        
        signature = bytes.fromhex(req.signature)
        public_key = bytes.fromhex(req.public_key)
        
        # Store public key if first time seeing this peer
        if req.node_id not in _peer_public_keys:
            _peer_public_keys[req.node_id] = public_key
            logger.info(f"📝 Stored PQC public key for {req.node_id}")
        else:
            # Verify public key hasn't changed (prevent key rotation attacks)
            if _peer_public_keys[req.node_id] != public_key:
                logger.warning(f"⚠️ Public key changed for {req.node_id} - possible attack!")
                raise HTTPException(
                    status_code=403,
                    detail="Public key changed - possible Byzantine attack"
                )
        
        # Verify signature
        is_valid = verify_beacon(beacon_data, signature, public_key)
        if not is_valid:
            logger.warning(f"❌ Invalid signature from {req.node_id} - rejecting")
            raise HTTPException(
                status_code=403,
                detail="Invalid beacon signature - possible Byzantine attack"
            )
        
        logger.debug(f"✅ Verified PQC signature from {req.node_id}")
    
    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED")
    
    # Register/update peer
    peers[req.node_id] = {
        "last_seen": time.time(),
        "neighbors": req.neighbors or []
    }
    
    beacons_received.append({
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time(),
        "signature_verified": LIBOQS_AVAILABLE
    })
    
    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "signature_verified": LIBOQS_AVAILABLE
    }

@app.get("/mesh/beacon/sign")
async def get_signed_beacon(neighbors: Optional[str] = None):
    """
    Generate a signed beacon for this node.
    
    Useful for testing and for other nodes to get our public key.
    """
    if not LIBOQS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PQC signatures not available (liboqs not installed)"
        )
    
    neighbors_list = neighbors.split(",") if neighbors else []
    timestamp = time.time()
    
    # Serialize beacon data
    beacon_data = get_beacon_data(node_id, timestamp, neighbors_list)
    
    # Sign beacon
    signature = sign_beacon(beacon_data)
    
    return {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": neighbors_list,
        "signature": signature.hex(),
        "public_key": _sig_public_key.hex() if _sig_public_key else None
    }

@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with PQC status."""
    current_time = time.time()
    peer_status = {}
    
    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT
        has_pqc_key = peer_id in _peer_public_keys
        
        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", []),
            "has_pqc_key": has_pqc_key
        }
    
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers),
        "pqc_enabled": LIBOQS_AVAILABLE
    }

@app.get("/mesh/status")
async def get_status():
    """Get mesh status with PQC info."""
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "beacons_received": len(beacons_received),
        "pqc_enabled": LIBOQS_AVAILABLE,
        "pqc_algorithm": "Dilithium3" if LIBOQS_AVAILABLE else None,
        "peers_with_pqc": len(_peer_public_keys)
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
    
    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead"
        }
    
    if req.destination in peers:
        latency = random.uniform(10, 50)
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": latency,
            "path": [node_id, req.destination]
        }
    
    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}"
    }

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with PQC stats."""
    import os
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_bytes = mem_info.rss
    except:
        memory_bytes = 0
    
    current_time = time.time()
    alive_peers = sum(
        1 for p in peers.values()
        if (current_time - p.get("last_seen", 0)) < PEER_TIMEOUT
    )
    
    metrics_str = f"""# HELP mesh_peers_count Number of known peers
# TYPE mesh_peers_count gauge
mesh_peers_count {len(peers)}

# HELP mesh_dead_peers_count Number of dead peers
# TYPE mesh_dead_peers_count gauge
mesh_dead_peers_count {len(dead_peers)}

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP mesh_pqc_enabled PQC signatures enabled (1=yes, 0=no)
# TYPE mesh_pqc_enabled gauge
mesh_pqc_enabled {1 if LIBOQS_AVAILABLE else 0}

# HELP mesh_peers_with_pqc Number of peers with PQC keys
# TYPE mesh_peers_with_pqc gauge
mesh_peers_with_pqc {len(_peer_public_keys)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str

@app.on_event("startup")
async def startup():
    """Start background tasks."""
    global node_id
    import os
    
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with PQC beacons started as {node_id}")
    
    if LIBOQS_AVAILABLE:
        logger.info("🔐 PQC beacon signatures enabled (Dilithium3)")
    else:
        logger.warning("⚠️ PQC beacon signatures disabled (liboqs not available)")
    
    # Start background tasks
    asyncio.create_task(health_check_loop())
    logger.info("✅ Background tasks started: health_check")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

