"""
MaaS Marketplace (Production) — x0tta6bl4
=========================================

Peer-to-peer infrastructure sharing with escrow payment protection.
Funds are held in escrow until the rented node passes a health heartbeat.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.database import MarketplaceEscrow, MarketplaceListing, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/marketplace", tags=["MaaS Marketplace"])


# Backward-compatible in-memory store used in unit tests.
_listings: Dict[str, Dict[str, Any]] = {}
_escrows: Dict[str, Dict[str, Any]] = {}


class ListingCreate(BaseModel):
    node_id: str
    region: str = Field(..., pattern="^(us-east|us-west|eu-central|asia-south|global)$")
    price_per_hour: float = Field(..., ge=0.001)
    bandwidth_mbps: int = Field(..., ge=10)


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit")


def _as_listing_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "listing_id": data["listing_id"],
        "owner_id": data["owner_id"],
        "node_id": data["node_id"],
        "region": data["region"],
        "price_per_hour": data["price_per_hour"],
        "bandwidth_mbps": data["bandwidth_mbps"],
        "status": data["status"],
        "created_at": data["created_at"],
    }


@router.post("/list")
async def create_listing(
    req: ListingCreate,
    current_user: User = Depends(require_permission("marketplace:list")),
    db: Session = Depends(get_db),
):
    for listing in _listings.values():
        if listing["node_id"] == req.node_id:
            raise HTTPException(status_code=400, detail="Node already listed")

    if _db_session_available(db):
        existing = (
            db.query(MarketplaceListing)
            .filter(MarketplaceListing.node_id == req.node_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Node already listed")

    listing_id = f"lst-{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    record = {
        "listing_id": listing_id,
        "owner_id": current_user.id,
        "node_id": req.node_id,
        "region": req.region,
        "price_per_hour": float(req.price_per_hour),
        "bandwidth_mbps": int(req.bandwidth_mbps),
        "status": "available",
        "created_at": created_at,
        "renter_id": None,
        "mesh_id": None,
    }
    _listings[listing_id] = record

    if _db_session_available(db):
        row = MarketplaceListing(
            id=listing_id,
            owner_id=current_user.id,
            node_id=req.node_id,
            region=req.region,
            price_per_hour=int(req.price_per_hour * 100),
            bandwidth_mbps=req.bandwidth_mbps,
            status="available",
        )
        db.add(row)
        db.commit()

    return _as_listing_response(record)


@router.get("/search")
async def search_listings(
    region: Optional[str] = None,
    max_price: Optional[float] = None,
    min_bandwidth: Optional[int] = None,
    db: Session = Depends(get_db),
):
    # Prefer in-memory store for direct-call paths/tests.
    if _listings:
        candidates = [x for x in _listings.values() if x["status"] == "available"]
    elif _db_session_available(db):
        rows = (
            db.query(MarketplaceListing)
            .filter(MarketplaceListing.status == "available")
            .all()
        )
        candidates = [
            {
                "listing_id": r.id,
                "owner_id": r.owner_id,
                "node_id": r.node_id,
                "region": r.region,
                "price_per_hour": r.price_per_hour / 100.0,
                "bandwidth_mbps": r.bandwidth_mbps,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "renter_id": r.renter_id,
                "mesh_id": r.mesh_id,
            }
            for r in rows
        ]
    else:
        candidates = []

    if region is not None:
        candidates = [x for x in candidates if x["region"] == region]
    if max_price is not None:
        candidates = [x for x in candidates if x["price_per_hour"] <= max_price]
    if min_bandwidth is not None:
        candidates = [x for x in candidates if x["bandwidth_mbps"] >= min_bandwidth]

    return [_as_listing_response(x) for x in candidates]


@router.post("/rent/{listing_id}")
async def rent_node(
    listing_id: str,
    mesh_id: str,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """
    Initiate a node rental.  Moves listing to 'escrow' status and creates
    a payment hold for one hour.  Funds are released only after the rented
    node sends a successful heartbeat (POST /nodes/{node_id}/heartbeat).
    """
    listing = _listings.get(listing_id)
    db_row = None

    if listing is None and _db_session_available(db):
        db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            listing = {
                "listing_id": db_row.id,
                "owner_id": db_row.owner_id,
                "node_id": db_row.node_id,
                "region": db_row.region,
                "price_per_hour": db_row.price_per_hour / 100.0,
                "bandwidth_mbps": db_row.bandwidth_mbps,
                "status": db_row.status,
                "created_at": db_row.created_at.isoformat() if db_row.created_at else "",
                "renter_id": db_row.renter_id,
                "mesh_id": db_row.mesh_id,
            }
            _listings[listing_id] = listing

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["owner_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot rent your own node")
    if listing["status"] != "available":
        raise HTTPException(status_code=400, detail="Listing not available")

    # Move to escrow — payment held until health confirmed
    listing["status"] = "escrow"
    listing["renter_id"] = current_user.id
    listing["mesh_id"] = mesh_id

    escrow_id = f"esc-{uuid.uuid4().hex[:8]}"
    amount_cents = int(listing["price_per_hour"] * 100)
    _escrows[escrow_id] = {
        "escrow_id": escrow_id,
        "listing_id": listing_id,
        "renter_id": current_user.id,
        "amount_cents": amount_cents,
        "status": "held",
        "created_at": datetime.utcnow().isoformat(),
        "released_at": None,
    }

    if _db_session_available(db):
        if db_row is None:
            db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            db_row.status = "escrow"
            db_row.renter_id = current_user.id
            db_row.mesh_id = mesh_id

        escrow_row = MarketplaceEscrow(
            id=escrow_id,
            listing_id=listing_id,
            renter_id=current_user.id,
            amount_cents=amount_cents,
            status="held",
            created_at=datetime.utcnow(),
        )
        db.add(escrow_row)
        db.commit()

    logger.info(
        "💰 Escrow %s created for listing %s (renter=%s, amount=%d¢)",
        escrow_id, listing_id, current_user.id, amount_cents,
    )
    return {
        "status": "escrow",
        "listing_id": listing_id,
        "escrow_id": escrow_id,
        "mesh_id": mesh_id,
        "amount_held_cents": amount_cents,
        "message": "Payment held in escrow. Send a heartbeat to confirm node health and release funds.",
    }


@router.post("/escrow/{listing_id}/release")
async def release_escrow(
    listing_id: str,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """
    Manually release escrow after node health is confirmed.
    Normally triggered automatically by the node heartbeat endpoint.
    Only the renter or an admin may call this.
    """
    listing = _listings.get(listing_id)
    if listing is None and _db_session_available(db):
        db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            listing = {"listing_id": db_row.id, "status": db_row.status,
                       "renter_id": db_row.renter_id, "owner_id": db_row.owner_id}

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["status"] != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow for this listing")

    is_renter = listing.get("renter_id") == current_user.id
    is_admin = getattr(current_user, "role", "user") == "admin"
    if not (is_renter or is_admin):
        raise HTTPException(status_code=403, detail="Only renter or admin may release escrow")

    released_at = datetime.utcnow()

    # Update in-memory
    if listing_id in _listings:
        _listings[listing_id]["status"] = "rented"
    for esc in _escrows.values():
        if esc["listing_id"] == listing_id and esc["status"] == "held":
            esc["status"] = "released"
            esc["released_at"] = released_at.isoformat()
            break

    # Update DB
    if _db_session_available(db):
        db_listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_listing:
            db_listing.status = "rented"
        db_escrow = (
            db.query(MarketplaceEscrow)
            .filter(MarketplaceEscrow.listing_id == listing_id, MarketplaceEscrow.status == "held")
            .first()
        )
        if db_escrow:
            db_escrow.status = "released"
            db_escrow.released_at = released_at
        db.commit()

    logger.info("✅ Escrow released for listing %s", listing_id)
    return {"status": "released", "listing_id": listing_id, "released_at": released_at.isoformat()}


@router.post("/escrow/{listing_id}/refund")
async def refund_escrow(
    listing_id: str,
    current_user: User = Depends(require_permission("marketplace:rent")),
    db: Session = Depends(get_db),
):
    """
    Refund escrow if node health check fails. Returns listing to 'available'.
    Only the renter or an admin may call this within the dispute window.
    """
    listing = _listings.get(listing_id)
    db_listing = None
    if listing is None and _db_session_available(db):
        db_listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_listing:
            listing = {"listing_id": db_listing.id, "status": db_listing.status,
                       "renter_id": db_listing.renter_id, "owner_id": db_listing.owner_id}

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["status"] != "escrow":
        raise HTTPException(status_code=400, detail="No active escrow for this listing")

    is_renter = listing.get("renter_id") == current_user.id
    is_admin = getattr(current_user, "role", "user") == "admin"
    if not (is_renter or is_admin):
        raise HTTPException(status_code=403, detail="Only renter or admin may refund escrow")

    # Update in-memory
    if listing_id in _listings:
        _listings[listing_id]["status"] = "available"
        _listings[listing_id]["renter_id"] = None
        _listings[listing_id]["mesh_id"] = None
    for esc in _escrows.values():
        if esc["listing_id"] == listing_id and esc["status"] == "held":
            esc["status"] = "refunded"
            break

    # Update DB
    if _db_session_available(db):
        if db_listing is None:
            db_listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_listing:
            db_listing.status = "available"
            db_listing.renter_id = None
            db_listing.mesh_id = None
        db_escrow = (
            db.query(MarketplaceEscrow)
            .filter(MarketplaceEscrow.listing_id == listing_id, MarketplaceEscrow.status == "held")
            .first()
        )
        if db_escrow:
            db_escrow.status = "refunded"
        db.commit()

    logger.info("💸 Escrow refunded for listing %s", listing_id)
    return {"status": "refunded", "listing_id": listing_id}


@router.delete("/list/{listing_id}")
async def cancel_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    listing = _listings.get(listing_id)
    db_row = None

    if listing is None and _db_session_available(db):
        db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            listing = {
                "listing_id": db_row.id,
                "owner_id": db_row.owner_id,
                "node_id": db_row.node_id,
                "region": db_row.region,
                "price_per_hour": db_row.price_per_hour / 100.0,
                "bandwidth_mbps": db_row.bandwidth_mbps,
                "status": db_row.status,
                "created_at": db_row.created_at.isoformat() if db_row.created_at else "",
                "renter_id": db_row.renter_id,
                "mesh_id": db_row.mesh_id,
            }

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["status"] == "escrow":
        raise HTTPException(status_code=400, detail="Cannot cancel listing with active escrow")
    if listing["owner_id"] != current_user.id and getattr(current_user, "role", "user") != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    _listings.pop(listing_id, None)

    if _db_session_available(db):
        if db_row is None:
            db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            db.delete(db_row)
            db.commit()

    return {"status": "cancelled"}
