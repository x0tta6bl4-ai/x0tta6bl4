import asyncio
import logging
from datetime import datetime, timedelta
from src.database import MarketplaceEscrow, MarketplaceListing, SessionLocal
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.service_event_identity import service_event_identity
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

_token_bridge = None
_SERVICE_AGENT = "maas-janitor"


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


async def marketplace_janitor_loop():
    """
    Background task to cleanup expired or failed escrows.
    If a node doesn't send a heartbeat within 1 hour of rental, 
    auto-refund the escrow and make node available again.
    """
    logger.info("🧹 Marketplace Janitor service started")
    event_identity = service_event_identity(service_name=_SERVICE_AGENT)
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

                    if escrow.currency == "X0T":
                        try:
                            refunded = await _get_token_bridge().refund_escrow_on_chain(escrow.id)
                        except Exception as exc:
                            logger.error("X0T janitor refund bridge error for escrow %s: %s", escrow.id, exc)
                            publish_marketplace_escrow_event(
                                transition="blocked",
                                source_agent=_SERVICE_AGENT,
                                escrow_id=escrow.id,
                                listing_id=escrow.listing_id,
                                renter_id=escrow.renter_id,
                                actor_id="janitor-loop",
                                currency=escrow.currency,
                                status="held",
                                node_id=getattr(listing, "node_id", None) if listing else None,
                                mesh_id=getattr(listing, "mesh_id", None) if listing else None,
                                amount_cents=getattr(escrow, "amount_cents", None),
                                amount_token=getattr(escrow, "amount_token", None),
                                reason="refund_bridge_error",
                                **event_identity,
                            )
                            continue
                        if not refunded:
                            logger.error(
                                "X0T janitor refund refused for escrow %s; leaving escrow held",
                                escrow.id,
                            )
                            publish_marketplace_escrow_event(
                                transition="blocked",
                                source_agent=_SERVICE_AGENT,
                                escrow_id=escrow.id,
                                listing_id=escrow.listing_id,
                                renter_id=escrow.renter_id,
                                actor_id="janitor-loop",
                                currency=escrow.currency,
                                status="held",
                                node_id=getattr(listing, "node_id", None) if listing else None,
                                mesh_id=getattr(listing, "mesh_id", None) if listing else None,
                                amount_cents=getattr(escrow, "amount_cents", None),
                                amount_token=getattr(escrow, "amount_token", None),
                                reason="refund_bridge_rejected",
                                **event_identity,
                            )
                            continue
                    
                    escrow.status = "refunded"
                    if listing:
                        listing.status = "available"
                        listing.renter_id = None
                        listing.mesh_id = None
                    
                    db.commit()
                    escrow_event_id = publish_marketplace_escrow_event(
                        transition="refunded",
                        source_agent=_SERVICE_AGENT,
                        escrow_id=escrow.id,
                        listing_id=escrow.listing_id,
                        renter_id=escrow.renter_id,
                        actor_id="janitor-loop",
                        currency=escrow.currency,
                        status="refunded",
                        node_id=getattr(listing, "node_id", None) if listing else None,
                        mesh_id=getattr(listing, "mesh_id", None) if listing else None,
                        amount_cents=getattr(escrow, "amount_cents", None),
                        amount_token=getattr(escrow, "amount_token", None),
                        reason="timeout_no_heartbeat",
                        **event_identity,
                    )
                    
                    record_audit_log(
                        db, None, "MARKETPLACE_ESCROW_AUTO_REFUNDED",
                        user_id=escrow.renter_id,
                        payload={
                            "escrow_id": escrow.id,
                            "reason": "timeout_no_heartbeat",
                            "event_id": escrow_event_id,
                        },
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
