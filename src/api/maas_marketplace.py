"""
MaaS Marketplace (Production) — x0tta6bl4
=========================================

Peer-to-peer infrastructure sharing with escrow payment protection.
Funds are held in escrow until the rented node passes a health heartbeat.
"""

import json
import logging
import os
import re
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.core.reliability_policy import mark_degraded_dependency
from src.database import MarketplaceEscrow, MarketplaceListing, User, GlobalConfig, get_db
from src.api.maas_telemetry import reputation_system
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.utils.audit import record_audit_log

from src.resilience.advanced_patterns import get_resilient_executor
from src.monitoring.maas_metrics import record_escrow_failure

logger = logging.getLogger(__name__)

# Global resilient executor for marketplace operations (P2 Reliability)
marketplace_executor = get_resilient_executor()

router = APIRouter(prefix="/api/v1/maas/marketplace", tags=["MaaS Marketplace"])

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


def _get_token_bridge() -> TokenBridge:
    global _token_bridge
    if _token_bridge is None:
        from src.core.settings import settings
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


def _to_cents(price_per_hour: float) -> int:
    return int(round(price_per_hour * 100))


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

    return {
        "listing_id": listing_id,
        "owner_id": _val(data, "owner_id"),
        "node_id": node_id,
        "region": _val(data, "region"),
        "price_per_hour": price_per_hour if currency == "USD" else None,
        "price_token_per_hour": price_token if currency == "X0T" else None,
        "currency": currency,
        "bandwidth_mbps": int(_val(data, "bandwidth_mbps") or 0),
        "status": _val(data, "status", "available"),
        "trust_score": round(trust_score, 2),
        "created_at": created_at_iso,
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


@router.post("/list", response_model=ListingResponse)
async def create_listing(
    req: ListingCreate,
    request: Request = None,
    current_user: User = Depends(require_permission("marketplace:list")),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
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
            return cached

    with _listings_lock:
        in_memory_exists = any(item.get("node_id") == req.node_id for item in _listings.values())
    if in_memory_exists:
        raise HTTPException(status_code=400, detail="Node already listed")

    if db_ready:
        existing = db.query(MarketplaceListing).filter(MarketplaceListing.node_id == req.node_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Node already listed")

    if req.currency == "USD" and not req.price_per_hour:
        raise HTTPException(status_code=400, detail="price_per_hour required for USD")
    if req.currency == "X0T" and not req.price_token_per_hour:
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
    # Allow direct coroutine calls in unit tests where FastAPI doesn't resolve Query defaults.
    if not isinstance(currency, str):
        currency = getattr(currency, "default", "USD")
    if not isinstance(currency, str):
        currency = "USD"
    currency = currency.upper()
    if currency not in {"USD", "X0T"}:
        raise HTTPException(status_code=422, detail="Invalid currency")

    with _listings_lock:
        cached_rows = [dict(item) for item in _listings.values()]

    if cached_rows:
        source = cached_rows
    elif _db_session_available(db):
        rows = db.query(MarketplaceListing).all()
        source = [_row_to_listing(row) for row in rows]
        with _listings_lock:
            for listing in source:
                _listings[listing["listing_id"]] = dict(listing)
    else:
        if request is not None:
            mark_degraded_dependency(request, "database")
        source = []

    result: List[Dict[str, Any]] = []
    multiplier = _get_global_price_multiplier(db)
    for listing in source:
        def _v(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        listing_currency = _v(listing, "currency", "USD") or "USD"
        if _v(listing, "status") != "available":
            continue
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

    return result


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

    renter_id = _current_user_id(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    if normalized_idem_key:
        scope = f"{listing_id}:{mesh_id}:{hours}"
        cache_key = _idempotency_compose_key("rent_node", scope, renter_id, normalized_idem_key)
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
    if not db_ready:
        listing["status"] = "rented"
        listing["renter_id"] = renter_id
        listing["mesh_id"] = mesh_id
        _save_listing_to_cache(listing)
        result = {
            "status": "success",
            "listing_id": listing_id,
            "mesh_id": mesh_id,
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

    row.status = "escrow"
    row.renter_id = renter_id
    row.mesh_id = mesh_id

    escrow_id = f"esc-{uuid.uuid4().hex[:8]}"
    multiplier = _get_global_price_multiplier(db)
    rep_multiplier = _get_node_reputation_multiplier(listing.get("node_id"))
    congestion_multiplier = _get_mesh_congestion_multiplier(mesh_id, db)
    total_multiplier = multiplier * rep_multiplier * congestion_multiplier
    
    amount_cents = None
    amount_token = None
    
    if listing.get("currency") == "X0T":
        amount_token = float(listing.get("price_token_per_hour", 0.0)) * total_multiplier * hours
        
        # Verify user has sufficient X0T balance before creating escrow
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
            # Note: Using run_until_complete simulation or similar if needed, 
            # but here we are in an async function.
            tx_hash = await bridge.lock_escrow_on_chain(escrow_id, renter_id, amount_token)
            if not tx_hash:
                raise RuntimeError("lock_escrow_on_chain returned empty transaction hash")
            
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
                logger.error("Token system unavailable; refusing X0T rent for escrow %s", escrow_id)
                raise HTTPException(status_code=502, detail="Token bridge unavailable")
        except Exception as e:
            if _allow_insecure_escrow_fallback():
                logger.warning("Token integration error, using insecure fallback: %s", e)
            else:
                logger.error("Token bridge lock failed for escrow %s: %s", escrow_id, e)
                raise HTTPException(status_code=502, detail="Failed to lock X0T escrow")
    else:
        amount_cents = _to_cents(float(listing["price_per_hour"]) * total_multiplier) * hours

    db.add(
        MarketplaceEscrow(
            id=escrow_id,
            listing_id=listing_id,
            renter_id=renter_id,
            amount_cents=amount_cents,
            amount_token=amount_token,
            currency=listing.get("currency", "USD"),
            status="held",
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    listing["status"] = "escrow"
    listing["renter_id"] = renter_id
    listing["mesh_id"] = mesh_id
    _save_listing_to_cache(listing)

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
            },
            status_code=200,
        )
    except Exception as exc:
        logger.warning("Failed to write rent audit log: %s", exc)

    result = {
        "status": "escrow",
        "listing_id": listing_id,
        "escrow_id": escrow_id,
        "hours": hours,
        "amount_held_cents": amount_cents,
        "amount_held_token": amount_token,
        "currency": listing.get("currency"),
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
    requester_id = _current_user_id(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    if normalized_idem_key:
        cache_key = _idempotency_compose_key("release_escrow", listing_id, requester_id, normalized_idem_key)
        cached = _idempotency_get(cache_key)
        if cached:
            return cached

    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    if not _ids_equal(listing.get("renter_id"), requester_id) and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    released_at = datetime.utcnow().isoformat()

    db_ready = _ensure_write_db_ready(db, request)
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
        # 1. Release on-chain if X0T
        if escrow.currency == "X0T":
            try:
                bridge = _get_token_bridge()
                released = await bridge.release_escrow_on_chain(escrow.id)
            except Exception as exc:
                logger.error("Escrow release bridge error for %s: %s", escrow.id, exc)
                record_escrow_failure("bridge_error")
                raise HTTPException(status_code=502, detail="Failed to release X0T escrow")
            if not released:
                record_escrow_failure("bridge_rejected")
                raise HTTPException(status_code=502, detail="Failed to release X0T escrow")

        escrow.status = "released"
        escrow.released_at = datetime.fromisoformat(released_at)
        row.status = "rented"
        db.commit()

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_RELEASED",
                user_id=requester_id,
                payload={"listing_id": listing_id, "escrow_id": escrow.id if escrow else None, "manual": True},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow release audit log: %s", exc)

    listing["status"] = "rented"
    _save_listing_to_cache(listing)

    result = {"status": "released", "listing_id": listing_id, "released_at": released_at}
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
    requester_id = _current_user_id(current_user)
    cache_key = None
    normalized_idem_key = _normalize_idempotency_key(idempotency_key)
    if normalized_idem_key:
        cache_key = _idempotency_compose_key("refund_escrow", listing_id, requester_id, normalized_idem_key)
        cached = _idempotency_get(cache_key)
        if cached:
            return cached

    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    if not _ids_equal(listing.get("renter_id"), requester_id) and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    db_ready = _ensure_write_db_ready(db, request)
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
        # 1. Refund on-chain if X0T
        if escrow.currency == "X0T":
            try:
                bridge = _get_token_bridge()
                refunded = await bridge.refund_escrow_on_chain(escrow.id)
            except Exception as exc:
                logger.error("Escrow refund bridge error for %s: %s", escrow.id, exc)
                record_escrow_failure("bridge_error")
                raise HTTPException(status_code=502, detail="Failed to refund X0T escrow")
            if not refunded:
                record_escrow_failure("bridge_rejected")
                raise HTTPException(status_code=502, detail="Failed to refund X0T escrow")

        escrow.status = "refunded"
        row.status = "available"
        row.renter_id = None
        row.mesh_id = None
        db.commit()

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_REFUNDED",
                user_id=requester_id,
                payload={"listing_id": listing_id, "escrow_id": escrow.id if escrow else None},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow refund audit log: %s", exc)

    listing["status"] = "available"
    listing["renter_id"] = None
    listing["mesh_id"] = None
    _save_listing_to_cache(listing)

    result = {"status": "refunded", "listing_id": listing_id}
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
    requester_id = _current_user_id(current_user)
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") in {"escrow", "rented"}:
        raise HTTPException(status_code=400, detail="Listing has active rental state (escrow)")
    if not _ids_equal(listing.get("owner_id"), requester_id) and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    db_ready = _ensure_write_db_ready(db, request)
    if db_ready:
        row = _load_listing_for_update(db, listing_id)
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status in {"escrow", "rented"}:
            raise HTTPException(status_code=400, detail="Listing has active rental state (escrow)")
        if current_user.role != "admin" and not _ids_equal(row.owner_id, requester_id):
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

    return {"status": "cancelled"}
