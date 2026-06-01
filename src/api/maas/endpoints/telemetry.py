"""
MaaS Telemetry (Production - Redis backed) — x0tta6bl4
======================================================

High-frequency telemetry storage using Redis for scalability.
"""

import logging
import hashlib
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

from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import MeshNode, get_db
from src.api.maas_auth import get_current_user_from_maas
from src.api.maas.registry import find_mesh_for_node, get_mesh
from src.core.reliability_policy import mark_degraded_dependency
from src.monitoring.maas_metrics import record_heartbeat as _record_heartbeat_metric
from src.network.reputation_scoring import ReputationScoringSystem

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MaaS Telemetry"])
root_router = APIRouter(tags=["MaaS Telemetry"])
_SERVICE_AGENT = "maas-telemetry"
_TELEMETRY_LAYER = "api_telemetry_observed_state"
_TELEMETRY_CLAIM_BOUNDARY = (
    "MaaS telemetry observed-state event only. It records bounded local "
    "telemetry snapshot/history/topology metadata and storage fallback state; "
    "topology responses expose only source-quality metadata and EventBus IDs for "
    "cached telemetry reads; they do not prove fresh live agent connectivity or "
    "external network reachability."
)
_HEARTBEAT_CLAIM_BOUNDARY = (
    "MaaS heartbeat processing evidence only. It records local DB update, "
    "uptime-sample, heartbeat metric, reputation update, and telemetry snapshot "
    "write metadata with node, mesh, client IP, and error identifiers hashed. It "
    "does not copy raw heartbeat payload values, pheromone maps, IP addresses, "
    "node IDs, mesh IDs, or error details, and it does not prove live dataplane "
    "reachability, remote node authenticity, escrow settlement, or external "
    "provider quality."
)
_MAAS_TELEMETRY_CLAIM_GATE_BOUNDARY = (
    "MaaS telemetry claim gate. Local readiness, heartbeat, uptime, cached "
    "snapshot/history, and topology evidence can support local API telemetry "
    "observations only. It does not prove fresh live agent connectivity, node "
    "reachability, routing convergence, dataplane delivery, customer traffic, "
    "external DPI bypass, escrow settlement finality, or production readiness."
)
_TELEMETRY_FIELD_LIMIT = 20

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


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _telemetry_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS telemetry EventBus: %s", exc)
        return None


def _telemetry_project_root_from_request(request: Optional[Request]) -> str:
    state = getattr(request, "state", None)
    return getattr(state, "event_project_root", ".")


def _telemetry_payload_summary(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {"payload_type": type(data).__name__, "field_count": 0}
    fields = sorted(str(key) for key in data.keys())
    return {
        "payload_type": "dict",
        "field_count": len(fields),
        "fields": fields[:_TELEMETRY_FIELD_LIMIT],
        "fields_truncated": len(fields) > _TELEMETRY_FIELD_LIMIT,
        "has_status": "status" in data,
        "has_pheromones": isinstance(data.get("pheromones"), dict),
        "numeric_field_count": sum(
            1
            for value in data.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ),
    }


def _maas_telemetry_claim_gate(
    *,
    surface: str,
    read_only: bool = True,
    local_readiness_dependency_observation: bool = False,
    local_snapshot_observation: bool = False,
    local_history_observation: bool = False,
    local_topology_observation: bool = False,
    local_heartbeat_processing: bool = False,
    local_uptime_sample_observation: bool = False,
    settlement_uptime_ready: bool = False,
    telemetry_runtime_ready: bool = False,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.maas_telemetry.claim_gate.v1",
        "surface": surface,
        "claim_boundary": _MAAS_TELEMETRY_CLAIM_GATE_BOUNDARY,
        "local_only": True,
        "read_only": bool(read_only),
        "local_readiness_dependency_observation_claim_allowed": bool(
            local_readiness_dependency_observation
        ),
        "local_telemetry_snapshot_observation_claim_allowed": bool(
            local_snapshot_observation
        ),
        "local_telemetry_history_observation_claim_allowed": bool(
            local_history_observation
        ),
        "local_topology_snapshot_observation_claim_allowed": bool(
            local_topology_observation
        ),
        "local_heartbeat_processing_claim_allowed": bool(
            local_heartbeat_processing
        ),
        "local_uptime_sample_observation_claim_allowed": bool(
            local_uptime_sample_observation
        ),
        "settlement_uptime_dependency_ready_observed": bool(
            settlement_uptime_ready
        ),
        "telemetry_runtime_ready_observed": bool(telemetry_runtime_ready),
        "raw_identifiers_redacted": True,
        "raw_telemetry_values_redacted": True,
        "fresh_live_agent_connectivity_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "remote_node_authenticity_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "escrow_settlement_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
    }


def _maas_telemetry_event_claim_gate(
    *,
    operation: str,
    read_only: bool,
    telemetry_summary: Dict[str, Any],
    topology_summary: Dict[str, Any],
    heartbeat_summary: Dict[str, Any],
    settlement_summary: Dict[str, Any],
) -> Dict[str, Any]:
    return _maas_telemetry_claim_gate(
        surface=f"maas_telemetry.{operation}",
        read_only=read_only,
        local_snapshot_observation=operation
        in {"telemetry_snapshot_write", "telemetry_snapshot_read"}
        or bool(telemetry_summary),
        local_history_observation=operation == "telemetry_history_read",
        local_topology_observation=operation.startswith("topology")
        or bool(topology_summary),
        local_heartbeat_processing=operation == "heartbeat"
        or bool(heartbeat_summary),
        local_uptime_sample_observation=bool(
            settlement_summary.get("uptime_sample_attempted")
            or settlement_summary.get("uptime_sample_recorded")
        ),
        settlement_uptime_ready=bool(
            settlement_summary.get("settlement_uptime_ready")
        ),
    )


def _publish_telemetry_observed_state(
    event_bus: Optional[EventBus],
    *,
    operation: str,
    stage: str,
    status: str,
    node_id: Any = None,
    mesh_id: Any = None,
    storage_backend: Optional[str] = None,
    read_only: bool = True,
    observed_state: bool = True,
    telemetry_summary: Optional[Dict[str, Any]] = None,
    topology_summary: Optional[Dict[str, Any]] = None,
    heartbeat_summary: Optional[Dict[str, Any]] = None,
    trust_summary: Optional[Dict[str, Any]] = None,
    settlement_summary: Optional[Dict[str, Any]] = None,
    upstream_event_ids: Optional[List[str]] = None,
    degraded_dependencies: Optional[set[str]] = None,
    reason: str = "",
    duration_ms: Optional[float] = None,
    claim_boundary: Optional[str] = None,
) -> Optional[str]:
    if event_bus is None:
        return None
    telemetry_summary_payload = telemetry_summary or {}
    topology_summary_payload = topology_summary or {}
    heartbeat_summary_payload = heartbeat_summary or {}
    trust_summary_payload = trust_summary or {}
    settlement_summary_payload = settlement_summary or {}
    payload = {
        "component": "api.maas_telemetry",
        "stage": stage,
        "operation": operation,
        "service_name": _SERVICE_AGENT,
        "source_alias": _SERVICE_AGENT,
        "layer": _TELEMETRY_LAYER,
        "status": status,
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "storage_backend": storage_backend,
        "read_only": read_only,
        "observed_state": observed_state,
        "safe_actuator": False,
        "telemetry_summary": telemetry_summary_payload,
        "topology_summary": topology_summary_payload,
        "heartbeat_summary": heartbeat_summary_payload,
        "trust_summary": trust_summary_payload,
        "settlement_summary": settlement_summary_payload,
        "maas_telemetry_claim_gate": _maas_telemetry_event_claim_gate(
            operation=operation,
            read_only=read_only,
            telemetry_summary=telemetry_summary_payload,
            topology_summary=topology_summary_payload,
            heartbeat_summary=heartbeat_summary_payload,
            settlement_summary=settlement_summary_payload,
        ),
        "upstream_event_ids": list(upstream_event_ids or [])[:20],
        "upstream_events_total": len(upstream_event_ids or []),
        "duration_ms": (
            round(float(duration_ms), 3) if duration_ms is not None else None
        ),
        "degraded_dependencies": sorted(degraded_dependencies or set()),
        "raw_identifiers_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": claim_boundary or _TELEMETRY_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SERVICE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS telemetry observed-state event: %s", exc)
        return None


def _telemetry_event_ids(
    event_bus: Optional[EventBus],
    *,
    operation: Optional[str] = None,
) -> set[str]:
    if event_bus is None or not hasattr(event_bus, "get_event_history"):
        return set()
    try:
        events = event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=_SERVICE_AGENT,
            limit=1000,
        )
    except Exception:
        return set()
    return {
        event.event_id
        for event in events
        if operation is None or event.data.get("operation") == operation
    }


def _topology_status_source(
    telemetry: Optional[Dict[str, Any]],
    db_status: Optional[str],
) -> str:
    if isinstance(telemetry, dict) and isinstance(telemetry.get("status"), str):
        return "cached_telemetry_status"
    if isinstance(telemetry, dict) and telemetry:
        return "cached_telemetry_presence"
    if isinstance(db_status, str) and db_status:
        return "database_node_status"
    return "missing"


def _topology_telemetry_source_quality(
    telemetry: Optional[Dict[str, Any]],
    degraded_dependencies: set[str],
) -> str:
    if not isinstance(telemetry, dict) or not telemetry:
        return "snapshot_missing"
    if "redis" in degraded_dependencies:
        return "local_fallback_or_redis_degraded_cached_snapshot"
    if REDIS_AVAILABLE:
        return "redis_cached_snapshot"
    return "local_fallback_cached_snapshot"


def _topology_telemetry_evidence(
    event_bus: Optional[EventBus],
    *,
    before_read_event_ids: set[str],
    telemetry: Optional[Dict[str, Any]],
    db_status: Optional[str],
    degraded_dependencies: set[str],
) -> Dict[str, Any]:
    read_event_ids = sorted(
        _telemetry_event_ids(event_bus, operation="telemetry_snapshot_read")
        - before_read_event_ids
    )
    has_snapshot = isinstance(telemetry, dict) and bool(telemetry)
    return {
        "source_agents": [_SERVICE_AGENT] if read_event_ids else [],
        "event_ids": read_event_ids,
        "events_total": len(read_event_ids),
        "source_quality": _topology_telemetry_source_quality(
            telemetry,
            degraded_dependencies,
        ),
        "decision_basis": (
            "cached_observed_state" if has_snapshot else "database_status_or_missing"
        ),
        "status_source": _topology_status_source(telemetry, db_status),
        "dataplane_confirmed": False,
        "raw_telemetry_values_redacted": True,
        "raw_identifiers_redacted": True,
        "payload_summary": _telemetry_payload_summary(telemetry or {}),
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.topology_node_telemetry_evidence",
            read_only=True,
            local_snapshot_observation=has_snapshot,
            local_topology_observation=True,
        ),
        "claim_boundary": _TELEMETRY_CLAIM_BOUNDARY,
    }


def _topology_control_policy_evidence(
    *,
    node_evidence: List[Dict[str, Any]],
    degraded_dependencies: set[str],
) -> Dict[str, Any]:
    evidence_ids = sorted(
        {
            event_id
            for item in node_evidence
            for event_id in item.get("event_ids", [])
        }
    )
    source_qualities = sorted(
        {
            str(item.get("source_quality"))
            for item in node_evidence
            if item.get("source_quality")
        }
    )
    return {
        "decision_basis": "cached_telemetry_observed_state",
        "dataplane_confirmed": False,
        "source_agents": [_SERVICE_AGENT] if evidence_ids else [],
        "event_ids": evidence_ids,
        "events_total": len(evidence_ids),
        "source_qualities": source_qualities,
        "degraded_dependencies": sorted(degraded_dependencies),
        "raw_telemetry_values_redacted": True,
        "raw_identifiers_redacted": True,
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.topology_control_policy_evidence",
            read_only=True,
            local_snapshot_observation=bool(evidence_ids),
            local_topology_observation=True,
        ),
        "claim_boundary": (
            "Topology control policy evidence reports source quality for cached "
            "telemetry snapshots only. It must not be treated as proof of live "
            "packet reachability, current mesh convergence, or remote node "
            "authenticity without stronger dataplane evidence."
        ),
    }


def _extract_pheromone_score(raw: Any) -> float:
    """Accept legacy numeric weights and richer score-bearing payloads."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, dict):
        for key in ("score", "weight", "latency_score"):
            value = raw.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return 0.0


def _derive_topology_status(
    telemetry: Optional[Dict[str, Any]],
    db_status: Optional[str],
) -> str:
    """Normalize node status for topology consumers across mixed payload shapes."""
    raw_status = None
    has_telemetry = isinstance(telemetry, dict) and bool(telemetry)
    if isinstance(telemetry, dict):
        value = telemetry.get("status")
        if isinstance(value, str):
            raw_status = value.strip().lower()

    if not raw_status and isinstance(db_status, str):
        raw_status = db_status.strip().lower()

    if raw_status in {"degraded", "unhealthy"}:
        return "degraded"
    if has_telemetry:
        return "healthy"
    return "offline"


def _telemetry_user_id(current_user: Any) -> Optional[str]:
    for attr in ("id", "user_id"):
        value = getattr(current_user, attr, None)
        if value is not None:
            return str(value)
    return None


def _verify_topology_mesh_access(
    mesh_id: str,
    current_user: Any,
    db: Any,
) -> Dict[str, Any]:
    """Confirm topology reads are for a real mesh owned by the caller."""
    owner_id = _telemetry_user_id(current_user)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")

    try:
        from src.database import MeshInstance as DBMeshInstance

        if all(callable(getattr(db, attr, None)) for attr in ("query",)):
            row = db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
            if row is not None:
                if str(getattr(row, "owner_id", "")) != owner_id:
                    raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")
                return {
                    "mesh_source": "database",
                    "owner_checked": True,
                }
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        from src.api.maas_legacy import _get_mesh_or_404

        _get_mesh_or_404(mesh_id, owner_id)
        return {
            "mesh_source": "legacy_or_modular_registry",
            "owner_checked": True,
        }
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")


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
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
    mesh_id: Any = None,
):
    key = f"maas:telemetry:{node_id}"
    history_key = f"{key}:history"
    storage_backend = "redis" if REDIS_AVAILABLE else "local_fallback"
    reason = ""
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
            storage_backend = "local_fallback"
            reason = "redis_write_failed"
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            _store_local_fallback(key, history_key, data)
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        _store_local_fallback(key, history_key, data)
    bus = event_bus
    if bus is None and event_project_root:
        try:
            bus = get_event_bus(event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize MaaS telemetry EventBus: %s", exc)
            bus = None
    _publish_telemetry_observed_state(
        bus,
        operation="telemetry_snapshot_write",
        stage="snapshot_written",
        status="success",
        node_id=node_id,
        mesh_id=mesh_id or data.get("mesh_id"),
        storage_backend=storage_backend,
        read_only=False,
        telemetry_summary=_telemetry_payload_summary(data),
        degraded_dependencies=degraded_dependencies,
        reason=reason,
    )


def _get_telemetry(
    node_id: str,
    degraded_dependencies: Optional[set[str]] = None,
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
    mesh_id: Any = None,
) -> Dict:
    key = f"maas:telemetry:{node_id}"
    storage_backend = "redis" if REDIS_AVAILABLE else "local_fallback"
    result: Dict[str, Any] = {}
    reason = ""
    if REDIS_AVAILABLE:
        try:
            raw = r_client.get(key)
            result = json.loads(raw) if raw else {}
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry snapshot for {node_id}: {e}")
            storage_backend = "local_fallback"
            reason = "redis_read_failed"
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
            result = fallback if isinstance(fallback, dict) else {}
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        result = fallback if isinstance(fallback, dict) else {}
    bus = event_bus
    if bus is None and event_project_root:
        try:
            bus = get_event_bus(event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize MaaS telemetry EventBus: %s", exc)
            bus = None
    _publish_telemetry_observed_state(
        bus,
        operation="telemetry_snapshot_read",
        stage="snapshot_read",
        status="success",
        node_id=node_id,
        mesh_id=mesh_id or result.get("mesh_id"),
        storage_backend=storage_backend,
        read_only=True,
        telemetry_summary=_telemetry_payload_summary(result),
        degraded_dependencies=degraded_dependencies,
        reason=reason,
    )
    return result


def _get_telemetry_history(
    node_id: str,
    limit: int = 100,
    degraded_dependencies: Optional[set[str]] = None,
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: Optional[str] = None,
    mesh_id: Any = None,
) -> List[Dict]:
    if limit <= 0:
        return []
    key = f"maas:telemetry:{node_id}:history"
    storage_backend = "redis" if REDIS_AVAILABLE else "local_fallback"
    results: List[Dict] = []
    reason = ""
    if REDIS_AVAILABLE:
        try:
            raw_items = r_client.lrange(key, 0, limit - 1)
        except Exception as e:
            logger.warning(f"⚠️ Failed to read telemetry history for {node_id}: {e}")
            storage_backend = "local_fallback"
            reason = "redis_history_read_failed"
            if degraded_dependencies is not None:
                degraded_dependencies.add("redis")
            fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
            if isinstance(fallback, list):
                results = [entry for entry in fallback[:limit] if isinstance(entry, dict)]
        else:
            for item in raw_items or []:
                try:
                    parsed = json.loads(item) if isinstance(item, str) else item
                    if isinstance(parsed, dict):
                        results.append(parsed)
                except Exception:
                    continue
    else:
        # Use local fallback when Redis is not available
        if degraded_dependencies is not None:
            degraded_dependencies.add("redis")
        fallback = _LOCAL_TELEMETRY_FALLBACK.get(key)
        if isinstance(fallback, list):
            results = [entry for entry in fallback[:limit] if isinstance(entry, dict)]
    bus = event_bus
    if bus is None and event_project_root:
        try:
            bus = get_event_bus(event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize MaaS telemetry EventBus: %s", exc)
            bus = None
    _publish_telemetry_observed_state(
        bus,
        operation="telemetry_history_read",
        stage="history_read",
        status="success",
        node_id=node_id,
        mesh_id=mesh_id,
        storage_backend=storage_backend,
        read_only=True,
        telemetry_summary={
            "history_count": len(results),
            "limit": limit,
            "returned_dict_entries": len(results),
        },
        degraded_dependencies=degraded_dependencies,
        reason=reason,
    )
    return results


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


def _telemetry_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "commit"))


def _mesh_node_model_available() -> bool:
    return all(
        hasattr(MeshNode, attr)
        for attr in ("id", "mesh_id", "status", "last_seen", "ip_address", "device_class")
    )


def _redis_persistence_ready() -> bool:
    return REDIS_AVAILABLE and r_client is not None


def _fallback_cache_available() -> bool:
    return all(
        callable(getattr(_LOCAL_TELEMETRY_FALLBACK, attr, None))
        for attr in ("get", "set", "get_stats")
    )


def _uptime_tracker_available() -> bool:
    return all(
        callable(getattr(uptime_tracker, attr, None))
        for attr in ("record_heartbeat", "get_uptime_percent")
    )


def _reputation_system_available() -> bool:
    return all(
        callable(getattr(reputation_system, attr, None))
        for attr in ("record_proxy_result", "get_proxy_trust")
    )


def _telemetry_readiness_status(db: Any) -> Dict[str, Any]:
    telemetry_db_ready = _telemetry_db_session_available(db)
    mesh_node_model_ready = _mesh_node_model_available()
    redis_persistence_ready = _redis_persistence_ready()
    fallback_cache_ready = _fallback_cache_available()
    uptime_tracker_ready = _uptime_tracker_available()
    settlement_uptime_ready = redis_persistence_ready and uptime_tracker_ready
    reputation_system_ready = _reputation_system_available()
    metrics_export_ready = callable(_record_heartbeat_metric)
    auth_dependency_ready = callable(get_current_user_from_maas)
    telemetry_runtime_ready = (
        telemetry_db_ready
        and mesh_node_model_ready
        and fallback_cache_ready
        and uptime_tracker_ready
        and reputation_system_ready
        and metrics_export_ready
        and auth_dependency_ready
    )

    degraded_dependencies = []
    if not telemetry_db_ready:
        degraded_dependencies.append("database")
    if not mesh_node_model_ready:
        degraded_dependencies.append("mesh_node_model")
    if not redis_persistence_ready:
        degraded_dependencies.append("redis")
    if not fallback_cache_ready:
        degraded_dependencies.append("fallback_cache")
    if not uptime_tracker_ready:
        degraded_dependencies.append("uptime_tracker")
    if not reputation_system_ready:
        degraded_dependencies.append("reputation_system")
    if not metrics_export_ready:
        degraded_dependencies.append("heartbeat_metrics")
    if not auth_dependency_ready:
        degraded_dependencies.append("auth")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "telemetry_runtime_ready": telemetry_runtime_ready,
        "telemetry_db_ready": telemetry_db_ready,
        "mesh_node_model_ready": mesh_node_model_ready,
        "redis_persistence_ready": redis_persistence_ready,
        "fallback_cache_ready": fallback_cache_ready,
        "uptime_tracker_ready": uptime_tracker_ready,
        "settlement_uptime_ready": settlement_uptime_ready,
        "reputation_system_ready": reputation_system_ready,
        "metrics_export_ready": metrics_export_ready,
        "auth_dependency_ready": auth_dependency_ready,
        "legacy_route_shadowing": {
            "shadowed_by_legacy": [
                "POST /heartbeat",
            ],
            "direct_routes": [
                "GET /{mesh_id}/topology",
            ],
            "import_level_runtime_users": [
                "src.api.maas_nodes",
                "src.services.marketplace_settlement",
            ],
            "boundary": (
                "Legacy maas router is registered before maas_telemetry, so "
                "HTTP heartbeat requests are handled by the legacy route. "
                "Topology is handled by maas_telemetry with mesh ownership "
                "verification before telemetry snapshot reads. The Redis/fallback "
                "telemetry helpers and uptime tracker remain active for maas_nodes "
                "imports and marketplace settlement."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Telemetry heartbeat updates MeshNode status, last_seen, and "
                "observed IP address through SQLAlchemy."
            ),
            "mesh_node_model": (
                "Topology and heartbeat paths depend on MeshNode identity, mesh, "
                "status, last_seen, IP, and device class fields."
            ),
            "redis": (
                "Redis is the durable high-frequency telemetry and uptime store. "
                "Snapshot/history helpers fall back to local memory, but settlement "
                "uptime uses the Redis-backed uptime tracker."
            ),
            "fallback_cache": (
                "LRU fallback keeps node telemetry snapshots/history bounded when "
                "Redis is unavailable."
            ),
            "uptime_tracker": (
                "Marketplace settlement imports uptime_tracker and requires uptime "
                "samples to decide escrow release/refund."
            ),
            "reputation_system": (
                "Heartbeat processing feeds proxy success and latency into "
                "ReputationScoringSystem."
            ),
            "heartbeat_metrics": (
                "Heartbeat processing exports MaaS heartbeat metrics."
            ),
            "auth": (
                "Topology route depends on maas_auth.get_current_user_from_maas."
            ),
        },
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "dataplane_delivery",
                "settlement_finality",
                "customer_traffic",
            ),
            surface="maas_telemetry_readiness",
        ),
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.readiness",
            read_only=True,
            local_readiness_dependency_observation=True,
            settlement_uptime_ready=settlement_uptime_ready,
            telemetry_runtime_ready=telemetry_runtime_ready,
        ),
        "claim_boundary": (
            "Telemetry readiness separates route availability from Redis-backed "
            "persistence, bounded local fallback, DB MeshNode updates, reputation "
            "scoring, metrics export, settlement uptime, and legacy route precedence. "
            "It does not prove that agents are actively sending fresh telemetry."
        ),
    }


@router.get("/telemetry/readiness")
async def telemetry_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _telemetry_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@root_router.post("/heartbeat")
@router.post("/heartbeat")
async def heartbeat(
    req: NodeHeartbeatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_maas),
):
    started = time.perf_counter()
    event_bus = _telemetry_event_bus_from_request(request)
    event_project_root = _telemetry_project_root_from_request(request)
    node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
    mesh_id = getattr(node, "mesh_id", None)
    db_node_found = node is not None
    db_committed = False
    registry_node = None
    last_seen = datetime.utcnow()

    if not node:
        mesh_id = find_mesh_for_node(req.node_id)
        if mesh_id:
            registry_instance = get_mesh(mesh_id)
            registry_node = (
                getattr(registry_instance, "node_instances", {}) or {}
            ).get(req.node_id)

    if not node and not registry_node:
        logger.warning(f"🚨 UNKNOWN NODE HEARTBEAT: {req.node_id}")
        _publish_telemetry_observed_state(
            event_bus,
            operation="heartbeat",
            stage="node_lookup",
            status="unknown_node",
            node_id=req.node_id,
            storage_backend="database",
            read_only=True,
            heartbeat_summary={
                "db_node_found": False,
                "db_committed": False,
                "registry_node_found": False,
                "client_ip_present": bool(getattr(request, "client", None)),
                "client_ip_hash": _redacted_sha256_prefix(
                    request.client.host if request.client else None
                ),
                "error_reports_count": len(req.error_reports or []),
                "has_error_reports": bool(req.error_reports),
                "has_pheromones": isinstance(req.pheromones, dict),
            },
            trust_summary={
                "reputation_update_attempted": False,
                "reputation_update_success": False,
            },
            settlement_summary={
                "uptime_sample_attempted": False,
                "uptime_sample_recorded": False,
                "settlement_uptime_ready": REDIS_AVAILABLE
                and _uptime_tracker_available(),
            },
            duration_ms=(time.perf_counter() - started) * 1000,
            claim_boundary=_HEARTBEAT_CLAIM_BOUNDARY,
            reason="node_not_registered",
        )
        raise HTTPException(status_code=404, detail="Node not registered")

    _verify_topology_mesh_access(str(mesh_id), current_user, db)

    client_ip = request.client.host if request.client else None
    if node:
        # Fast DB update
        node.status = "healthy"
        node.last_seen = last_seen

        # Capture IP address for eBPF filtering and geographic analytics
        if client_ip:
            node.ip_address = client_ip

        db.commit()
        db_committed = True
    elif registry_node is not None:
        registry_node["status"] = "healthy"
        registry_node["last_seen"] = last_seen.isoformat()
        if client_ip:
            registry_node["ip_address"] = client_ip

    # Track long-term uptime for settlement
    uptime_tracker.record_heartbeat(req.node_id)
    uptime_sample_attempted = True
    _record_heartbeat_metric(req.node_id)
    heartbeat_metric_recorded = True


    # Update Reputation based on heartbeat data
    has_errors = bool(req.error_reports)
    error_type = req.error_reports[0].get("type") if has_errors else None

    await reputation_system.record_proxy_result(
        proxy_id=req.node_id,
        success=not has_errors,
        latency_ms=req.latency_ms,
        error_type=error_type
    )
    reputation_update_success = True

    # Store high-frequency data in Redis
    trust_score = 0.5
    proxy_trust = reputation_system.get_proxy_trust(req.node_id)
    if proxy_trust:
        trust_score = proxy_trust.trust_score

    telemetry_data = {
        "status": "healthy",
        "cpu": req.cpu_usage,
        "mem": req.memory_usage,
        "neighbors": req.neighbors_count,
        "uptime": req.uptime,
        "latency": req.latency_ms,
        "last_seen": last_seen.isoformat(),
        "reputation": trust_score,
    }
    if req.pheromones:
        telemetry_data["pheromones"] = req.pheromones
    degraded_dependencies: set[str] = set()
    before_snapshot_event_ids = _telemetry_event_ids(
        event_bus,
        operation="telemetry_snapshot_write",
    )
    _set_telemetry(
        req.node_id,
        telemetry_data,
        degraded_dependencies=degraded_dependencies,
        event_bus=event_bus,
        event_project_root=event_project_root,
        mesh_id=mesh_id,
    )
    snapshot_event_ids = sorted(
        _telemetry_event_ids(event_bus, operation="telemetry_snapshot_write")
        - before_snapshot_event_ids
    )
    for dependency in degraded_dependencies:
        mark_degraded_dependency(request, dependency)

    _publish_telemetry_observed_state(
        event_bus,
        operation="heartbeat",
        stage="heartbeat_processed",
        status="accepted",
        node_id=req.node_id,
        mesh_id=mesh_id,
        storage_backend=(
            "local_fallback"
            if "redis" in degraded_dependencies or not REDIS_AVAILABLE
            else "redis"
        ),
        read_only=False,
        heartbeat_summary={
            "db_node_found": db_node_found,
            "db_committed": db_committed,
            "registry_node_found": registry_node is not None,
            "client_ip_present": bool(client_ip),
            "client_ip_hash": _redacted_sha256_prefix(client_ip),
            "neighbors_count": int(req.neighbors_count),
            "routing_table_size": int(req.routing_table_size),
            "latency_ms": round(float(req.latency_ms), 3),
            "uptime_seconds": round(float(req.uptime), 3),
            "cpu_usage_present": isinstance(req.cpu_usage, (int, float)),
            "memory_usage_present": isinstance(req.memory_usage, (int, float)),
            "has_error_reports": has_errors,
            "error_reports_count": len(req.error_reports or []),
            "first_error_type_hash": _redacted_sha256_prefix(error_type),
            "has_pheromones": isinstance(req.pheromones, dict),
            "pheromone_destination_count": (
                len(req.pheromones) if isinstance(req.pheromones, dict) else 0
            ),
            "heartbeat_metric_recorded": heartbeat_metric_recorded,
            "telemetry_snapshot_events_total": len(snapshot_event_ids),
        },
        telemetry_summary=_telemetry_payload_summary(telemetry_data),
        trust_summary={
            "reputation_update_attempted": True,
            "reputation_update_success": reputation_update_success,
            "trust_score_after": round(float(trust_score), 6),
            "trust_source": (
                "reputation_system" if proxy_trust is not None else "default"
            ),
        },
        settlement_summary={
            "uptime_sample_attempted": uptime_sample_attempted,
            "uptime_sample_recorded": bool(REDIS_AVAILABLE),
            "settlement_uptime_ready": REDIS_AVAILABLE
            and _uptime_tracker_available(),
            "settlement_decision_made": False,
        },
        upstream_event_ids=snapshot_event_ids,
        degraded_dependencies=degraded_dependencies,
        duration_ms=(time.perf_counter() - started) * 1000,
        claim_boundary=_HEARTBEAT_CLAIM_BOUNDARY,
    )

    return {
        "status": "ack",
        "mesh_id": mesh_id,
        "trust_score": trust_score,
        "maas_telemetry_claim_gate": _maas_telemetry_claim_gate(
            surface="maas_telemetry.heartbeat_response",
            read_only=False,
            local_heartbeat_processing=True,
            local_uptime_sample_observation=uptime_sample_attempted,
            settlement_uptime_ready=REDIS_AVAILABLE
            and _uptime_tracker_available(),
        ),
    }

@root_router.get("/{mesh_id}/topology")
@router.get("/{mesh_id}/topology")
async def get_topology(
    mesh_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_maas)
):
    """Returns nodes and links for the D3.js dashboard from Redis."""
    event_bus = _telemetry_event_bus_from_request(request)
    try:
        mesh_context = _verify_topology_mesh_access(mesh_id, current_user, db)
    except HTTPException as exc:
        _publish_telemetry_observed_state(
            event_bus,
            operation="topology_access_check",
            stage="topology_access_check",
            status="denied",
            mesh_id=mesh_id,
            storage_backend="registry",
            read_only=True,
            topology_summary={
                "access_granted": False,
                "owner_checked": True,
            },
            reason=getattr(exc, "detail", "topology access denied"),
        )
        raise

    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()

    result_nodes = []
    links = []
    seen_links = set()
    degraded_dependencies: set[str] = set()
    node_evidence: List[Dict[str, Any]] = []

    for n in nodes:
        before_read_event_ids = _telemetry_event_ids(
            event_bus,
            operation="telemetry_snapshot_read",
        )
        telemetry = _get_telemetry(
            n.id,
            degraded_dependencies=degraded_dependencies,
            event_bus=event_bus,
            event_project_root=_telemetry_project_root_from_request(request),
            mesh_id=mesh_id,
        )
        telemetry_evidence = _topology_telemetry_evidence(
            event_bus,
            before_read_event_ids=before_read_event_ids,
            telemetry=telemetry,
            db_status=n.status,
            degraded_dependencies=degraded_dependencies,
        )
        node_evidence.append(telemetry_evidence)
        result_nodes.append({
            "id": n.id,
            "class": n.device_class,
            "status": _derive_topology_status(telemetry, n.status),
            "telemetry": telemetry,
            "telemetry_evidence": telemetry_evidence,
            "pqc_enabled": True # All MaaS nodes have PQC by default
        })

        # Extract links from pheromones
        if telemetry and "pheromones" in telemetry:
            pheromones = telemetry["pheromones"]
            if isinstance(pheromones, dict):
                for _destination_id, paths in pheromones.items():
                    if not isinstance(paths, dict):
                        continue
                    for neighbor_id, raw_score in paths.items():
                        if not isinstance(neighbor_id, str) or not neighbor_id:
                            continue
                        link_key = tuple(sorted([n.id, neighbor_id]))
                        if link_key in seen_links:
                            continue

                        links.append({
                            "source": n.id,
                            "target": neighbor_id,
                            "quality": _extract_pheromone_score(raw_score),
                            "secure": True, # PQC Tunnel
                            "type": "pqc-mesh"
                        })
                        seen_links.add(link_key)
    for dependency in degraded_dependencies:
        mark_degraded_dependency(request, dependency)

    _publish_telemetry_observed_state(
        event_bus,
        operation="topology_read",
        stage="topology_read",
        status="success",
        mesh_id=mesh_id,
        storage_backend="mixed",
        read_only=True,
        topology_summary={
            "access_granted": True,
            "mesh_source": mesh_context["mesh_source"],
            "owner_checked": mesh_context["owner_checked"],
            "node_count": len(result_nodes),
            "link_count": len(links),
            "degraded_dependencies_count": len(degraded_dependencies),
        },
        degraded_dependencies=degraded_dependencies,
    )

    return {
        "nodes": result_nodes,
        "links": links,
        "control_policy_evidence": _topology_control_policy_evidence(
            node_evidence=node_evidence,
            degraded_dependencies=degraded_dependencies,
        ),
    }
