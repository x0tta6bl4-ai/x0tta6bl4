import asyncio
import logging
from datetime import datetime, timedelta
from src.database import MarketplaceEscrow, MarketplaceListing, SessionLocal
from src.api.maas_telemetry import uptime_tracker
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

# Settlement Threshold (99.9% uptime required)
SETTLEMENT_UPTIME_THRESHOLD = 0.999

async def marketplace_settlement_loop():
    """
    Daily background worker to release escrows to node owners 
    if the node maintained 99.9% uptime over the last 24h.
    """
    logger.info("💸 Marketplace Settlement service started")
    
    # Initialize Bridge for X0T payouts
    from src.core.settings import settings
    bridge_config = BridgeConfig(
        rpc_url=settings.rpc_url or "",
        contract_address=settings.contract_address or "",
        private_key=settings.operator_private_key or ""
    )
    bridge = TokenBridge(MeshToken(), bridge_config)

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
                    listing = db.query(MarketplaceListing).filter(
                        MarketplaceListing.id == escrow.listing_id
                    ).first()
                    
                    if not listing:
                        continue
                        
                    # 2. Check uptime
                    uptime = uptime_tracker.get_uptime_percent(listing.node_id)
                    
                    if uptime >= SETTLEMENT_UPTIME_THRESHOLD:
                        logger.info(f"✅ Node {listing.node_id} passed 99.9% uptime ({uptime:.2%}). Releasing escrow {escrow.id}")
                        
                        # Trigger on-chain release if X0T
                        if escrow.currency == "X0T":
                            await bridge.release_escrow_on_chain(escrow.id)
                        
                        escrow.status = "released"
                        escrow.released_at = datetime.utcnow()
                        # Finalize listing status if rental period ended
                        # (Assume simple hourly/daily model for now)
                        listing.status = "rented" # Still rented, just settled for last 24h
                        
                        record_audit_log(
                            db, None, "MARKETPLACE_SETTLEMENT_RELEASED",
                            user_id=escrow.renter_id,
                            payload={"escrow_id": escrow.id, "uptime": uptime},
                            status_code=200
                        )
                    else:
                        logger.warning(f"⚠️ Node {listing.node_id} FAILED 99.9% uptime ({uptime:.2%}). Refunding escrow {escrow.id}")
                        
                        # Trigger on-chain refund if X0T
                        if escrow.currency == "X0T":
                            await bridge.refund_escrow_on_chain(escrow.id)
                            
                        escrow.status = "refunded"
                        listing.status = "available"
                        listing.renter_id = None
                        
                        record_audit_log(
                            db, None, "MARKETPLACE_SETTLEMENT_REFUNDED",
                            user_id=escrow.renter_id,
                            payload={"escrow_id": escrow.id, "uptime": uptime},
                            status_code=200
                        )
                    
                    db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ Marketplace Settlement error: {e}")
            
        await asyncio.sleep(3600) # Run every hour to check for new candidates

if __name__ == "__main__":
    asyncio.run(marketplace_settlement_loop())
