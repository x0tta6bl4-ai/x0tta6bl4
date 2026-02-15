"""
x0tta6bl4 Minimal App with Automatic Failover
Enhanced version with peer health monitoring and route recalculation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

app = FastAPI(title="x0tta6bl4-minimal-failover", version="3.0.0", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0  # Seconds without beacon = dead peer
HEALTH_CHECK_INTERVAL = 5.0  # Check peer health every 5 seconds
ROUTE_RECALC_INTERVAL = 10.0  # Recalculate routes every 10 seconds

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: set = set()  # Track dead peers for route recalculation

# Background tasks
_health_check_task: Optional[asyncio.Task] = None
_route_recalc_task: Optional[asyncio.Task] = None


# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []


class RouteRequest(BaseModel):
    destination: str
    payload: str


# --- Background Tasks ---


async def health_check_loop():
    """
    MAPE-K Monitor: Check peer health and prune dead peers.

    This implements the Monitor phase of MAPE-K:
    - Monitors last_seen timestamps
    - Detects dead peers (timeout > PEER_TIMEOUT)
    - Triggers route recalculation when peers die
    """
    global peers, dead_peers

    while True:
        try:
            current_time = time.time()
            newly_dead = []

            # Check all peers
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen

                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(
                            f"🔴 Peer {peer_id} marked as DEAD (no beacon for {elapsed:.1f}s)"
                        )

            # Remove dead peers from active peers
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    logger.info(f"🗑️ Removed dead peer {peer_id} from active peers")

            # Trigger route recalculation if peers died
            if newly_dead:
                logger.info(
                    f"🔄 Triggering route recalculation due to {len(newly_dead)} dead peer(s)"
                )
                await recalculate_routes()

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)


async def recalculate_routes():
    """
    MAPE-K Plan: Recalculate routes after topology changes.

    This implements the Plan phase of MAPE-K:
    - Rebuilds routing table after peer failures
    - Finds alternative paths
    - Updates route cache
    """
    global routes

    logger.info("🧮 Recalculating routes...")

    # Clear route cache
    routes.clear()

    # Rebuild routes using Dijkstra-like algorithm
    for peer_id in peers.keys():
        path = compute_shortest_path(node_id, peer_id)
        if path:
            routes[peer_id] = path
            logger.debug(f"Route to {peer_id}: {' -> '.join(path)}")

    logger.info(f"✅ Routes recalculated: {len(routes)} active routes")


def compute_shortest_path(source: str, destination: str) -> Optional[List[str]]:
    """
    Dijkstra's algorithm for shortest path.

    Returns shortest path from source to destination, avoiding dead peers.
    """
    if source == destination:
        return [source]

    # Build graph from peers (excluding dead peers)
    graph: Dict[str, List[str]] = defaultdict(list)

    for peer_id, peer_info in peers.items():
        if peer_id in dead_peers:
            continue

        neighbors = peer_info.get("neighbors", [])
        for neighbor in neighbors:
            if neighbor not in dead_peers and neighbor != source:
                graph[peer_id].append(neighbor)

    # Add direct connections
    if source in peers:
        for neighbor in peers[source].get("neighbors", []):
            if neighbor not in dead_peers:
                graph[source].append(neighbor)

    # Dijkstra's algorithm
    distances: Dict[str, float] = {source: 0}
    previous: Dict[str, Optional[str]] = {source: None}
    unvisited = set(graph.keys()) | {source, destination}

    while unvisited:
        # Find unvisited node with minimum distance
        current = min(unvisited, key=lambda n: distances.get(n, float("inf")))

        if current == destination:
            # Reconstruct path
            path = []
            node = destination
            while node is not None:
                path.append(node)
                node = previous.get(node)
            return list(reversed(path))

        unvisited.remove(current)
        current_dist = distances.get(current, float("inf"))

        # Update distances to neighbors
        for neighbor in graph.get(current, []):
            if neighbor in unvisited:
                alt = current_dist + 1  # All edges have weight 1
                if alt < distances.get(neighbor, float("inf")):
                    distances[neighbor] = alt
                    previous[neighbor] = current

    # No path found
    return None


async def periodic_route_recalc():
    """
    Periodic route recalculation (even without failures).

    This ensures routes stay optimal as topology changes.
    """
    while True:
        try:
            await asyncio.sleep(ROUTE_RECALC_INTERVAL)
            await recalculate_routes()
        except Exception as e:
            logger.error(f"Periodic route recalculation error: {e}", exc_info=True)


# --- Endpoints ---


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "node_id": node_id,
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "routes_count": len(routes),
    }


@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon from another node.

    MAPE-K Monitor: Updates peer health status.
    """
    global peers, dead_peers

    beacon = {
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time(),
    }
    beacons_received.append(beacon)

    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED from dead state")
        # Trigger route recalculation
        await recalculate_routes()

    # Register/update peer
    peers[req.node_id] = {"last_seen": time.time(), "neighbors": req.neighbors or []}

    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "was_dead": req.node_id in dead_peers,
    }


@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with health status."""
    current_time = time.time()
    peer_status = {}

    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT

        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", []),
        }

    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers),
    }


@app.get("/mesh/status")
async def get_status():
    """Get mesh status with failover metrics."""
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "beacons_received": len(beacons_received),
        "routes_count": len(routes),
        "uptime": time.time(),
        "failover_enabled": True,
    }


@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """
    Route a message to destination with automatic failover.

    MAPE-K Execute: Uses updated routes after failures.
    """
    if req.destination == node_id:
        return {"status": "delivered", "hops": 0, "latency_ms": 0}

    # Check if destination is dead
    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead",
            "dead_peers": list(dead_peers),
        }

    # Use cached route if available
    if req.destination in routes:
        path = routes[req.destination]
        latency = random.uniform(10, 50) * len(path)
        return {
            "status": "delivered",
            "hops": len(path) - 1,
            "latency_ms": latency,
            "path": path,
        }

    # Compute route on-the-fly
    path = compute_shortest_path(node_id, req.destination)
    if path:
        routes[req.destination] = path  # Cache it
        latency = random.uniform(10, 50) * len(path)
        return {
            "status": "delivered",
            "hops": len(path) - 1,
            "latency_ms": latency,
            "path": path,
        }

    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}",
        "dead_peers": list(dead_peers),
    }


@app.get("/mesh/route/{destination}")
async def get_route(destination: str):
    """Get route to destination (with failover support)."""
    if destination in dead_peers:
        raise HTTPException(
            status_code=503, detail=f"Destination {destination} is dead"
        )

    if destination == node_id:
        return {"path": [node_id], "hops": 0}

    # Use cached route
    if destination in routes:
        return {"path": routes[destination], "hops": len(routes[destination]) - 1}

    # Compute route
    path = compute_shortest_path(node_id, destination)
    if path:
        routes[destination] = path
        return {"path": path, "hops": len(path) - 1}

    raise HTTPException(status_code=404, detail=f"No route to {destination}")


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with failover stats."""
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

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP mesh_routes_count Number of cached routes
# TYPE mesh_routes_count gauge
mesh_routes_count {len(routes)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str


@app.on_event("startup")
async def startup():
    """Start background tasks."""
    global _health_check_task, _route_recalc_task, node_id
    import os

    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with failover started as {node_id}")

    # Start background tasks
    _health_check_task = asyncio.create_task(health_check_loop())
    _route_recalc_task = asyncio.create_task(periodic_route_recalc())

    logger.info("✅ Background tasks started: health_check, route_recalc")


@app.on_event("shutdown")
async def shutdown():
    """Stop background tasks."""
    global _health_check_task, _route_recalc_task

    if _health_check_task:
        _health_check_task.cancel()
    if _route_recalc_task:
        _route_recalc_task.cancel()

    logger.info("🛑 Background tasks stopped")


if __name__ == "__main__":
    import uvicorn

    from src.core.settings import settings

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
