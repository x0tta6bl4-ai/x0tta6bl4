"""
MaaS Telemetry (Production - Redis backed) — x0tta6bl4
======================================================

High-frequency telemetry storage using Redis for scalability.
"""

import logging
import json
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Any, List, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import MeshNode, get_db
from src.api.maas_auth import get_current_user_from_maas
from src.core.reliability_policy import mark_degraded_dependency
from src.monitoring.maas_metrics import record_heartbeat as _record_heartbeat_metric
from src.network.reputation_scoring import ReputationScoringSystem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Telemetry"])

# Global Reputation System for MaaS
reputation_system = ReputationScoringSystem()

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TELEMETRY_TTL_SECONDS = 300
TELEMETRY_HISTORY_MAX_ITEMS = 2000
TELEMETRY_HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_FALLBACK_ENTRIES = 10000  # Prevent unbounded memory growth
FALLBACK_EVICTION_BATCH = 1000  # Evict this many entries when over limit
try:
    r_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5)
    r_client.ping()
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to memory.")
    r_client = None
    REDIS_AVAILABLE = False


class LRUCache:
    """
    Thread-safe LRU cache for telemetry fallback.
    
    Uses OrderedDict for O(1) access and eviction.
    Automatically evicts least-recently-used entries when capacity is exceeded.
    """
    
    def __init__(self, max_size: int = MAX_FALLBACK_ENTRIES):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item and move to end (most recently used)."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item, evicting LRU entries if necessary."""
        with self._lock:
            if key in self._cache:
                # Update existing and move to end
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new entry
                self._cache[key] = value
                
                # Evict LRU entries if over capacity
                while len(self._cache) > self._max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    self._evictions += 1
    
    def delete(self, key: str) -> bool:
        """Delete an item from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def keys(self) -> List[str]:
        """Get all keys (for cleanup operations)."""
        with self._lock:
            return list(self._cache.keys())
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key)
        if value is None and key not in self._cache:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._cache

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
            }


# Global LRU cache for telemetry fallback
_LOCAL_TELEMETRY_FALLBACK = LRUCache(max_size=MAX_FALLBACK_ENTRIES)

class NodeHeartbeatRequest(BaseModel):
    node_id: str
    cpu_usage: float
    memory_usage: float
    neighbors_count: int
    routing_table_size: int
    uptime: float
    latency_ms: float = 0.0
    error_reports: Optional[List[Dict[str, Any]]] = None
    pheromones: Optional[Dict[str, Dict[str, float]]] = None


def _store_local_fallback(key: str, history_key: str, data: Dict) -> None:
    """Store telemetry data in LRU cache fallback.
    
    Uses LRU eviction to maintain bounded memory usage.
    History is stored as a separate key with list of entries.
    """
    # Store current snapshot
    _LOCAL_TELEMETRY_FALLBACK.set(key, data)
    
    # Update history (stored as list under history key)
    history = _LOCAL_TELEMETRY_FALLBACK.get(history_key)
    if history is None:
        history = []
    elif not isinstance(history, list):
        history = []
    
    # Prepend new data and trim to max items
    history.insert(0, data)
    if len(history) > TELEMETRY_HISTORY_MAX_ITEMS:
        history = history[:TELEMETRY_HISTORY_MAX_ITEMS]
    
    _LOCAL_TELEMETRY_FALLBACK.set(history_key, history)


def _set_telemetry(
    node_id: str,
    data: Dict,
    degraded_dependencies: Optional[set[str]] = None,
):
    key = f"maas:telemetry:{node_id}"
    history_key = f"{key}:history"
    if REDIS_AVAILABLE:
        payload = json.dumps(data)
        try:
            r_client.setex(key, TELEMETRY_TTL_SECONDS, payload) # 5 min TTL
            pipeline = r_client.pipeline()
            pipeline.lpush(history_key, payload)
            pipeline.ltrim(history_key, 0, TELEMETRY_HISTORY_MAX_ITEMS - 1)
            pipeline.expire(history_key, TELEMETRY_HISTORY_TTL_SECONDS)
            pipeline.execute()
        except Exception as e:
            logger.warning(f"⚠️ Failed to persist telemetry history for {node_id}: {e}")
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            _store_local_fallback(key, history_key, data)
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        _store_local_fallback(key, history_key, data)


def _get_telemetry(
    node_id: str,
    degraded_dependencies: Optional[set[str]] = None,
) -> Dict:
    key = f"maas:telemetry:{node_id}"
    if REDIS_AVAILABLE:
        try:
            raw = r_client.get(key)
            return json.loads(raw) if raw else {}
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry snapshot for {node_id}: {e}")
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
            return fallback if isinstance(fallback, dict) else {}
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        return fallback if isinstance(fallback, dict) else {}


def _get_telemetry_history(
    node_id: str,
    limit: int = 100,
    degraded_dependencies: Optional[set[str]] = None,
) -> List[Dict]:
    if limit <= 0:
        return []
    key = f"maas:telemetry:{node_id}:history"
    if REDIS_AVAILABLE:
        try:
            raw_items = r_client.lrange(key, 0, limit - 1)
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry history for {node_id}: {e}")
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
            if isinstance(fallback, list):
                return [entry for entry in fallback[:limit] if isinstance(entry, dict)]
            return []
        results: List[Dict] = []
        for item in raw_items or []:
            try:
                parsed = json.loads(item) if isinstance(item, str) else item
                if isinstance(parsed, dict):
                    results.append(parsed)
            except Exception:
                continue
        return results
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        if isinstance(fallback, list):
            return [entry for entry in fallback[:limit] if isinstance(entry, dict)]
        return []


def get_fallback_cache_stats() -> Dict[str, Any]:
    """Get statistics for the telemetry fallback cache."""
    return _LOCAL_TELEMETRY_FALLBACK.get_stats()


class NodeUptimeTracker:
    """Tracks long-term node uptime in Redis or memory."""

    def __init__(self, window_hours: int = 24):
        self.window_seconds = window_hours * 3600

    def record_heartbeat(self, node_id: str):
        key = f"maas:uptime:{node_id}"
        now = time.time()
        if REDIS_AVAILABLE:
            try:
                # Store timestamps of heartbeats in a sorted set
                r_client.zadd(key, {str(now): now})
                # Evict old heartbeats
                r_client.zremrangebyscore(key, 0, now - self.window_seconds)
                # Keep TTL
                r_client.expire(key, self.window_seconds)
            except Exception as e:
                logger.warning(f"⚠️ Uptime tracking failed for {node_id}: {e}")

    def get_uptime_percent(self, node_id: str) -> float:
        """
        Calculate uptime % based on received heartbeats vs expected (1/min).
        Returns 0.0 to 1.0.
        """
        key = f"maas:uptime:{node_id}"
        if REDIS_AVAILABLE:
            try:
                now = time.time()
                count = r_client.zcount(key, now - self.window_seconds, now)
                # Expect 60 heartbeats per hour -> 1440 per 24h
                expected = self.window_seconds / 60
                return min(count / expected, 1.0)
            except Exception:
                return 0.0
        return 0.0


# Singleton Tracker
uptime_tracker = NodeUptimeTracker()


@router.post("/heartbeat")
async def heartbeat(
    req: NodeHeartbeatRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
    if not node:
        logger.warning(f"🚨 UNKNOWN NODE HEARTBEAT: {req.node_id}")
        raise HTTPException(status_code=404, detail="Node not registered")
    
    # Fast DB update
    node.status = "healthy"
    node.last_seen = datetime.utcnow()

    # Capture IP address for eBPF filtering and geographic analytics
    client_ip = request.client.host if request.client else None
    if client_ip:
        node.ip_address = client_ip
        
    db.commit()

    # Track long-term uptime for settlement
    uptime_tracker.record_heartbeat(req.node_id)
    _record_heartbeat_metric(req.node_id)

    
    # Update Reputation based on heartbeat data
    has_errors = bool(req.error_reports)
    error_type = req.error_reports[0].get("type") if has_errors else None
    
    await reputation_system.record_proxy_result(
        proxy_id=req.node_id,
        success=not has_errors,
        latency_ms=req.latency_ms,
        error_type=error_type
    )
    
    # Store high-frequency data in Redis
    trust_score = 0.5
    proxy_trust = reputation_system.get_proxy_trust(req.node_id)
    if proxy_trust:
        trust_score = proxy_trust.trust_score

    telemetry_data = {
        "cpu": req.cpu_usage,
        "mem": req.memory_usage,
        "neighbors": req.neighbors_count,
        "uptime": req.uptime,
        "latency": req.latency_ms,
        "last_seen": node.last_seen.isoformat(),
        "reputation": trust_score
    }
    degraded_dependencies: set[str] = set()
    _set_telemetry(req.node_id, telemetry_data, degraded_dependencies=degraded_dependencies)
    for dependency in degraded_dependencies:
        mark_degraded_dependency(request, dependency)
    
    return {"status": "ack", "mesh_id": node.mesh_id, "trust_score": trust_score}

@router.get("/{mesh_id}/topology")
async def get_topology(
    mesh_id: str, 
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_maas)
):
    """Returns nodes and links for the D3.js dashboard from Redis."""
    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
    
    result_nodes = []
    links = []
    seen_links = set()
    degraded_dependencies: set[str] = set()
    
    for n in nodes:
        telemetry = _get_telemetry(n.id, degraded_dependencies=degraded_dependencies)
        result_nodes.append({
            "id": n.id,
            "class": n.device_class,
            "status": "healthy" if telemetry else "offline",
            "telemetry": telemetry,
            "pqc_enabled": True # All MaaS nodes have PQC by default
        })
        
        # Extract links from pheromones
        if telemetry and "pheromones" in telemetry:
            for neighbor_id, paths in telemetry["pheromones"].items():
                # Link ID: sorted pair to avoid duplicates
                link_key = tuple(sorted([n.id, neighbor_id]))
                if link_key not in seen_links:
                    # Get best score/latency if available
                    score = 0.0
                    if paths:
                        score = max(p.get("score", 0.0) for p in paths.values())
                    
                    links.append({
                        "source": n.id,
                        "target": neighbor_id,
                        "quality": score,
                        "secure": True, # PQC Tunnel
                        "type": "pqc-mesh"
                    })
                    seen_links.add(link_key)
    for dependency in degraded_dependencies:
        mark_degraded_dependency(request, dependency)

    return {"nodes": result_nodes, "links": links}
