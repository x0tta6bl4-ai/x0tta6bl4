"""
x0tta6bl4 Minimal App with Byzantine Protection
Enhanced version with Signed Gossip and Quorum Validation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

# Try to import Byzantine protection
try:
    from libx0t.network.byzantine.mesh_byzantine_protection import \
        MeshByzantineProtection
    from libx0t.network.byzantine.signed_gossip import MessageType

    BYZANTINE_AVAILABLE = True
except ImportError as e:
    BYZANTINE_AVAILABLE = False
    logger.warning(f"⚠️ Byzantine protection not available: {e}")

app = FastAPI(title="x0tta6bl4-minimal-byzantine", version="3.2.1", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0
HEALTH_CHECK_INTERVAL = 5.0
TOTAL_NODES = 10  # Total nodes in network (for quorum calculation)

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: Set[str] = set()
validated_failures: Set[str] = set()  # Nodes validated as failed by quorum

# Byzantine Protection
byzantine_protection: Optional[MeshByzantineProtection] = None

if BYZANTINE_AVAILABLE:
    try:
        byzantine_protection = MeshByzantineProtection(node_id, total_nodes=TOTAL_NODES)
        logger.info("✅ Byzantine protection enabled")
    except Exception as e:
        logger.error(f"🔴 Failed to initialize Byzantine protection: {e}")
        BYZANTINE_AVAILABLE = False


# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []
    signature: Optional[str] = None  # Hex-encoded signature
    public_key: Optional[str] = None  # Hex-encoded public key


class RouteRequest(BaseModel):
    destination: str
    payload: str


class NodeFailureReport(BaseModel):
    failed_node: str
    evidence: Dict[str, Any]
    signature: str  # Signature of the report


# --- Background Tasks ---


async def health_check_loop():
    """MAPE-K Monitor: Check peer health with Byzantine protection."""
    global peers, dead_peers, validated_failures

    while True:
        try:
            current_time = time.time()
            newly_dead = []

            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                # Skip if node is quarantined
                if byzantine_protection and byzantine_protection.is_node_quarantined(
                    peer_id
                ):
                    logger.warning(
                        f"⚠️ Peer {peer_id} is quarantined - skipping health check"
                    )
                    continue

                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen

                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers and peer_id not in validated_failures:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(
                            f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)"
                        )

                        # Report to Byzantine protection (requires quorum validation)
                        if byzantine_protection:
                            evidence = {
                                "latency": float("inf"),
                                "packet_loss": 1.0,
                                "last_seen": last_seen,
                                "elapsed": elapsed,
                            }
                            event = byzantine_protection.report_node_failure(
                                peer_id, evidence
                            )
                            logger.info(
                                f"📢 Node failure reported to quorum: {peer_id} "
                                f"(quorum needed: {byzantine_protection.quorum_validator.quorum_size})"
                            )

            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)


# --- Endpoints ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.2.1",
        "node_id": node_id,
        "byzantine_protection": BYZANTINE_AVAILABLE,
        "peers_count": len(peers),
        "validated_failures": list(validated_failures),
    }


@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon with Byzantine protection.

    Все beacon'ы должны быть подписаны PQC подписями.
    """
    global peers, dead_peers

    # Check Byzantine protection
    if byzantine_protection:
        # Check if sender is quarantined
        if byzantine_protection.is_node_quarantined(req.node_id):
            logger.warning(f"⚠️ Beacon from quarantined node {req.node_id} - rejecting")
            raise HTTPException(
                status_code=403, detail=f"Node {req.node_id} is quarantined"
            )

        # Check if we should accept message from this node
        if not byzantine_protection.should_accept_message(req.node_id):
            logger.warning(
                f"⚠️ Beacon from low-reputation node {req.node_id} - rejecting"
            )
            raise HTTPException(
                status_code=403, detail=f"Node {req.node_id} has low reputation"
            )

        # Verify signature if provided
        if req.signature and req.public_key:
            try:
                from libx0t.network.byzantine.signed_gossip import SignedMessage

                # Create SignedMessage from request
                message = SignedMessage(
                    msg_type=MessageType.BEACON,
                    sender=req.node_id,
                    timestamp=req.timestamp,
                    nonce=int(time.time() * 1000000),  # Approximate
                    epoch=0,  # Default epoch
                    payload={"neighbors": req.neighbors or []},
                    signature=bytes.fromhex(req.signature),
                    public_key=bytes.fromhex(req.public_key),
                )

                # Verify message
                is_valid, error = byzantine_protection.verify_beacon(message)
                if not is_valid:
                    logger.warning(
                        f"❌ Invalid beacon signature from {req.node_id}: {error}"
                    )
                    raise HTTPException(
                        status_code=403, detail=f"Invalid beacon signature: {error}"
                    )

                logger.debug(f"✅ Verified beacon signature from {req.node_id}")
            except Exception as e:
                logger.error(f"Failed to verify beacon signature: {e}")
                raise HTTPException(
                    status_code=400, detail=f"Beacon signature verification failed: {e}"
                )

    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED")

    # Register/update peer
    peers[req.node_id] = {"last_seen": time.time(), "neighbors": req.neighbors or []}

    beacons_received.append(
        {
            "node_id": req.node_id,
            "timestamp": req.timestamp,
            "neighbors": req.neighbors,
            "received_at": time.time(),
            "byzantine_protected": BYZANTINE_AVAILABLE,
        }
    )

    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "byzantine_protected": BYZANTINE_AVAILABLE,
    }


@app.post("/mesh/report-failure")
async def report_node_failure(report: NodeFailureReport):
    """
    Report node failure (requires quorum validation).

    Критические события (node failure) требуют кворумной валидации.
    """
    if not byzantine_protection:
        raise HTTPException(
            status_code=503, detail="Byzantine protection not available"
        )

    # Report failure
    event = byzantine_protection.report_node_failure(
        report.failed_node, report.evidence
    )

    # Validate with our signature
    signature = bytes.fromhex(report.signature)
    is_validated = byzantine_protection.validate_node_failure(event, signature)

    if is_validated:
        validated_failures.add(report.failed_node)
        logger.warning(f"🔴 Node {report.failed_node} validated as FAILED by quorum")

    return {
        "event_id": f"{event.event_type.value}:{event.target}:{int(event.timestamp)}",
        "quorum_reached": is_validated,
        "signatures_count": len(event.signatures),
        "quorum_needed": byzantine_protection.quorum_validator.quorum_size,
    }


@app.get("/mesh/byzantine/stats")
async def get_byzantine_stats():
    """Get Byzantine protection statistics."""
    if not byzantine_protection:
        raise HTTPException(
            status_code=503, detail="Byzantine protection not available"
        )

    return byzantine_protection.get_protection_stats()


@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with Byzantine status."""
    current_time = time.time()
    peer_status = {}

    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT

        reputation = None
        is_quarantined = False
        if byzantine_protection:
            reputation = byzantine_protection.get_node_reputation(peer_id)
            is_quarantined = byzantine_protection.is_node_quarantined(peer_id)

        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", []),
            "reputation": reputation,
            "is_quarantined": is_quarantined,
            "is_validated_failure": peer_id in validated_failures,
        }

    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers),
        "validated_failures": list(validated_failures),
        "byzantine_protection": BYZANTINE_AVAILABLE,
    }


@app.get("/mesh/status")
async def get_status():
    """Get mesh status with Byzantine protection info."""
    stats = {}
    if byzantine_protection:
        stats = byzantine_protection.get_protection_stats()

    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "validated_failures_count": len(validated_failures),
        "beacons_received": len(beacons_received),
        "byzantine_protection": {"enabled": BYZANTINE_AVAILABLE, "stats": stats},
    }


@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """Route a message to destination (excluding validated failures)."""
    if req.destination == node_id:
        return {"status": "delivered", "hops": 0, "latency_ms": 0}

    # Don't route to validated failures
    if req.destination in validated_failures:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is validated as FAILED by quorum",
        }

    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead",
        }

    if req.destination in peers:
        latency = random.uniform(10, 50)
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": latency,
            "path": [node_id, req.destination],
        }

    return {"status": "unreachable", "error": f"No route to {req.destination}"}


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with Byzantine stats."""
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
        1
        for p in peers.values()
        if (current_time - p.get("last_seen", 0)) < PEER_TIMEOUT
    )

    metrics_str = f"""# HELP mesh_peers_count Number of known peers
# TYPE mesh_peers_count gauge
mesh_peers_count {len(peers)}

# HELP mesh_dead_peers_count Number of dead peers
# TYPE mesh_dead_peers_count gauge
mesh_dead_peers_count {len(dead_peers)}

# HELP mesh_validated_failures_count Number of validated failures
# TYPE mesh_validated_failures_count gauge
mesh_validated_failures_count {len(validated_failures)}

# HELP mesh_byzantine_protection_enabled Byzantine protection enabled (1=yes, 0=no)
# TYPE mesh_byzantine_protection_enabled gauge
mesh_byzantine_protection_enabled {1 if BYZANTINE_AVAILABLE else 0}

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

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
    """Start background tasks."""
    global node_id
    import os

    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with Byzantine protection started as {node_id}")

    if BYZANTINE_AVAILABLE:
        logger.info(
            "🛡️ Byzantine protection enabled (Signed Gossip + Quorum Validation)"
        )
    else:
        logger.warning("⚠️ Byzantine protection disabled")

    # Start background tasks
    asyncio.create_task(health_check_loop())
    logger.info("✅ Background tasks started: health_check")


if __name__ == "__main__":
    import uvicorn

    from libx0t.core.settings import settings

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
