"""
MaaS Marketplace (Production) — x0tta6bl4
=========================================

Peer-to-peer infrastructure sharing with in-memory direct-call compatibility
and optional SQLAlchemy persistence.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.database import MarketplaceListing, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/marketplace", tags=["MaaS Marketplace"])


# Backward-compatible in-memory store used in unit tests.
_listings: Dict[str, Dict[str, Any]] = {}


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
                "renter_id": None,
                "mesh_id": None,
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
                "renter_id": None,
                "mesh_id": None,
            }
            _listings[listing_id] = listing

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["owner_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot rent your own node")
    if listing["status"] != "available":
        raise HTTPException(status_code=400, detail="Listing not available")

    listing["status"] = "rented"
    listing["renter_id"] = current_user.id
    listing["mesh_id"] = mesh_id

    if _db_session_available(db):
        if db_row is None:
            db_row = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        if db_row:
            db_row.status = "rented"
            db.commit()

    return {"status": "success", "listing_id": listing_id, "mesh_id": mesh_id}


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
                "renter_id": None,
                "mesh_id": None,
            }

    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
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
