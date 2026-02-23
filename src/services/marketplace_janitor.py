import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.database import MarketplaceEscrow, MarketplaceListing, SessionLocal
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

async def marketplace_janitor_loop():
    """
    Background task to cleanup expired or failed escrows.
    If a node doesn't send a heartbeat within 1 hour of rental, 
    auto-refund the escrow and make node available again.
    """
    logger.info("🧹 Marketplace Janitor service started")
    while True:
        try:
            db = SessionLocal()
            try:
                # 1. Find held escrows older than 1 hour without release
                expiry_limit = datetime.utcnow() - timedelta(hours=1)
                expired_escrows = db.query(MarketplaceEscrow).filter(
                    MarketplaceEscrow.status == "held",
                    MarketplaceEscrow.created_at < expiry_limit
                ).all()

                for escrow in expired_escrows:
                    listing = db.query(MarketplaceListing).filter(
                        MarketplaceListing.id == escrow.listing_id
                    ).first()
                    
                    logger.info(f"⏳ Escrow {escrow.id} for listing {escrow.listing_id} expired (no heartbeat)")
                    
                    escrow.status = "refunded"
                    if listing:
                        listing.status = "available"
                        listing.renter_id = None
                        listing.mesh_id = None
                    
                    db.commit()
                    
                    record_audit_log(
                        db, None, "MARKETPLACE_ESCROW_AUTO_REFUNDED",
                        user_id=escrow.renter_id,
                        payload={"escrow_id": escrow.id, "reason": "timeout_no_heartbeat"},
                        status_code=200
                    )
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ Marketplace Janitor error: {e}")
            
        await asyncio.sleep(600) # Run every 10 minutes

if __name__ == "__main__":
    # For manual testing
    asyncio.run(marketplace_janitor_loop())
