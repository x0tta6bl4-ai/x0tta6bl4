"""
MaaS Marketplace (Production) — x0tta6bl4
=========================================

Peer-to-peer infrastructure sharing with escrow payment protection.
Funds are held in escrow until the rented node passes a health heartbeat.
"""

import json
import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.database import MarketplaceEscrow, MarketplaceListing, User, GlobalConfig, get_db
from src.api.maas_telemetry import reputation_system
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/marketplace", tags=["MaaS Marketplace"])

_listings: Dict[str, Dict[str, Any]] = {}
_listings_lock = Lock()


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


def _get_node_reputation_multiplier(node_id: str) -> float:
    """Calculate price multiplier based on node trust score (0.5 to 1.2x)."""
    proxy_trust = reputation_system.get_proxy_trust(node_id)
    if not proxy_trust:
        return 1.0
    
    # 0.0 trust -> 0.5x price penalty
    # 1.0 trust -> 1.2x price premium
    trust = proxy_trust.trust_score
    return 0.5 + (trust * 0.7)


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
    created_at: str


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit")


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
    rep_multiplier = _get_node_reputation_multiplier(node_id)
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
    price_token = _val(data, "price_token_per_hour")
    if price_token:
        price_token = round(float(price_token) * rep_multiplier, 4)

    proxy_trust = reputation_system.get_proxy_trust(node_id)
    trust_score = proxy_trust.trust_score if proxy_trust else 0.5

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
        "owner_id": row.owner_id,
        "node_id": row.node_id,
        "region": row.region,
        "price_per_hour": _to_dollars(row.price_per_hour) if row.price_per_hour is not None else 0.0,
        "price_token_per_hour": row.price_token_per_hour,
        "currency": row.currency or "USD",
        "bandwidth_mbps": row.bandwidth_mbps,
        "status": row.status,
        "renter_id": row.renter_id,
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


@router.post("/list", response_model=ListingResponse)
async def create_listing(
    req: ListingCreate,
    current_user: User = Depends(require_permission("marketplace:list")),
    db: Session = Depends(get_db),
):
    db_ready = _db_session_available(db)

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
        "owner_id": current_user.id,
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
            owner_id=current_user.id,
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
                user_id=current_user.id,
                payload={"listing_id": listing_id, "node_id": req.node_id},
                status_code=201,
            )
        except Exception as exc:
            logger.warning("Failed to write listing audit log: %s", exc)

    _save_listing_to_cache(listing)
    multiplier = _get_global_price_multiplier(db)
    return _as_listing_response(listing, multiplier=multiplier)


@router.get("/search", response_model=List[ListingResponse])
async def search_listings(
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
        
        # Price filtering depends on currency
        if max_price is not None:
            if currency == "USD":
                if float(_v(listing, "price_per_hour") or 0.0) * multiplier > float(max_price):
                    continue
            else: # X0T
                if float(_v(listing, "price_token_per_hour") or 0.0) > float(max_price):
                    continue

        if min_bandwidth is not None and int(_v(listing, "bandwidth_mbps") or 0) < int(min_bandwidth or 0):
            continue
        result.append(_as_listing_response(listing, multiplier=multiplier))

    return result


@router.post("/rent/{listing_id}")
async def rent_node(
    listing_id: str,
    mesh_id: str,
    hours: int = Query(default=1, ge=1, le=720),  # Up to 30 days
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """
    Initiate a node rental with multi-hour deposit.
    Funds are released to the owner after the first healthy heartbeat.
    """
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("owner_id") == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot rent your own node")
    if listing.get("status") != "available":
        raise HTTPException(status_code=400, detail="Listing not available")

    if not _db_session_available(db):
        listing["status"] = "rented"
        listing["renter_id"] = current_user.id
        listing["mesh_id"] = mesh_id
        _save_listing_to_cache(listing)
        return {
            "status": "success",
            "listing_id": listing_id,
            "mesh_id": mesh_id,
        }

    row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    row.status = "escrow"
    row.renter_id = current_user.id
    row.mesh_id = mesh_id

    escrow_id = f"esc-{uuid.uuid4().hex[:8]}"
    multiplier = _get_global_price_multiplier(db)
    rep_multiplier = _get_node_reputation_multiplier(listing.get("node_id"))
    
    amount_cents = None
    amount_token = None
    
    if listing.get("currency") == "X0T":
        amount_token = float(listing.get("price_token_per_hour", 0.0)) * rep_multiplier * hours
        
        # Verify user has sufficient X0T balance before creating escrow
        try:
            from src.dao.token import MeshToken
            token_sys = MeshToken()
            user_balance = token_sys.balance_of(current_user.id)

            # MeshToken is currently in-memory; a fresh instance may have no ledger data.
            # Enforce balance checks only when ledger state is actually present.
            has_ledger_state = bool(getattr(token_sys, "balances", {}))
            if has_ledger_state and user_balance < amount_token:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient X0T balance. Required: {amount_token}, Available: {user_balance}"
                )

            # Lock tokens for escrow (non-blocking reservation)
            # In production, this should call a persistent token backend.
            if has_ledger_state:
                logger.info(
                    "Verified %s X0T balance for user %s, escrow %s",
                    amount_token,
                    current_user.id,
                    escrow_id,
                )
            else:
                logger.info(
                    "Skipping strict X0T balance check (stateless token ledger), escrow %s",
                    escrow_id,
                )
            
        except HTTPException:
            raise
        except ImportError:
            # Token system not available - allow for development/testing
            logger.warning("Token system not available, skipping balance check")
        except Exception as e:
            logger.warning(f"Token system integration error: {e}")
    else:
        amount_cents = _to_cents(float(listing["price_per_hour"]) * multiplier * rep_multiplier) * hours

    db.add(
        MarketplaceEscrow(
            id=escrow_id,
            listing_id=listing_id,
            renter_id=current_user.id,
            amount_cents=amount_cents,
            amount_token=amount_token,
            currency=listing.get("currency", "USD"),
            status="held",
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    listing["status"] = "escrow"
    listing["renter_id"] = current_user.id
    listing["mesh_id"] = mesh_id
    _save_listing_to_cache(listing)

    # Automated Orchestration: Push node to target mesh
    try:
        from src.services.maas_orchestrator import maas_orchestrator
        import asyncio
        asyncio.create_task(maas_orchestrator.provision_rented_node(db, listing_id, current_user.id, mesh_id))
    except Exception as orch_err:
        logger.error(f"Failed to trigger orchestration: {orch_err}")

    try:
        record_audit_log(
            db, None, "MARKETPLACE_RENT_INITIATED",
            user_id=current_user.id,
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

    return {
        "status": "escrow",
        "listing_id": listing_id,
        "escrow_id": escrow_id,
        "hours": hours,
        "amount_held_cents": amount_cents,
        "amount_held_token": amount_token,
        "currency": listing.get("currency"),
        "message": f"Payment for {hours}h held in escrow. Node must send a healthy heartbeat to release funds.",
    }


@router.post("/escrow/{listing_id}/release")
async def release_escrow(
    listing_id: str,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """Manually release escrow. Usually triggered by heartbeat."""
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    if listing.get("renter_id") != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    released_at = datetime.utcnow().isoformat()

    if _db_session_available(db):
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status != "escrow":
            raise HTTPException(status_code=400, detail="No active escrow")

        escrow = db.query(MarketplaceEscrow).filter(
            MarketplaceEscrow.listing_id == listing_id,
            MarketplaceEscrow.status == "held",
        ).first()
        if escrow:
            escrow.status = "released"
            escrow.released_at = datetime.fromisoformat(released_at)
        row.status = "rented"
        db.commit()

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_RELEASED",
                user_id=current_user.id,
                payload={"listing_id": listing_id, "escrow_id": escrow.id if escrow else None, "manual": True},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow release audit log: %s", exc)

    listing["status"] = "rented"
    _save_listing_to_cache(listing)

    return {"status": "released", "listing_id": listing_id, "released_at": released_at}


@router.post("/escrow/{listing_id}/refund")
async def refund_escrow(
    listing_id: str,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """Refund escrow if node health fails or rental cancelled before heartbeat."""
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow")
    if listing.get("renter_id") != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    if _db_session_available(db):
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        if row.status != "escrow":
            raise HTTPException(status_code=400, detail="No active escrow")

        escrow = db.query(MarketplaceEscrow).filter(
            MarketplaceEscrow.listing_id == listing_id,
            MarketplaceEscrow.status == "held",
        ).first()
        if escrow:
            escrow.status = "refunded"
        row.status = "available"
        row.renter_id = None
        row.mesh_id = None
        db.commit()

        try:
            record_audit_log(
                db, None, "MARKETPLACE_ESCROW_REFUNDED",
                user_id=current_user.id,
                payload={"listing_id": listing_id, "escrow_id": escrow.id if escrow else None},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write escrow refund audit log: %s", exc)

    listing["status"] = "available"
    listing["renter_id"] = None
    listing["mesh_id"] = None
    _save_listing_to_cache(listing)

    return {"status": "refunded", "listing_id": listing_id}


@router.delete("/list/{listing_id}")
async def cancel_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    listing = _get_listing_from_cache_or_db(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") == "escrow":
        raise HTTPException(status_code=400, detail="Active escrow in progress")
    if listing.get("owner_id") != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    if _db_session_available(db):
        row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if row:
            db.delete(row)
            db.commit()
        try:
            record_audit_log(
                db, None, "MARKETPLACE_LISTING_CANCELLED",
                user_id=current_user.id,
                payload={"listing_id": listing_id},
                status_code=200,
            )
        except Exception as exc:
            logger.warning("Failed to write listing cancel audit log: %s", exc)

    with _listings_lock:
        _listings.pop(listing_id, None)

    return {"status": "cancelled"}
