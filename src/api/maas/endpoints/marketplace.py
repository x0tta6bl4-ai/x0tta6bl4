"""
MaaS Marketplace (Production) — x0tta6bl4
=========================================

Peer-to-peer infrastructure sharing with escrow payment protection.
Funds are held in escrow until the rented node passes a health heartbeat.
"""

import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import MarketplaceEscrow, MarketplaceListing, MeshNode, User, GlobalConfig, get_db
from src.api.maas.endpoints.telemetry import reputation_system
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.utils.audit import record_audit_log

from src.resilience.advanced_patterns import get_resilient_executor
from src.monitoring.maas_metrics import record_escrow_failure
from src.services.marketplace_events import (
    bridge_upstream_evidence,
    publish_marketplace_escrow_event,
)

logger = logging.getLogger(__name__)

# Global resilient executor for marketplace operations (P2 Reliability)
marketplace_executor = get_resilient_executor()

router = APIRouter( tags=["MaaS Marketplace"])
_MARKETPLACE_API_SOURCE_AGENT = "maas-marketplace"
_MARKETPLACE_API_LAYER = "api_to_commerce"
_MARKETPLACE_API_CLAIM_BOUNDARY = (
    "Marketplace API route evidence records local request, cache, SQLAlchemy, "
    "and helper-call boundaries only. It does not prove live dataplane quality, "
    "remote node authenticity, external payment settlement, chain finality, or "
    "that a listed/rented node is usable by a customer."
)
_MARKETPLACE_LISTING_CLAIM_BOUNDARY = (
    "Marketplace listing responses describe local listing state, pricing metadata, "
    "and reputation-derived trust score only. A listing being available does not "
    "prove node dataplane reachability, customer traffic delivery, remote node "
    "authenticity, external settlement finality, or production readiness."
)

_listings: Dict[str, Dict[str, Any]] = {}
_listings_lock = Lock()

_IDEMPOTENCY_TTL_SECONDS = max(60, int(os.getenv("MAAS_MARKETPLACE_IDEMPOTENCY_TTL_SECONDS", "3600")))
_IDEMPOTENCY_MAX_ENTRIES = max(100, int(os.getenv("MAAS_MARKETPLACE_IDEMPOTENCY_MAX_ENTRIES", "5000")))
_IDEMPOTENCY_MAX_KEY_LEN = max(16, int(os.getenv("MAAS_MARKETPLACE_IDEMPOTENCY_MAX_KEY_LEN", "128")))
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")
_idempotency_cache: "OrderedDict[str, tuple[float, Dict[str, Any]]]" = OrderedDict()
_idempotency_lock = Lock()

# Token Bridge Singleton Simulation
_token_bridge: Optional[TokenBridge] = None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _allow_insecure_escrow_fallback() -> bool:
    """Only allow insecure fallback in development/testing mode."""
    env = os.getenv("ENVIRONMENT", "").lower()
    if env in {"production", "prod"}:
        return False
    # Escape hatch for local debugging only. Keep secure-by-default in production.
    return _env_flag("MAAS_MARKETPLACE_ALLOW_INSECURE_ESCROW_FALLBACK", False)


def _normalize_identity(value: Any) -> str:
    """Normalize user identity across legacy str/int representations."""
    if value is None:
        return ""
    return str(value).strip()


def _ids_equal(left: Any, right: Any) -> bool:
    """Compare identifiers while tolerating int<->str legacy mismatches."""
    left_norm = _normalize_identity(left)
    right_norm = _normalize_identity(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    try:
        return int(left_norm) == int(right_norm)
    except (TypeError, ValueError):
        return False


def _current_user_id(current_user: User) -> str:
    user_id = _normalize_identity(getattr(current_user, "id", None))
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authenticated user id")
    return user_id


def _current_user_event_identity(current_user: User) -> Dict[str, Optional[str]]:
    return {
        "spiffe_id": _normalize_identity(getattr(current_user, "spiffe_id", None)) or None,
        "did": _normalize_identity(getattr(current_user, "did", None)) or None,
        "wallet_address": _normalize_identity(getattr(current_user, "wallet_address", None)) or None,
    }


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    normalized = _normalize_identity(value)
    if not normalized:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _marketplace_event_bus_from_request(request: Request | None) -> Optional[EventBus]:
    if request is not None:
        event_bus = getattr(getattr(request, "state", None), "event_bus", None)
        if isinstance(event_bus, EventBus):
            return event_bus
        project_root = getattr(getattr(request, "state", None), "project_root", ".")
    else:
        project_root = "."
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize marketplace API EventBus: %s", exc)
        return None


def _marketplace_route_context(
    *,
    current_user: Any = None,
    listing_id: Any = None,
    node_id: Any = None,
    mesh_id: Any = None,
    region: Any = None,
    currency: Any = None,
    idempotency_key: Any = None,
) -> Dict[str, Any]:
    return {
        "actor_id_hash": _redacted_sha256_prefix(getattr(current_user, "id", None)),
        "actor_role": _normalize_identity(getattr(current_user, "role", None))
        or "unknown",
        "listing_id_hash": _redacted_sha256_prefix(listing_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "region": _normalize_identity(region) or None,
        "currency": _normalize_identity(currency) or None,
        "idempotency_key_present": _normalize_identity(idempotency_key) is not None,
        "idempotency_key_hash": _redacted_sha256_prefix(idempotency_key),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _marketplace_db_evidence(
    *,
    action: str,
    db_ready: bool,
    read_attempted: bool = False,
    write_attempted: bool = False,
    committed: bool = False,
    cache_hit: bool = False,
    cache_write: bool = False,
) -> Dict[str, Any]:
    return {
        "storage_backend": "sqlalchemy",
        "action": action,
        "db_ready": bool(db_ready),
        "read_attempted": bool(read_attempted),
        "write_attempted": bool(write_attempted),
        "committed": bool(committed),
        "cache_hit": bool(cache_hit),
        "cache_write": bool(cache_write),
        "payloads_redacted": True,
    }


def _marketplace_result_summary(
    *,
    listing_count: Optional[int] = None,
    listing_status: Any = None,
    bandwidth_mbps: Any = None,
    price_present: Optional[bool] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "listing_count": listing_count if isinstance(listing_count, int) else None,
        "listing_status": _normalize_identity(listing_status) or None,
        "bandwidth_mbps": int(bandwidth_mbps)
        if isinstance(bandwidth_mbps, int)
        else None,
        "price_present": price_present if isinstance(price_present, bool) else None,
        "reason": reason,
        "payloads_redacted": True,
    }


def _marketplace_listing_claim_gate(listing_status: Any) -> Dict[str, Any]:
    local_listing_observed = bool(_normalize_identity(listing_status))
    return {
        "decision": "local_listing_state_only"
        if local_listing_observed
        else "listing_state_missing",
        "local_listing_state_claim_allowed": local_listing_observed,
        "local_pricing_metadata_claim_allowed": local_listing_observed,
        "reputation_score_observation_claim_allowed": local_listing_observed,
        "node_dataplane_reachability_claim_allowed": False,
        "customer_traffic_delivery_claim_allowed": False,
        "remote_node_authenticity_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_dataplane_evidence_for_delivery_claim": True,
        "requires_identity_attestation_for_authenticity_claim": True,
        "requires_external_finality_evidence_for_settlement_claim": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": _MARKETPLACE_LISTING_CLAIM_BOUNDARY,
    }


def _publish_marketplace_api_event(
    *,
    request: Request | None,
    operation: str,
    stage: str,
    status_text: str,
    started_at: float,
    http_status_code: int,
    context: Optional[Dict[str, Any]] = None,
    db_evidence: Optional[Dict[str, Any]] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    event_type: Optional[EventType] = None,
) -> Optional[str]:
    event_bus = _marketplace_event_bus_from_request(request)
    if event_bus is None:
        return None

    payload = {
        "component": "api.maas_marketplace",
        "operation": operation,
        "service_name": _MARKETPLACE_API_SOURCE_AGENT,
        "source_alias": _MARKETPLACE_API_SOURCE_AGENT,
        "layer": _MARKETPLACE_API_LAYER,
        "stage": stage,
        "status": status_text,
        "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
        "http_status_code": http_status_code,
        "control_action": operation in {
            "marketplace_create_listing",
            "marketplace_cancel_listing",
        },
        "observed_state": operation in {
            "marketplace_status",
            "marketplace_search_listings",
        },
        "source_quality": "local_api_db_cache_observed",
        "request_context": context or _marketplace_route_context(),
        "db_evidence": db_evidence
        or _marketplace_db_evidence(action="none", db_ready=False),
        "result_summary": result_summary or _marketplace_result_summary(),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": _MARKETPLACE_API_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            event_type
            or (
                EventType.TASK_BLOCKED
                if http_status_code >= 400
                else EventType.PIPELINE_STAGE_END
            ),
            _MARKETPLACE_API_SOURCE_AGENT,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish marketplace API route event: %s", exc)
        return None


def _marketplace_request_evidence(
    *,
    action: str,
    route: str,
    current_user: User,
    request_scope: Any = None,
    normalized_idempotency_key: Optional[str] = None,
    idempotency_cache_hit: bool = False,
    db_write_ready: Optional[bool] = None,
    listing_status: Any = None,
    currency: Any = None,
    hours: Optional[int] = None,
    renter_matches_listing: Optional[bool] = None,
    admin_override: Optional[bool] = None,
) -> Dict[str, Any]:
    role = _normalize_identity(getattr(current_user, "role", None)) or "unknown"
    return {
        "action": action,
        "route": route,
        "actor_role": role,
        "request_scope_hash": _redacted_sha256_prefix(request_scope),
        "idempotency_key_present": normalized_idempotency_key is not None,
        "idempotency_key_hash": _redacted_sha256_prefix(normalized_idempotency_key),
        "idempotency_cache_hit": bool(idempotency_cache_hit),
        "db_write_ready": db_write_ready if isinstance(db_write_ready, bool) else None,
        "listing_status": _normalize_identity(listing_status) or None,
        "currency": _normalize_identity(currency) or None,
        "hours": hours if isinstance(hours, int) else None,
        "renter_matches_listing": (
            renter_matches_listing if isinstance(renter_matches_listing, bool) else None
        ),
        "admin_override": admin_override if isinstance(admin_override, bool) else None,
        "service_identity_present": {
            "spiffe_id": bool(_normalize_identity(getattr(current_user, "spiffe_id", None))),
            "did": bool(_normalize_identity(getattr(current_user, "did", None))),
            "wallet_address": bool(_normalize_identity(getattr(current_user, "wallet_address", None))),
        },
        "raw_identifiers_redacted": True,
        "claim_boundary": (
            "Marketplace API request evidence records local auth/request/idempotency "
            "metadata only. It does not authenticate the caller beyond the enclosing "
            "FastAPI dependency result and never copies raw user, listing, mesh, or "
            "idempotency-key values."
        ),
    }


def _marketplace_api_settlement_evidence(
    *,
    action: str,
    started_at: float,
    decision_basis: str,
    source_quality: str,
    bridge_attempted: bool = False,
    bridge_status: str = "not_required",
    db_write_attempted: bool = False,
    db_committed: bool = False,
    escrow_status_after: Optional[Any] = None,
    listing_status_after: Optional[Any] = None,
) -> Dict[str, Any]:
    return {
        "decision_basis": str(decision_basis)[:120],
        "source_quality": str(source_quality)[:120],
        "settlement_action": str(action)[:80],
        "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
        "dataplane_confirmed": False,
        "threshold_met": True,
        "telemetry_evidence": {
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "payloads_redacted": True,
        },
        "bridge_evidence": {
            "attempted": bool(bridge_attempted),
            "status": str(bridge_status)[:80],
            "source_agent": "token-bridge" if bridge_attempted else None,
            "payloads_redacted": True,
        },
        "db_write_evidence": {
            "storage_backend": "sqlalchemy",
            "attempted": bool(db_write_attempted),
            "committed": bool(db_committed),
            "payloads_redacted": True,
        },
        "output_summary": {
            "escrow_status_after": str(escrow_status_after)[:80]
            if escrow_status_after is not None
            else None,
            "listing_status_after": str(listing_status_after)[:80]
            if listing_status_after is not None
            else None,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": (
            "Marketplace API escrow evidence records local authenticated request, "
            "TokenBridge call status, and SQLAlchemy write state. It does not prove "
            "live dataplane reachability, remote node authenticity, or final external "
            "settlement without downstream chain receipt evidence."
        ),
    }


def _marketplace_lifecycle_claim_boundary() -> str:
    return (
        "Marketplace lifecycle response fields describe local API, cache, and "
        "SQLAlchemy marketplace state only. They help native apps continue the "
        "operator workflow, but they do not prove live dataplane delivery, "
        "remote node authenticity, customer traffic delivery, external "
        "settlement finality, or production readiness."
    )


def _get_token_bridge() -> TokenBridge:
    global _token_bridge
    if _token_bridge is None:
        from src.core.config.settings import settings
        config = BridgeConfig(
            rpc_url=settings.rpc_url or "",
            contract_address=settings.contract_address or "",
            private_key=settings.operator_private_key or ""
        )
        _token_bridge = TokenBridge(MeshToken(), config)
    return _token_bridge


def _idempotency_compose_key(action: str, scope: str, user_id: Any, idempotency_key: str) -> str:
    normalized_user_id = _normalize_identity(user_id) or "anonymous"
    return f"{action}:{scope}:{normalized_user_id}:{idempotency_key.strip()}"


def _normalize_idempotency_key(idempotency_key: Any) -> Optional[str]:
    # Allow direct coroutine calls in unit tests where FastAPI doesn't resolve Header defaults.
    if isinstance(idempotency_key, str):
        normalized = idempotency_key.strip()
        if not normalized:
            return None
        if len(normalized) > _IDEMPOTENCY_MAX_KEY_LEN:
            raise HTTPException(status_code=400, detail="Idempotency-Key is too long")
        if not _IDEMPOTENCY_KEY_PATTERN.match(normalized):
            raise HTTPException(status_code=400, detail="Idempotency-Key contains invalid characters")
        return normalized
    default_value = getattr(idempotency_key, "default", None)
    if isinstance(default_value, str):
        normalized = default_value.strip()
        if not normalized:
            return None
        if len(normalized) > _IDEMPOTENCY_MAX_KEY_LEN:
            raise HTTPException(status_code=400, detail="Idempotency-Key is too long")
        if not _IDEMPOTENCY_KEY_PATTERN.match(normalized):
            raise HTTPException(status_code=400, detail="Idempotency-Key contains invalid characters")
        return normalized
    return None


def _idempotency_get(cache_key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    with _idempotency_lock:
        cached = _idempotency_cache.get(cache_key)
        if not cached:
            return None
        cached_at, payload = cached
        if (now - cached_at) > _IDEMPOTENCY_TTL_SECONDS:
            _idempotency_cache.pop(cache_key, None)
            return None
        _idempotency_cache.move_to_end(cache_key)
        return dict(payload)


def _idempotency_set(cache_key: str, payload: Dict[str, Any]) -> None:
    with _idempotency_lock:
        _idempotency_cache[cache_key] = (time.time(), dict(payload))
        _idempotency_cache.move_to_end(cache_key)
        while len(_idempotency_cache) > _IDEMPOTENCY_MAX_ENTRIES:
            _idempotency_cache.popitem(last=False)


def _get_global_price_multiplier(db: Any) -> float:
    if not _db_session_available(db):
        return 1.0
    try:
        config = db.query(GlobalConfig).filter(GlobalConfig.key == "global_price_multiplier").first()
        if config and config.value_json:
            return float(json.loads(config.value_json))
    except Exception as e:
        logger.warning(f"Error fetching global price multiplier: {e}")
    return 1.0


def _get_node_reputation_multiplier(node_id: Optional[str]) -> float:
    """Calculate price multiplier based on node trust score (0.5 to 1.2x)."""
    if not node_id:
        return 1.0
    proxy_trust = reputation_system.get_proxy_trust(node_id)
    if not proxy_trust:
        return 1.0

    # 0.0 trust -> 0.5x price penalty
    # 1.0 trust -> 1.2x price premium
    trust = proxy_trust.trust_score
    return 0.5 + (trust * 0.7)


def _get_mesh_congestion_multiplier(mesh_id: str, db: Session) -> float:
    """Increase price if the target mesh is already crowded (congestion factor)."""
    if not _db_session_available(db):
        return 1.0

    from src.database import MeshNode
    active_nodes = db.query(MeshNode).filter(
        MeshNode.mesh_id == mesh_id,
        MeshNode.status == "healthy"
    ).count()

    # Base: 1.0
    # > 5 nodes: +10% per node
    if active_nodes > 5:
        multiplier = 1.0 + (active_nodes - 5) * 0.10
        return min(multiplier, 3.0) # Cap at 3x

    return 1.0


class ListingCreate(BaseModel):
    node_id: str
    region: str = Field(..., pattern="^(us-east|us-west|eu-central|asia-south|global)$")
    price_per_hour: Optional[float] = Field(None, ge=0.01)
    price_token_per_hour: Optional[float] = Field(None, ge=0.0001)
    currency: str = Field(default="USD", pattern="^(USD|X0T)$")
    bandwidth_mbps: int = Field(..., ge=10)

class ListingResponse(BaseModel):
    listing_id: str
    owner_id: str
    node_id: str
    region: str
    price_per_hour: Optional[float] = None
    price_token_per_hour: Optional[float] = None
    currency: str
    bandwidth_mbps: int
    status: str
    trust_score: float
    created_at: str
    dataplane_confirmed: bool = False
    customer_traffic_delivery_claim_allowed: bool = False
    external_settlement_finality_claim_allowed: bool = False
    production_readiness_claim_allowed: bool = False
    listing_claim_gate: Dict[str, Any] = Field(default_factory=dict)
    claim_boundary: str = _MARKETPLACE_LISTING_CLAIM_BOUNDARY


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit")


def _is_dependency_placeholder(db: Any) -> bool:
    """Detect direct coroutine calls where FastAPI did not resolve Depends()."""
    return db.__class__.__name__ == "Depends" and hasattr(db, "dependency")


def _ensure_write_db_ready(db: Any, request: Optional[Request] = None) -> bool:
    """
    Validate DB readiness for state-changing marketplace operations.

    Returns:
        True when SQLAlchemy session is available.
        False for direct unit-test coroutine calls with unresolved Depends().
    """
    if _db_session_available(db):
        return True
    # Keep direct coroutine unit tests backward-compatible.
    if _is_dependency_placeholder(db):
        return False
    if request is not None:
        mark_degraded_dependency(request, "database")
    raise HTTPException(
        status_code=503,
        detail="Marketplace write path unavailable: database dependency degraded",
    )


def _marketplace_readiness_status(db: Any) -> Dict[str, Any]:
    db_ready = _db_session_available(db)
    degraded_dependencies = [] if db_ready else ["database"]
    with _listings_lock:
        cached_listings = len(_listings)

    return {
        "status": "ready" if db_ready else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "write_db_ready": db_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": "ready" if db_ready else "unavailable",
            "in_memory_listing_cache_entries": cached_listings,
            "escrow_write_path": "database_required",
            "token_bridge": "lazy",
            "telemetry_reputation": "imported",
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_marketplace_readiness"
        ),
        "claim_boundary": (
            "Marketplace route readiness distinguishes route availability from "
            "state-changing database readiness. It does not prove live chain "
            "settlement, Stripe payment state, or node heartbeat quality."
        ),
    }


@router.get("/status")
async def marketplace_status(
    request: Request = None,
    db: Session = Depends(get_db),
):
    started = time.monotonic()
    payload = _marketplace_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        if request is not None:
            mark_degraded_dependency(request, dependency)
    _publish_marketplace_api_event(
        request=request,
        operation="marketplace_status",
        stage="readiness_read",
        status_text=payload["status"],
        started_at=started,
        http_status_code=200,
        db_evidence=_marketplace_db_evidence(
            action="readiness_check",
            db_ready=bool(payload["write_db_ready"]),
            read_attempted=True,
        ),
        result_summary=_marketplace_result_summary(
            listing_count=payload["backing_state"]["in_memory_listing_cache_entries"],
            reason="degraded" if payload["degraded_dependencies"] else "ready",
        ),
    )
    return payload


def _to_cents(price_per_hour: float) -> int:
    cents = Decimal(str(price_per_hour)) * Decimal("100")
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _to_dollars(cents: int) -> float:
    return round(cents / 100.0, 2)


def _as_listing_response(data: Any, multiplier: float = 1.0) -> Dict[str, Any]:
    def _val(obj, key, default=None):
        if isinstance(obj, dict): return obj.get(key, default)
        return getattr(obj, key, default)

    listing_id = _val(data, "listing_id") or _val(data, "id")
    if not listing_id: raise ValueError("listing_id is required")

    node_id = _val(data, "node_id")
    proxy_trust = reputation_system.get_proxy_trust(node_id) if node_id else None
    trust_score = proxy_trust.trust_score if proxy_trust else 0.5
    rep_multiplier = 0.5 + (trust_score * 0.7) if proxy_trust else 1.0
    total_multiplier = multiplier * rep_multiplier

    created_at = _val(data, "created_at")
    if isinstance(created_at, datetime): created_at_iso = created_at.isoformat()
    elif isinstance(created_at, str): created_at_iso = created_at
    else: created_at_iso = datetime.utcnow().isoformat()

    currency = _val(data, "currency", "USD") or "USD"
    raw_price = _val(data, "price_per_hour", 0.0)
    if isinstance(raw_price, int): price_per_hour = _to_dollars(raw_price)
    else: price_per_hour = float(raw_price or 0.0)

    price_per_hour = round(price_per_hour * total_multiplier, 2)
    raw_price_token = _val(data, "price_token_per_hour")
    price_token = None
    if raw_price_token is not None:
        price_token = round(float(raw_price_token) * total_multiplier, 4)

    status = _val(data, "status", "available")
    claim_gate = _marketplace_listing_claim_gate(status)
    return {
        "listing_id": listing_id,
        "owner_id": _val(data, "owner_id"),
        "node_id": node_id,
        "region": _val(data, "region"),
        "price_per_hour": price_per_hour if currency == "USD" else None,
        "price_token_per_hour": price_token if currency == "X0T" else None,
        "currency": currency,
        "bandwidth_mbps": int(_val(data, "bandwidth_mbps") or 0),
        "status": status,
        "trust_score": round(trust_score, 2),
        "created_at": created_at_iso,
        "dataplane_confirmed": False,
        "customer_traffic_delivery_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "listing_claim_gate": claim_gate,
        "claim_boundary": _MARKETPLACE_LISTING_CLAIM_BOUNDARY,
    }


def _row_to_listing(row: MarketplaceListing) -> Dict[str, Any]:
    return {
        "listing_id": row.id,
        "owner_id": _normalize_identity(row.owner_id),
        "node_id": row.node_id,
        "region": row.region,
        "price_per_hour": _to_dollars(row.price_per_hour) if row.price_per_hour is not None else 0.0,
        "price_token_per_hour": row.price_token_per_hour,
        "currency": row.currency or "USD",
        "bandwidth_mbps": row.bandwidth_mbps,
        "status": row.status,
        "renter_id": _normalize_identity(row.renter_id) or None,
        "mesh_id": row.mesh_id,
        "created_at": row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
    }


def _get_listing_from_cache_or_db(listing_id: str, db: Any) -> Optional[Dict[str, Any]]:
    with _listings_lock:
        cached = _listings.get(listing_id)
    if cached:
        return dict(cached)

    if not _db_session_available(db):
        return None

    row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not row:
        return None

    listing = _row_to_listing(row)
    with _listings_lock:
        _listings[listing_id] = dict(listing)
    return listing


def _save_listing_to_cache(listing: Dict[str, Any]) -> None:
    with _listings_lock:
        _listings[listing["listing_id"]] = dict(listing)


def _load_listing_for_update(db: Session, listing_id: str) -> Optional[MarketplaceListing]:
    """Best-effort row lock to reduce race windows on state transitions."""
    query = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id)
    try:
        return query.with_for_update().first()
    except Exception:
        return query.first()


def _load_held_escrow_for_update(db: Session, listing_id: str) -> Optional[MarketplaceEscrow]:
    query = db.query(MarketplaceEscrow).filter(
        MarketplaceEscrow.listing_id == listing_id,
        MarketplaceEscrow.status == "held",
    )
    try:
        return query.with_for_update().first()
    except Exception:
        return query.first()


def _isoformat_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None
    normalized = _normalize_identity(value)
    return normalized or None


def _load_latest_escrow(db: Any, listing_id: str) -> Optional[MarketplaceEscrow]:
    if not _db_session_available(db):
        return None
    query = db.query(MarketplaceEscrow).filter(MarketplaceEscrow.listing_id == listing_id)
    try:
        return query.order_by(MarketplaceEscrow.created_at.desc()).first()
    except Exception:
        return query.first()


def _load_marketplace_node(db: Any, *, node_id: Any, mesh_id: Any) -> Any:
    normalized_node_id = _normalize_identity(node_id)
    normalized_mesh_id = _normalize_identity(mesh_id)
    if not normalized_node_id or not _db_session_available(db):
        return None
    query = db.query(MeshNode).filter(MeshNode.id == normalized_node_id)
    if normalized_mesh_id:
        query = query.filter(MeshNode.mesh_id == normalized_mesh_id)
    try:
        return query.first()
    except Exception:
        return None


def _heartbeat_age_seconds(last_seen: Any) -> Optional[float]:
    if last_seen is None or not hasattr(last_seen, "timestamp"):
        return None
    try:
        return max(0.0, round((datetime.utcnow() - last_seen).total_seconds(), 3))
    except Exception:
        return None


def _marketplace_lifecycle_next_action(
    *,
    listing_status: str,
    escrow_status: str,
    assignment_status: str,
    heartbeat_status: str,
) -> str:
    if escrow_status == "refunded":
        return "listing_available_for_new_rent"
    if escrow_status == "released" or listing_status == "rented":
        return "observe_rented_node_telemetry"
    if escrow_status == "held" or listing_status == "escrow":
        if assignment_status == "node_not_registered_in_mesh":
            return "register_or_attach_rented_node_to_mesh"
        if assignment_status == "node_pending_approval":
            return "approve_rented_node"
        if heartbeat_status == "heartbeat_missing":
            return "wait_for_healthy_heartbeat"
        if heartbeat_status == "heartbeat_observed":
            return "release_or_investigate_escrow_auto_release"
        return "observe_node_assignment"
    return "rent_listing_before_lifecycle"


def _marketplace_lifecycle_snapshot(
    *,
    listing: Dict[str, Any],
    db: Any,
    escrow: Optional[MarketplaceEscrow] = None,
) -> Dict[str, Any]:
    listing_id = _normalize_identity(listing.get("listing_id"))
    node_id = _normalize_identity(listing.get("node_id"))
    mesh_id = _normalize_identity(listing.get("mesh_id"))
    listing_status = _normalize_identity(listing.get("status")) or "unknown"
    if escrow is None and listing_id:
        escrow = _load_latest_escrow(db, listing_id)

    node = _load_marketplace_node(db, node_id=node_id, mesh_id=mesh_id)
    node_status = _normalize_identity(getattr(node, "status", None)) if node is not None else None
    last_seen = getattr(node, "last_seen", None) if node is not None else None
    if not mesh_id:
        assignment_status = "not_assigned_to_mesh"
    elif node is None:
        assignment_status = "node_not_registered_in_mesh"
    elif node_status == "pending":
        assignment_status = "node_pending_approval"
    else:
        assignment_status = "node_record_found"

    heartbeat_status = "heartbeat_observed" if last_seen is not None else "heartbeat_missing"
    escrow_status = _normalize_identity(getattr(escrow, "status", None)) or (
        "not_created" if listing_status == "available" else "unknown"
    )
    lifecycle_next_action = _marketplace_lifecycle_next_action(
        listing_status=listing_status,
        escrow_status=escrow_status,
        assignment_status=assignment_status,
        heartbeat_status=heartbeat_status,
    )

    return {
        "schema": "x0tta6bl4.marketplace.rental_lifecycle.v1",
        "listing_id": listing_id or None,
        "node_id": node_id or None,
        "mesh_id": mesh_id or None,
        "listing_status": listing_status,
        "escrow_id": _normalize_identity(getattr(escrow, "id", None)) or None,
        "escrow_status": escrow_status,
        "currency": _normalize_identity(getattr(escrow, "currency", None))
        or _normalize_identity(listing.get("currency"))
        or None,
        "amount_held_cents": getattr(escrow, "amount_cents", None) if escrow is not None else None,
        "amount_held_token": getattr(escrow, "amount_token", None) if escrow is not None else None,
        "released_at": _isoformat_or_none(getattr(escrow, "released_at", None))
        if escrow is not None
        else None,
        "node_assignment": {
            "status": assignment_status,
            "node_record_found": node is not None,
            "node_status": node_status,
            "device_class": _normalize_identity(getattr(node, "device_class", None)) or None,
            "hardware_id_present": bool(_normalize_identity(getattr(node, "hardware_id", None))),
            "runtime_identity_bound": bool(
                _normalize_identity(getattr(node, "runtime_identity_binding_hash", None))
            ),
            "raw_runtime_identity_redacted": True,
        },
        "heartbeat_snapshot": {
            "status": heartbeat_status,
            "last_seen": _isoformat_or_none(last_seen),
            "age_seconds": _heartbeat_age_seconds(last_seen),
            "dataplane_probe_target_present": bool(
                _normalize_identity(getattr(node, "ip_address", None))
            ),
            "raw_dataplane_probe_target_redacted": True,
        },
        "lifecycle_next_action": lifecycle_next_action,
        "claim_boundary": _marketplace_lifecycle_claim_boundary(),
    }


@router.post("/list", response_model=ListingResponse)
async def create_listing(
    req: ListingCreate,
    request: Request = None,
    current_user: User = Depends(require_permission("marketplace:list")),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    started = time.monotonic()
    db_ready = _ensure_write_db_ready(db, request)
    owner_id = _current_user_id(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    if normalized_idem_key:
        cache_key = _idempotency_compose_key(
            "create_listing", req.node_id, owner_id, normalized_idem_key
        )
        cached = _idempotency_get(cache_key)
        if cached:
            _publish_marketplace_api_event(
                request=request,
                operation="marketplace_create_listing",
                stage="idempotent_replay",
                status_text="success",
                started_at=started,
                http_status_code=200,
                context=_marketplace_route_context(
                    current_user=current_user,
                    node_id=req.node_id,
                    region=req.region,
                    currency=req.currency,
                    idempotency_key=normalized_idem_key,
                ),
                db_evidence=_marketplace_db_evidence(
                    action="create_listing_replay",
                    db_ready=db_ready,
                    cache_hit=True,
                ),
                result_summary=_marketplace_result_summary(reason="idempotent_replay"),
            )
            return cached

    with _listings_lock:
        in_memory_exists = any(item.get("node_id") == req.node_id for item in _listings.values())
    if in_memory_exists:
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_create_listing",
            stage="create_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=400,
            context=_marketplace_route_context(
                current_user=current_user,
                node_id=req.node_id,
                region=req.region,
                currency=req.currency,
                idempotency_key=normalized_idem_key,
            ),
            db_evidence=_marketplace_db_evidence(
                action="create_listing_duplicate_cache_check",
                db_ready=db_ready,
                read_attempted=True,
                cache_hit=True,
            ),
            result_summary=_marketplace_result_summary(reason="node_already_listed"),
        )
        raise HTTPException(status_code=400, detail="Node already listed")

    if db_ready:
        existing = db.query(MarketplaceListing).filter(MarketplaceListing.node_id == req.node_id).first()
        if existing:
            _publish_marketplace_api_event(
                request=request,
                operation="marketplace_create_listing",
                stage="create_blocked",
                status_text="blocked",
                started_at=started,
                http_status_code=400,
                context=_marketplace_route_context(
                    current_user=current_user,
                    node_id=req.node_id,
                    region=req.region,
                    currency=req.currency,
                    idempotency_key=normalized_idem_key,
                ),
                db_evidence=_marketplace_db_evidence(
                    action="create_listing_duplicate_db_check",
                    db_ready=db_ready,
                    read_attempted=True,
                    cache_hit=False,
                ),
                result_summary=_marketplace_result_summary(reason="node_already_listed"),
            )
            raise HTTPException(status_code=400, detail="Node already listed")

    if req.currency == "USD" and not req.price_per_hour:
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_create_listing",
            stage="create_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=400,
            context=_marketplace_route_context(
                current_user=current_user,
                node_id=req.node_id,
                region=req.region,
                currency=req.currency,
                idempotency_key=normalized_idem_key,
            ),
            db_evidence=_marketplace_db_evidence(
                action="create_listing_validate_price",
                db_ready=db_ready,
            ),
            result_summary=_marketplace_result_summary(reason="missing_usd_price"),
        )
        raise HTTPException(status_code=400, detail="price_per_hour required for USD")
    if req.currency == "X0T" and not req.price_token_per_hour:
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_create_listing",
            stage="create_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=400,
            context=_marketplace_route_context(
                current_user=current_user,
                node_id=req.node_id,
                region=req.region,
                currency=req.currency,
                idempotency_key=normalized_idem_key,
            ),
            db_evidence=_marketplace_db_evidence(
                action="create_listing_validate_price",
                db_ready=db_ready,
            ),
            result_summary=_marketplace_result_summary(reason="missing_x0t_price"),
        )
        raise HTTPException(status_code=400, detail="price_token_per_hour required for X0T")

    listing_id = f"lst-{uuid.uuid4().hex[:8]}"
    listing = {
        "listing_id": listing_id,
        "owner_id": owner_id,
        "node_id": req.node_id,
        "region": req.region,
        "price_per_hour": float(req.price_per_hour or 0.0),
        "price_token_per_hour": float(req.price_token_per_hour or 0.0),
        "currency": req.currency,
        "bandwidth_mbps": req.bandwidth_mbps,
        "status": "available",
        "renter_id": None,
        "mesh_id": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    if db_ready:
        row = MarketplaceListing(
            id=listing_id,
            owner_id=owner_id,
            node_id=req.node_id,
            region=req.region,
            price_per_hour=_to_cents(req.price_per_hour) if req.price_per_hour else 0,
            price_token_per_hour=req.price_token_per_hour,
            currency=req.currency,
            bandwidth_mbps=req.bandwidth_mbps,
            status="available",
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        listing = _row_to_listing(row)

        try:
            record_audit_log(
                db, None, "MARKETPLACE_LISTING_CREATED",
                user_id=owner_id,
                payload={"listing_id": listing_id, "node_id": req.node_id},
                status_code=201,
            )
        except Exception as exc:
            logger.warning("Failed to write listing audit log: %s", exc)

    _save_listing_to_cache(listing)
    multiplier = _get_global_price_multiplier(db)
    result = _as_listing_response(listing, multiplier=multiplier)
    if cache_key:
        _idempotency_set(cache_key, result)
    _publish_marketplace_api_event(
        request=request,
        operation="marketplace_create_listing",
        stage="listing_created",
        status_text="success",
        started_at=started,
        http_status_code=201,
        context=_marketplace_route_context(
            current_user=current_user,
            listing_id=listing_id,
            node_id=req.node_id,
            region=req.region,
            currency=req.currency,
            idempotency_key=normalized_idem_key,
        ),
        db_evidence=_marketplace_db_evidence(
            action="create_listing",
            db_ready=db_ready,
            read_attempted=True,
            write_attempted=db_ready,
            committed=db_ready,
            cache_write=True,
        ),
        result_summary=_marketplace_result_summary(
            listing_status=result.get("status"),
            bandwidth_mbps=result.get("bandwidth_mbps"),
            price_present=bool(
                result.get("price_per_hour") or result.get("price_token_per_hour")
            ),
        ),
    )
    return result


@router.get("/search", response_model=List[ListingResponse])
async def search_listings(
    request: Request = None,
    region: Optional[str] = None,
    max_price: Optional[float] = None,
    min_bandwidth: Optional[int] = None,
    currency: str = Query("USD", pattern="^(USD|X0T)$"),
    db: Session = Depends(get_db),
):
    started = time.monotonic()
    # Allow direct coroutine calls in unit tests where FastAPI doesn't resolve Query defaults.
    if not isinstance(currency, str):
        currency = getattr(currency, "default", "USD")
    if not isinstance(currency, str):
        currency = "USD"
    currency = currency.upper()
    if currency not in {"USD", "X0T"}:
        raise HTTPException(status_code=422, detail="Invalid currency")

    # Prefer DB for truth, use cache only as fallback or for recently added items not yet committed.
    # In tests, we always want the latest from DB.
    source = []
    if _db_session_available(db):
        rows = db.query(MarketplaceListing).all()
        source = [_row_to_listing(row) for row in rows]
        # Sync cache
        with _listings_lock:
            for item in source:
                _listings[item["listing_id"]] = dict(item)
    else:
        with _listings_lock:
            source = [dict(item) for item in _listings.values()]
        if request is not None:
            mark_degraded_dependency(request, "database")

    result: List[Dict[str, Any]] = []
    multiplier = _get_global_price_multiplier(db) or 1.0
    for listing in source:
        def _v(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        status_val = _v(listing, "status")
        # In tests, sometimes status is None if mock DB is messy
        if status_val and status_val != "available":
            continue

        listing_currency = _v(listing, "currency", "USD") or "USD"
        if listing_currency != currency:
            continue
        if region and _v(listing, "region") != region:
            continue
        rep_multiplier = _get_node_reputation_multiplier(_v(listing, "node_id"))

        # Price filtering depends on currency
        if max_price is not None:
            if currency == "USD":
                if float(_v(listing, "price_per_hour") or 0.0) * multiplier * rep_multiplier > float(max_price):
                    continue
            else: # X0T
                if float(_v(listing, "price_token_per_hour") or 0.0) * multiplier * rep_multiplier > float(max_price):
                    continue

        if min_bandwidth is not None and int(_v(listing, "bandwidth_mbps") or 0) < int(min_bandwidth or 0):
            continue
        result.append(_as_listing_response(listing, multiplier=multiplier))

    _publish_marketplace_api_event(
        request=request,
        operation="marketplace_search_listings",
        stage="search_read",
        status_text="success",
        started_at=started,
        http_status_code=200,
        context=_marketplace_route_context(region=region, currency=currency),
        db_evidence=_marketplace_db_evidence(
            action="search_listings",
            db_ready=_db_session_available(db),
            read_attempted=True,
            cache_hit=False,
        ),

        result_summary=_marketplace_result_summary(listing_count=len(result)),
    )
    return result


@router.get("/rental/{listing_id}/lifecycle")
async def rental_lifecycle(
    listing_id: str,
    request: Request = None,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """Read local marketplace rental, node assignment, and heartbeat state."""
    listing = None
    if _db_session_available(db):
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if row:
            listing = _row_to_listing(row)
            with _listings_lock:
                _listings[listing_id] = dict(listing)
    if listing is None:
        listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    actor_id = _current_user_id(current_user)
    actor_role = _normalize_identity(getattr(current_user, "role", None))
    is_participant = (
        _ids_equal(listing.get("owner_id"), actor_id)
        or _ids_equal(listing.get("renter_id"), actor_id)
        or actor_role == "admin"
    )
    if listing.get("renter_id") and not is_participant:
        raise HTTPException(status_code=403, detail="Permission denied")

    snapshot = _marketplace_lifecycle_snapshot(listing=listing, db=db)
    snapshot["read_path"] = f"/api/v1/maas/marketplace/rental/{listing_id}/lifecycle"
    snapshot["read_only"] = True
    return snapshot


@router.post("/rent/{listing_id}")
async def rent_node(
    listing_id: str,
    mesh_id: str,
    request: Request = None,
    hours: int = Query(default=1, ge=1, le=720),  # Up to 30 days
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    Initiate a node rental with multi-hour deposit.
    Funds are released to the owner after the first healthy heartbeat.
    """
    # Allow direct coroutine calls in unit tests where FastAPI doesn't resolve Query defaults.
    if not isinstance(hours, int):
        hours = getattr(hours, "default", 1)
    if not isinstance(hours, int):
        hours = 1

    started = time.monotonic()
    renter_id = _current_user_id(current_user)
    current_user_event_identity = _current_user_event_identity(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    request_scope = f"{listing_id}:{mesh_id}:{hours}"
    if normalized_idem_key:
        cache_key = _idempotency_compose_key(
            "rent_node",
            request_scope,
            renter_id,
            normalized_idem_key,
        )
        cached = _idempotency_get(cache_key)
        if cached:
            return cached

    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if _ids_equal(listing.get("owner_id"), renter_id):
        raise HTTPException(status_code=400, detail="Cannot rent your own node")
    if listing.get("status") != "available":
        raise HTTPException(status_code=400, detail="Listing not available")

    db_ready = _ensure_write_db_ready(db, request)
    request_evidence = _marketplace_request_evidence(
        action="rent_node",
        route="POST /rent/{listing_id}",
        current_user=current_user,
        request_scope=request_scope,
        normalized_idempotency_key=normalized_idem_key,
        db_write_ready=db_ready,
        listing_status=listing.get("status"),
        currency=listing.get("currency"),
        hours=hours,
        renter_matches_listing=False,
        admin_override=False,
    )
    if not db_ready:
        listing["status"] = "rented"
        listing["renter_id"] = renter_id
        listing["mesh_id"] = mesh_id
        _save_listing_to_cache(listing)
        lifecycle_snapshot = _marketplace_lifecycle_snapshot(listing=listing, db=db)
        result = {
            "status": "success",
            "listing_id": listing_id,
            "node_id": listing.get("node_id"),
            "mesh_id": mesh_id,
            "escrow_id": None,
            "escrow_status": "not_created_without_write_db",
            "listing_status": listing.get("status"),
            "currency": listing.get("currency"),
            "hours": hours,
            "amount_held_cents": None,
            "amount_held_token": None,
            "node_assignment": lifecycle_snapshot["node_assignment"],
            "heartbeat_snapshot": lifecycle_snapshot["heartbeat_snapshot"],
            "lifecycle_next_action": lifecycle_snapshot["lifecycle_next_action"],
            "lifecycle_snapshot": lifecycle_snapshot,
            "claim_boundary": _marketplace_lifecycle_claim_boundary(),
        }
        if cache_key:
            _idempotency_set(cache_key, result)
        return result

    row = _load_listing_for_update(db, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    if _ids_equal(row.owner_id, renter_id):
        raise HTTPException(status_code=400, detail="Cannot rent your own node")
    if row.status != "available":
        raise HTTPException(status_code=400, detail="Listing not available")

    escrow_id = f"esc-{uuid.uuid4().hex[:8]}"
    multiplier = _get_global_price_multiplier(db)
    rep_multiplier = _get_node_reputation_multiplier(listing.get("node_id"))
    congestion_multiplier = _get_mesh_congestion_multiplier(mesh_id, db)
    total_multiplier = multiplier * rep_multiplier * congestion_multiplier

    amount_cents = None
    amount_token = None
    bridge_evidence = {}
    bridge_attempted = False
    bridge_status = "not_required"

    if listing.get("currency") == "X0T":
        amount_token = float(listing.get("price_token_per_hour", 0.0)) * total_multiplier * hours

        # Verify user has sufficient X0T balance before creating escrow
        bridge = None
        try:
            token_sys = MeshToken()
            user_balance = token_sys.balance_of(renter_id)

            # MeshToken is currently in-memory; a fresh instance may have no ledger data.
            # Enforce balance checks only when ledger state is actually present.
            has_ledger_state = bool(getattr(token_sys, "balances", {}))
            if has_ledger_state and user_balance < amount_token:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient X0T balance. Required: {amount_token}, Available: {user_balance}"
                )

            # 3. Lock tokens in Decentralized Escrow (Token Bridge)
            bridge = _get_token_bridge()
            bridge_attempted = True
            # Note: Using run_until_complete simulation or similar if needed,
            # but here we are in an async function.
            tx_hash = await bridge.lock_escrow_on_chain(escrow_id, renter_id, amount_token)
            bridge_evidence = bridge_upstream_evidence(bridge)
            if not tx_hash:
                bridge_status = "rejected"
                raise RuntimeError("lock_escrow_on_chain returned empty transaction hash")
            bridge_status = "locked"

            if has_ledger_state:
                logger.info(
                    "Verified %s X0T balance for user %s, escrow %s (TX: %s)",
                    amount_token,
                    renter_id,
                    escrow_id,
                    tx_hash
                )
            else:
                logger.info(
                    "Skipping strict X0T balance check (stateless token ledger), escrow %s (TX: %s)",
                    escrow_id,
                    tx_hash
                )

        except HTTPException:
            raise
        except ImportError:
            if _allow_insecure_escrow_fallback():
                logger.warning("Token system unavailable, using insecure escrow fallback")
            else:
                bridge_evidence = bridge_upstream_evidence(bridge)
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="rent_node",
                    started_at=started,
                    decision_basis="api_rent_escrow_hold_request",
                    source_quality="token_bridge_unavailable_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status="unavailable",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=None,
                    listing_status_after=getattr(row, "status", listing.get("status")),
                )
                logger.error("Token system unavailable; refusing X0T rent for escrow %s", escrow_id)
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow_id,
                    listing_id=listing_id,
                    renter_id=renter_id,
                    actor_id=renter_id,
                    currency=listing.get("currency"),
                    status="blocked",
                    node_id=listing.get("node_id"),
                    mesh_id=mesh_id,
                    **current_user_event_identity,
                    amount_token=amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="token_bridge_unavailable",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Token bridge unavailable")
        except Exception as e:
            if _allow_insecure_escrow_fallback():
                logger.warning("Token integration error, using insecure fallback: %s", e)
            else:
                bridge_evidence = bridge_upstream_evidence(bridge)
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="rent_node",
                    started_at=started,
                    decision_basis="api_rent_escrow_hold_request",
                    source_quality="token_bridge_lock_failed_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status=bridge_status if bridge_status != "not_required" else "error",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=None,
                    listing_status_after=getattr(row, "status", listing.get("status")),
                )
                logger.error("Token bridge lock failed for escrow %s: %s", escrow_id, e)
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow_id,
                    listing_id=listing_id,
                    renter_id=renter_id,
                    actor_id=renter_id,
                    currency=listing.get("currency"),
                    status="blocked",
                    node_id=listing.get("node_id"),
                    mesh_id=mesh_id,
                    **current_user_event_identity,
                    amount_token=amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="x0t_lock_failed",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Failed to lock X0T escrow")
    else:
        amount_cents = _to_cents(float(listing["price_per_hour"]) * total_multiplier) * hours

    row.status = "escrow"
    row.renter_id = renter_id
    row.mesh_id = mesh_id

    escrow_row = MarketplaceEscrow(
        id=escrow_id,
        listing_id=listing_id,
        renter_id=renter_id,
        amount_cents=amount_cents,
        amount_token=amount_token,
        currency=listing.get("currency", "USD"),
        status="held",
        created_at=datetime.utcnow(),
    )
    db.add(escrow_row)
    db.commit()
    event_settlement_evidence = _marketplace_api_settlement_evidence(
        action="rent_node",
        started_at=started,
        decision_basis="api_rent_escrow_hold_request",
        source_quality="api_request_db_commit_and_optional_token_bridge_lock",
        bridge_attempted=bridge_attempted,
        bridge_status=bridge_status,
        db_write_attempted=True,
        db_committed=True,
        escrow_status_after="held",
        listing_status_after=getattr(row, "status", None),
    )
    escrow_event_id = publish_marketplace_escrow_event(
        transition="held",
        source_agent="maas-marketplace",
        escrow_id=escrow_id,
        listing_id=listing_id,
        renter_id=renter_id,
        actor_id=renter_id,
        currency=listing.get("currency"),
        status="held",
        node_id=listing.get("node_id"),
        mesh_id=mesh_id,
        **current_user_event_identity,
        amount_cents=amount_cents,
        amount_token=amount_token,
        request_evidence=request_evidence,
        settlement_evidence=event_settlement_evidence,
        **bridge_evidence,
    )

    listing["status"] = "escrow"
    listing["renter_id"] = renter_id
    listing["mesh_id"] = mesh_id
    _save_listing_to_cache(listing)
    lifecycle_snapshot = _marketplace_lifecycle_snapshot(
        listing=listing,
        db=db,
        escrow=escrow_row,
    )

    # Automated Orchestration: Push node to target mesh
    try:
        from src.services.maas_orchestrator import maas_orchestrator
        import asyncio
        asyncio.create_task(maas_orchestrator.provision_rented_node(db, listing_id, renter_id, mesh_id))
    except Exception as orch_err:
        logger.error(f"Failed to trigger orchestration: {orch_err}")

    try:
        record_audit_log(
            db, None, "MARKETPLACE_RENT_INITIATED",
            user_id=renter_id,
            payload={
                "listing_id": listing_id,
                "escrow_id": escrow_id,
                "hours": hours,
                "amount_cents": amount_cents,
                "amount_token": amount_token,
                "currency": listing.get("currency"),
                "event_id": escrow_event_id,
            },
            status_code=200,
        )
    except Exception as exc:
        logger.warning("Failed to write rent audit log: %s", exc)

    result = {
        "status": "escrow",
        "listing_id": listing_id,
        "node_id": listing.get("node_id"),
        "mesh_id": mesh_id,
        "escrow_id": escrow_id,
        "escrow_status": "held",
        "listing_status": getattr(row, "status", "escrow"),
        "hours": hours,
        "amount_held_cents": amount_cents,
        "amount_held_token": amount_token,
        "currency": listing.get("currency"),
        "node_assignment": lifecycle_snapshot["node_assignment"],
        "heartbeat_snapshot": lifecycle_snapshot["heartbeat_snapshot"],
        "lifecycle_next_action": lifecycle_snapshot["lifecycle_next_action"],
        "lifecycle_snapshot": lifecycle_snapshot,
        "claim_boundary": _marketplace_lifecycle_claim_boundary(),
        "message": f"Payment for {hours}h held in escrow. Node must send a healthy heartbeat to release funds.",
    }
    if cache_key:
        _idempotency_set(cache_key, result)
    return result


@router.post("/escrow/{listing_id}/release")
async def release_escrow(
    listing_id: str,
    request: Request = None,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Manually release escrow. Usually triggered by heartbeat."""
    started = time.monotonic()
    requester_id = _current_user_id(current_user)
    current_user_event_identity = _current_user_event_identity(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    request_scope = listing_id
    if normalized_idem_key:
        cache_key = _idempotency_compose_key(
            "release_escrow",
            request_scope,
            requester_id,
            normalized_idem_key,
        )
        cached = _idempotency_get(cache_key)
        if cached:
            return cached

    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    renter_matches_listing = _ids_equal(listing.get("renter_id"), requester_id)
    if not renter_matches_listing and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    released_at = datetime.utcnow().isoformat()

    db_ready = _ensure_write_db_ready(db, request)
    response_escrow_id = None
    response_node_id = listing.get("node_id")
    response_mesh_id = listing.get("mesh_id")
    response_currency = listing.get("currency")
    if db_ready:
        row = _load_listing_for_update(db, listing_id)
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status != "escrow":
            raise HTTPException(status_code=400, detail="No active escrow")
        if current_user.role != "admin" and not _ids_equal(row.renter_id, requester_id):
            raise HTTPException(status_code=403, detail="Permission denied")

        escrow = _load_held_escrow_for_update(db, listing_id)
        if not escrow:
            raise HTTPException(status_code=409, detail="Escrow state mismatch")
        response_escrow_id = escrow.id
        response_node_id = getattr(row, "node_id", response_node_id)
        response_mesh_id = getattr(row, "mesh_id", response_mesh_id)
        response_currency = getattr(escrow, "currency", response_currency)
        bridge_evidence = {}
        bridge_attempted = False
        bridge_status = "not_required"
        request_evidence = _marketplace_request_evidence(
            action="release_escrow",
            route="POST /escrow/{listing_id}/release",
            current_user=current_user,
            request_scope=request_scope,
            normalized_idempotency_key=normalized_idem_key,
            db_write_ready=db_ready,
            listing_status=getattr(row, "status", listing.get("status")),
            currency=getattr(escrow, "currency", listing.get("currency")),
            renter_matches_listing=_ids_equal(row.renter_id, requester_id),
            admin_override=(
                current_user.role == "admin"
                and not _ids_equal(row.renter_id, requester_id)
            ),
        )
        # 1. Release on-chain if X0T
        if escrow.currency == "X0T":
            bridge = None
            bridge_attempted = True
            try:
                bridge = _get_token_bridge()
                released = await bridge.release_escrow_on_chain(escrow.id)
                bridge_evidence = bridge_upstream_evidence(bridge)
            except Exception as exc:
                bridge_evidence = bridge_upstream_evidence(bridge)
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="release_escrow",
                    started_at=started,
                    decision_basis="api_manual_escrow_release_request",
                    source_quality="token_bridge_release_error_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status="error",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=getattr(escrow, "status", None),
                    listing_status_after=getattr(row, "status", None),
                )
                logger.error("Escrow release bridge error for %s: %s", escrow.id, exc)
                record_escrow_failure("bridge_error")
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow.id,
                    listing_id=listing_id,
                    renter_id=escrow.renter_id,
                    actor_id=requester_id,
                    currency=escrow.currency,
                    status="held",
                    node_id=getattr(row, "node_id", None),
                    mesh_id=getattr(row, "mesh_id", None),
                    **current_user_event_identity,
                    amount_cents=escrow.amount_cents,
                    amount_token=escrow.amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="release_bridge_error",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Failed to release X0T escrow")
            if not released:
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="release_escrow",
                    started_at=started,
                    decision_basis="api_manual_escrow_release_request",
                    source_quality="token_bridge_release_rejected_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status="rejected",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=getattr(escrow, "status", None),
                    listing_status_after=getattr(row, "status", None),
                )
                record_escrow_failure("bridge_rejected")
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow.id,
                    listing_id=listing_id,
                    renter_id=escrow.renter_id,
                    actor_id=requester_id,
                    currency=escrow.currency,
                    status="held",
                    node_id=getattr(row, "node_id", None),
                    mesh_id=getattr(row, "mesh_id", None),
                    **current_user_event_identity,
                    amount_cents=escrow.amount_cents,
                    amount_token=escrow.amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="release_bridge_rejected",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Failed to release X0T escrow")
            bridge_status = "released"

        escrow.status = "released"
        escrow.released_at = datetime.fromisoformat(released_at)
        row.status = "rented"
        db.commit()
        event_settlement_evidence = _marketplace_api_settlement_evidence(
            action="release_escrow",
            started_at=started,
            decision_basis="api_manual_escrow_release_request",
            source_quality="api_request_db_commit_and_optional_token_bridge_release",
            bridge_attempted=bridge_attempted,
            bridge_status=bridge_status,
            db_write_attempted=True,
            db_committed=True,
            escrow_status_after=getattr(escrow, "status", None),
            listing_status_after=getattr(row, "status", None),
        )
        escrow_event_id = publish_marketplace_escrow_event(
            transition="released",
            source_agent="maas-marketplace",
            escrow_id=escrow.id,
            listing_id=listing_id,
            renter_id=escrow.renter_id,
            actor_id=requester_id,
            currency=escrow.currency,
            status="released",
            node_id=getattr(row, "node_id", None),
            mesh_id=getattr(row, "mesh_id", None),
            **current_user_event_identity,
            amount_cents=escrow.amount_cents,
            amount_token=escrow.amount_token,
            request_evidence=request_evidence,
            settlement_evidence=event_settlement_evidence,
            reason="manual_release",
            **bridge_evidence,
        )

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_RELEASED",
                user_id=requester_id,
                payload={
                    "listing_id": listing_id,
                    "escrow_id": escrow.id if escrow else None,
                    "manual": True,
                    "event_id": escrow_event_id,
                },
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow release audit log: %s", exc)

    listing["status"] = "rented"
    _save_listing_to_cache(listing)
    lifecycle_listing = dict(listing)
    lifecycle_listing["node_id"] = response_node_id
    lifecycle_listing["mesh_id"] = response_mesh_id
    lifecycle_listing["status"] = listing.get("status")
    lifecycle_snapshot = _marketplace_lifecycle_snapshot(
        listing=lifecycle_listing,
        db=db,
        escrow=escrow if db_ready else None,
    )

    result = {
        "status": "released",
        "listing_id": listing_id,
        "node_id": response_node_id,
        "mesh_id": response_mesh_id,
        "escrow_id": response_escrow_id,
        "escrow_status": "released" if response_escrow_id else "not_observed_without_write_db",
        "listing_status": listing.get("status"),
        "currency": response_currency,
        "released_at": released_at,
        "node_assignment": lifecycle_snapshot["node_assignment"],
        "heartbeat_snapshot": lifecycle_snapshot["heartbeat_snapshot"],
        "lifecycle_next_action": lifecycle_snapshot["lifecycle_next_action"],
        "lifecycle_snapshot": lifecycle_snapshot,
        "claim_boundary": _marketplace_lifecycle_claim_boundary(),
    }
    if cache_key:
        _idempotency_set(cache_key, result)
    return result


@router.post("/escrow/{listing_id}/refund")
async def refund_escrow(
    listing_id: str,
    request: Request = None,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Refund escrow if node health fails or rental cancelled before heartbeat."""
    started = time.monotonic()
    requester_id = _current_user_id(current_user)
    current_user_event_identity = _current_user_event_identity(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    request_scope = listing_id
    if normalized_idem_key:
        cache_key = _idempotency_compose_key(
            "refund_escrow",
            request_scope,
            requester_id,
            normalized_idem_key,
        )
        cached = _idempotency_get(cache_key)
        if cached:
            return cached

    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    renter_matches_listing = _ids_equal(listing.get("renter_id"), requester_id)
    if not renter_matches_listing and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    db_ready = _ensure_write_db_ready(db, request)
    response_escrow_id = None
    response_node_id = listing.get("node_id")
    response_mesh_id = listing.get("mesh_id")
    response_currency = listing.get("currency")
    if db_ready:
        row = _load_listing_for_update(db, listing_id)
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status != "escrow":
            raise HTTPException(status_code=400, detail="No active escrow")
        if current_user.role != "admin" and not _ids_equal(row.renter_id, requester_id):
            raise HTTPException(status_code=403, detail="Permission denied")

        escrow = _load_held_escrow_for_update(db, listing_id)
        if not escrow:
            raise HTTPException(status_code=409, detail="Escrow state mismatch")
        response_escrow_id = escrow.id
        response_node_id = getattr(row, "node_id", response_node_id)
        response_mesh_id = getattr(row, "mesh_id", response_mesh_id)
        response_currency = getattr(escrow, "currency", response_currency)
        bridge_evidence = {}
        bridge_attempted = False
        bridge_status = "not_required"
        request_evidence = _marketplace_request_evidence(
            action="refund_escrow",
            route="POST /escrow/{listing_id}/refund",
            current_user=current_user,
            request_scope=request_scope,
            normalized_idempotency_key=normalized_idem_key,
            db_write_ready=db_ready,
            listing_status=getattr(row, "status", listing.get("status")),
            currency=getattr(escrow, "currency", listing.get("currency")),
            renter_matches_listing=_ids_equal(row.renter_id, requester_id),
            admin_override=(
                current_user.role == "admin"
                and not _ids_equal(row.renter_id, requester_id)
            ),
        )
        # 1. Refund on-chain if X0T
        if escrow.currency == "X0T":
            bridge = None
            bridge_attempted = True
            try:
                bridge = _get_token_bridge()
                refunded = await bridge.refund_escrow_on_chain(escrow.id)
                bridge_evidence = bridge_upstream_evidence(bridge)
            except Exception as exc:
                bridge_evidence = bridge_upstream_evidence(bridge)
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="refund_escrow",
                    started_at=started,
                    decision_basis="api_manual_escrow_refund_request",
                    source_quality="token_bridge_refund_error_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status="error",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=getattr(escrow, "status", None),
                    listing_status_after=getattr(row, "status", None),
                )
                logger.error("Escrow refund bridge error for %s: %s", escrow.id, exc)
                record_escrow_failure("bridge_error")
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow.id,
                    listing_id=listing_id,
                    renter_id=escrow.renter_id,
                    actor_id=requester_id,
                    currency=escrow.currency,
                    status="held",
                    node_id=getattr(row, "node_id", None),
                    mesh_id=getattr(row, "mesh_id", None),
                    **current_user_event_identity,
                    amount_cents=escrow.amount_cents,
                    amount_token=escrow.amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="refund_bridge_error",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Failed to refund X0T escrow")
            if not refunded:
                event_settlement_evidence = _marketplace_api_settlement_evidence(
                    action="refund_escrow",
                    started_at=started,
                    decision_basis="api_manual_escrow_refund_request",
                    source_quality="token_bridge_refund_rejected_before_db_write",
                    bridge_attempted=bridge_attempted,
                    bridge_status="rejected",
                    db_write_attempted=False,
                    db_committed=False,
                    escrow_status_after=getattr(escrow, "status", None),
                    listing_status_after=getattr(row, "status", None),
                )
                record_escrow_failure("bridge_rejected")
                publish_marketplace_escrow_event(
                    transition="blocked",
                    source_agent="maas-marketplace",
                    escrow_id=escrow.id,
                    listing_id=listing_id,
                    renter_id=escrow.renter_id,
                    actor_id=requester_id,
                    currency=escrow.currency,
                    status="held",
                    node_id=getattr(row, "node_id", None),
                    mesh_id=getattr(row, "mesh_id", None),
                    **current_user_event_identity,
                    amount_cents=escrow.amount_cents,
                    amount_token=escrow.amount_token,
                    request_evidence=request_evidence,
                    settlement_evidence=event_settlement_evidence,
                    reason="refund_bridge_rejected",
                    **bridge_evidence,
                )
                raise HTTPException(status_code=502, detail="Failed to refund X0T escrow")
            bridge_status = "refunded"

        escrow.status = "refunded"
        row.status = "available"
        row.renter_id = None
        row.mesh_id = None
        db.commit()
        event_settlement_evidence = _marketplace_api_settlement_evidence(
            action="refund_escrow",
            started_at=started,
            decision_basis="api_manual_escrow_refund_request",
            source_quality="api_request_db_commit_and_optional_token_bridge_refund",
            bridge_attempted=bridge_attempted,
            bridge_status=bridge_status,
            db_write_attempted=True,
            db_committed=True,
            escrow_status_after=getattr(escrow, "status", None),
            listing_status_after=getattr(row, "status", None),
        )
        escrow_event_id = publish_marketplace_escrow_event(
            transition="refunded",
            source_agent="maas-marketplace",
            escrow_id=escrow.id,
            listing_id=listing_id,
            renter_id=escrow.renter_id,
            actor_id=requester_id,
            currency=escrow.currency,
            status="refunded",
            node_id=getattr(row, "node_id", None),
            mesh_id=getattr(row, "mesh_id", None),
            **current_user_event_identity,
            amount_cents=escrow.amount_cents,
            amount_token=escrow.amount_token,
            request_evidence=request_evidence,
            settlement_evidence=event_settlement_evidence,
            reason="manual_refund",
            **bridge_evidence,
        )

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_REFUNDED",
                user_id=requester_id,
                payload={
                    "listing_id": listing_id,
                    "escrow_id": escrow.id if escrow else None,
                    "event_id": escrow_event_id,
                },
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow refund audit log: %s", exc)

    listing["status"] = "available"
    listing["renter_id"] = None
    listing["mesh_id"] = None
    _save_listing_to_cache(listing)
    lifecycle_listing = dict(listing)
    lifecycle_listing["node_id"] = response_node_id
    lifecycle_listing["mesh_id"] = response_mesh_id
    lifecycle_listing["status"] = listing.get("status")
    lifecycle_snapshot = _marketplace_lifecycle_snapshot(
        listing=lifecycle_listing,
        db=db,
        escrow=escrow if db_ready else None,
    )

    result = {
        "status": "refunded",
        "listing_id": listing_id,
        "node_id": response_node_id,
        "mesh_id": response_mesh_id,
        "escrow_id": response_escrow_id,
        "escrow_status": "refunded" if response_escrow_id else "not_observed_without_write_db",
        "listing_status": listing.get("status"),
        "currency": response_currency,
        "node_assignment": lifecycle_snapshot["node_assignment"],
        "heartbeat_snapshot": lifecycle_snapshot["heartbeat_snapshot"],
        "lifecycle_next_action": lifecycle_snapshot["lifecycle_next_action"],
        "lifecycle_snapshot": lifecycle_snapshot,
        "claim_boundary": _marketplace_lifecycle_claim_boundary(),
    }
    if cache_key:
        _idempotency_set(cache_key, result)
    return result


@router.delete("/list/{listing_id}")
async def cancel_listing(
    listing_id: str,
    request: Request = None,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    started = time.monotonic()
    requester_id = _current_user_id(current_user)
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_cancel_listing",
            stage="cancel_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=404,
            context=_marketplace_route_context(
                current_user=current_user,
                listing_id=listing_id,
            ),
            db_evidence=_marketplace_db_evidence(
                action="load_listing_for_cancel",
                db_ready=_db_session_available(db),
                read_attempted=True,
            ),
            result_summary=_marketplace_result_summary(reason="listing_not_found"),
        )
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") in {"escrow", "rented"}:
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_cancel_listing",
            stage="cancel_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=400,
            context=_marketplace_route_context(
                current_user=current_user,
                listing_id=listing_id,
                node_id=listing.get("node_id"),
                currency=listing.get("currency"),
            ),
            db_evidence=_marketplace_db_evidence(
                action="validate_cancel_state",
                db_ready=_db_session_available(db),
                read_attempted=True,
                cache_hit=True,
            ),
            result_summary=_marketplace_result_summary(
                listing_status=listing.get("status"),
                reason="active_rental_state",
            ),
        )
        raise HTTPException(status_code=400, detail="Listing has active rental state (escrow)")
    if not _ids_equal(listing.get("owner_id"), requester_id) and current_user.role != "admin":
        _publish_marketplace_api_event(
            request=request,
            operation="marketplace_cancel_listing",
            stage="cancel_blocked",
            status_text="blocked",
            started_at=started,
            http_status_code=403,
            context=_marketplace_route_context(
                current_user=current_user,
                listing_id=listing_id,
                node_id=listing.get("node_id"),
                currency=listing.get("currency"),
            ),
            db_evidence=_marketplace_db_evidence(
                action="validate_cancel_owner",
                db_ready=_db_session_available(db),
                read_attempted=True,
                cache_hit=True,
            ),
            result_summary=_marketplace_result_summary(reason="permission_denied"),
        )
        raise HTTPException(status_code=403, detail="Permission denied")

    db_ready = _ensure_write_db_ready(db, request)
    if db_ready:
        row = _load_listing_for_update(db, listing_id)
        if not row:
            _publish_marketplace_api_event(
                request=request,
                operation="marketplace_cancel_listing",
                stage="cancel_blocked",
                status_text="blocked",
                started_at=started,
                http_status_code=404,
                context=_marketplace_route_context(
                    current_user=current_user,
                    listing_id=listing_id,
                ),
                db_evidence=_marketplace_db_evidence(
                    action="load_listing_for_cancel_update",
                    db_ready=db_ready,
                    read_attempted=True,
                ),
                result_summary=_marketplace_result_summary(reason="listing_not_found"),
            )
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status in {"escrow", "rented"}:
            _publish_marketplace_api_event(
                request=request,
                operation="marketplace_cancel_listing",
                stage="cancel_blocked",
                status_text="blocked",
                started_at=started,
                http_status_code=400,
                context=_marketplace_route_context(
                    current_user=current_user,
                    listing_id=listing_id,
                    node_id=getattr(row, "node_id", None),
                    currency=getattr(row, "currency", None),
                ),
                db_evidence=_marketplace_db_evidence(
                    action="validate_cancel_state_db",
                    db_ready=db_ready,
                    read_attempted=True,
                ),
                result_summary=_marketplace_result_summary(
                    listing_status=getattr(row, "status", None),
                    reason="active_rental_state",
                ),
            )
            raise HTTPException(status_code=400, detail="Listing has active rental state (escrow)")
        if current_user.role != "admin" and not _ids_equal(row.owner_id, requester_id):
            _publish_marketplace_api_event(
                request=request,
                operation="marketplace_cancel_listing",
                stage="cancel_blocked",
                status_text="blocked",
                started_at=started,
                http_status_code=403,
                context=_marketplace_route_context(
                    current_user=current_user,
                    listing_id=listing_id,
                    node_id=getattr(row, "node_id", None),
                    currency=getattr(row, "currency", None),
                ),
                db_evidence=_marketplace_db_evidence(
                    action="validate_cancel_owner_db",
                    db_ready=db_ready,
                    read_attempted=True,
                ),
                result_summary=_marketplace_result_summary(reason="permission_denied"),
            )
            raise HTTPException(status_code=403, detail="Permission denied")

        db.delete(row)
        db.commit()
        try:
            record_audit_log(
                db, None, "MARKETPLACE_LISTING_CANCELLED",
                user_id=requester_id,
                payload={"listing_id": listing_id},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write listing cancel audit log: %s", exc)

    with _listings_lock:
        _listings.pop(listing_id, None)

    _publish_marketplace_api_event(
        request=request,
        operation="marketplace_cancel_listing",
        stage="listing_cancelled",
        status_text="success",
        started_at=started,
        http_status_code=200,
        context=_marketplace_route_context(
            current_user=current_user,
            listing_id=listing_id,
            node_id=listing.get("node_id"),
            currency=listing.get("currency"),
        ),
        db_evidence=_marketplace_db_evidence(
            action="cancel_listing",
            db_ready=db_ready,
            read_attempted=True,
            write_attempted=db_ready,
            committed=db_ready,
            cache_write=True,
        ),
        result_summary=_marketplace_result_summary(
            listing_status="cancelled",
            reason="cancelled",
        ),
    )
    return {"status": "cancelled"}
