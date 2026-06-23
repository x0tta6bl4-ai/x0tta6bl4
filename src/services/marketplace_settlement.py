import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import MarketplaceEscrow, MarketplaceListing, SessionLocal
from src.api.maas_telemetry import uptime_tracker
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.service_event_identity import service_event_identity
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

# Settlement Threshold (99.9% uptime required)
SETTLEMENT_UPTIME_THRESHOLD = 0.999

_token_bridge = None
_SERVICE_AGENT = "maas-settlement"


def _get_token_bridge():
    global _token_bridge
    if _token_bridge is None:
        from src.core.settings import settings

        bridge_config = BridgeConfig(
            rpc_url=settings.rpc_url or "",
            contract_address=settings.contract_address or "",
            private_key=settings.operator_private_key or "",
        )
        _token_bridge = TokenBridge(MeshToken(), bridge_config)
    return _token_bridge


async def marketplace_settlement_loop():
    """
    Daily background worker to release escrows to node owners 
    if the node maintained 99.9% uptime over the last 24h.
    """
    logger.info("💸 Marketplace Settlement service started")
    event_identity = service_event_identity(service_name=_SERVICE_AGENT)

    while True:
        try:
            db = SessionLocal()
            try:
                # 1. Find held escrows older than 24 hours
                settlement_limit = datetime.utcnow() - timedelta(hours=24)
                pending_escrows = db.query(MarketplaceEscrow).filter(
                    MarketplaceEscrow.status == "held",
                    MarketplaceEscrow.created_at < settlement_limit
                ).all()

                for escrow in pending_escrows:
                    attempt_started = time.monotonic()
                    listing = db.query(MarketplaceListing).filter(
                        MarketplaceListing.id == escrow.listing_id
                    ).first()
                    
                    if not listing:
                        continue
                        
                    # 2. Check uptime
                    uptime = uptime_tracker.get_uptime_percent(listing.node_id)
                    settlement_evidence = _settlement_uptime_evidence(
                        node_id=listing.node_id,
                        uptime=uptime,
                    )
                    
                    if uptime >= SETTLEMENT_UPTIME_THRESHOLD:
                        logger.info(f"✅ Node {listing.node_id} passed 99.9% uptime ({uptime:.2%}). Releasing escrow {escrow.id}")
                        
                        bridge_evidence = {}
                        bridge_attempted = False
                        bridge_status = "not_required"
                        # Trigger on-chain release if X0T
                        if escrow.currency == "X0T":
                            try:
                                released = await _get_token_bridge().release_escrow_on_chain(escrow.id)
                            except Exception as exc:
                                logger.error("X0T settlement release bridge error for escrow %s: %s", escrow.id, exc)
                                publish_marketplace_escrow_event(
                                    transition="blocked",
                                    source_agent=_SERVICE_AGENT,
                                    escrow_id=escrow.id,
                                    listing_id=escrow.listing_id,
                                    renter_id=escrow.renter_id,
                                    actor_id="settlement-loop",
                                    currency=escrow.currency,
                                    status="held",
                                    node_id=listing.node_id,
                                    mesh_id=getattr(listing, "mesh_id", None),
                                    amount_cents=getattr(escrow, "amount_cents", None),
                                    amount_token=getattr(escrow, "amount_token", None),
                                    reason="release_bridge_error",
                                    **event_identity,
                                )
                                continue
                            if not released:
                                logger.error(
                                    "X0T settlement release refused for escrow %s; "
                                    "leaving escrow held",
                                    escrow.id,
                                )
                                publish_marketplace_escrow_event(
                                    transition="blocked",
                                    source_agent=_SERVICE_AGENT,
                                    escrow_id=escrow.id,
                                    listing_id=escrow.listing_id,
                                    renter_id=escrow.renter_id,
                                    actor_id="settlement-loop",
                                    currency=escrow.currency,
                                    status="held",
                                    node_id=listing.node_id,
                                    mesh_id=getattr(listing, "mesh_id", None),
                                    amount_cents=getattr(escrow, "amount_cents", None),
                                    amount_token=getattr(escrow, "amount_token", None),
                                    reason="release_bridge_rejected",
                                    **event_identity,
                                )
                                continue
                        
                        escrow.status = "released"
                        escrow.released_at = datetime.utcnow()
                        # Finalize listing status if rental period ended
                        # (Assume simple hourly/daily model for now)
                        listing.status = "rented" # Still rented, just settled for last 24h
                        db.commit()
                        escrow_event_id = publish_marketplace_escrow_event(
                            transition="released",
                            source_agent=_SERVICE_AGENT,
                            escrow_id=escrow.id,
                            listing_id=escrow.listing_id,
                            renter_id=escrow.renter_id,
                            actor_id="settlement-loop",
                            currency=escrow.currency,
                            status="released",
                            node_id=listing.node_id,
                            mesh_id=getattr(listing, "mesh_id", None),
                            amount_cents=getattr(escrow, "amount_cents", None),
                            amount_token=getattr(escrow, "amount_token", None),
                            reason="uptime_threshold_met",
                            **event_identity,
                        )
                        
                        record_audit_log(
                            db, None, "MARKETPLACE_SETTLEMENT_RELEASED",
                            user_id=escrow.renter_id,
                            payload={"escrow_id": escrow.id, "uptime": uptime, "event_id": escrow_event_id},
                            status_code=200
                        )
                    else:
                        logger.warning(f"⚠️ Node {listing.node_id} FAILED 99.9% uptime ({uptime:.2%}). Refunding escrow {escrow.id}")
                        
                        bridge_evidence = {}
                        bridge_attempted = False
                        bridge_status = "not_required"
                        # Trigger on-chain refund if X0T
                        if escrow.currency == "X0T":
                            try:
                                refunded = await _get_token_bridge().refund_escrow_on_chain(escrow.id)
                            except Exception as exc:
                                logger.error("X0T settlement refund bridge error for escrow %s: %s", escrow.id, exc)
                                publish_marketplace_escrow_event(
                                    transition="blocked",
                                    source_agent=_SERVICE_AGENT,
                                    escrow_id=escrow.id,
                                    listing_id=escrow.listing_id,
                                    renter_id=escrow.renter_id,
                                    actor_id="settlement-loop",
                                    currency=escrow.currency,
                                    status="held",
                                    node_id=listing.node_id,
                                    mesh_id=getattr(listing, "mesh_id", None),
                                    amount_cents=getattr(escrow, "amount_cents", None),
                                    amount_token=getattr(escrow, "amount_token", None),
                                    reason="refund_bridge_error",
                                    **event_identity,
                                )
                                continue
                            if not refunded:
                                logger.error(
                                    "X0T settlement refund refused for escrow %s; "
                                    "leaving escrow held",
                                    escrow.id,
                                )
                                publish_marketplace_escrow_event(
                                    transition="blocked",
                                    source_agent=_SERVICE_AGENT,
                                    escrow_id=escrow.id,
                                    listing_id=escrow.listing_id,
                                    renter_id=escrow.renter_id,
                                    actor_id="settlement-loop",
                                    currency=escrow.currency,
                                    status="held",
                                    node_id=listing.node_id,
                                    mesh_id=getattr(listing, "mesh_id", None),
                                    amount_cents=getattr(escrow, "amount_cents", None),
                                    amount_token=getattr(escrow, "amount_token", None),
                                    reason="refund_bridge_rejected",
                                    **event_identity,
                                )
                                continue
                            
                        escrow.status = "refunded"
                        listing.status = "available"
                        listing.renter_id = None
                        db.commit()
                        escrow_event_id = publish_marketplace_escrow_event(
                            transition="refunded",
                            source_agent=_SERVICE_AGENT,
                            escrow_id=escrow.id,
                            listing_id=escrow.listing_id,
                            renter_id=escrow.renter_id,
                            actor_id="settlement-loop",
                            currency=escrow.currency,
                            status="refunded",
                            node_id=listing.node_id,
                            mesh_id=getattr(listing, "mesh_id", None),
                            amount_cents=getattr(escrow, "amount_cents", None),
                            amount_token=getattr(escrow, "amount_token", None),
                            reason="uptime_threshold_failed",
                            **event_identity,
                        )
                        
                        record_audit_log(
                            db, None, "MARKETPLACE_SETTLEMENT_REFUNDED",
                            user_id=escrow.renter_id,
                            payload={"escrow_id": escrow.id, "uptime": uptime, "event_id": escrow_event_id},
                            status_code=200
                        )
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ Marketplace Settlement error: {e}")
            
        await asyncio.sleep(3600) # Run every hour to check for new candidates

if __name__ == "__main__":
    asyncio.run(marketplace_settlement_loop())
