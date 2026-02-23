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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import MeshNode, MeshInstance, get_db
from src.api.maas_auth import get_current_user_from_maas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas", tags=["MaaS Telemetry"])

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TELEMETRY_TTL_SECONDS = 300
TELEMETRY_HISTORY_MAX_ITEMS = 2000
TELEMETRY_HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_FALLBACK_ENTRIES = 10000  # Prevent unbounded memory growth
FALLBACK_EVICTION_BATCH = 1000  # Evict this many entries when over limit
try:
    r_client = redis.from_url(REDIS_URL, decode_responses=True)
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to memory.")
    r_client = {}
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


def _set_telemetry(node_id: str, data: Dict):
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
            _store_local_fallback(key, history_key, data)
    else:
        # Use local fallback when Redis is not available
        _store_local_fallback(key, history_key, data)


def _get_telemetry(node_id: str) -> Dict:
    key = f"maas:telemetry:{node_id}"
    if REDIS_AVAILABLE:
        try:
            raw = r_client.get(key)
            return json.loads(raw) if raw else {}
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry snapshot for {node_id}: {e}")
            fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
            return fallback if isinstance(fallback, dict) else {}
    else:
        # Use local fallback when Redis is not available
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        return fallback if isinstance(fallback, dict) else {}


def _get_telemetry_history(node_id: str, limit: int = 100) -> List[Dict]:
    if limit <= 0:
        return []
    key = f"maas:telemetry:{node_id}:history"
    if REDIS_AVAILABLE:
        try:
            raw_items = r_client.lrange(key, 0, limit - 1)
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry history for {node_id}: {e}")
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
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        if isinstance(fallback, list):
            return [entry for entry in fallback[:limit] if isinstance(entry, dict)]
        return []


def get_fallback_cache_stats() -> Dict[str, Any]:
    """Get statistics for the telemetry fallback cache."""
    return _LOCAL_TELEMETRY_FALLBACK.get_stats()

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
