import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from src.database import MarketplaceEscrow, MarketplaceListing, SessionLocal
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken
from src.services.marketplace_events import (
    bridge_upstream_evidence,
    publish_marketplace_escrow_event,
)
from src.services.service_event_identity import service_event_identity
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

_token_bridge = None
_SERVICE_AGENT = "maas-janitor"
_ESCROW_EXPIRY_HOURS = 1


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


def _janitor_timeout_evidence() -> dict[str, Any]:
    return {
        "decision_basis": "escrow_timeout_without_release",
        "source_quality": "local_db_expiry_scan_without_heartbeat_event_link",
        "dataplane_confirmed": False,
        "threshold_met": True,
        "measurement_window_hours": _ESCROW_EXPIRY_HOURS,
        "telemetry_evidence": {
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": (
            "Marketplace janitor timeout evidence is based on a local DB scan "
            "for held escrows older than the configured expiry window. It does "
            "not prove live dataplane failure, remote node authenticity, or "
            "external settlement finality."
        ),
    }


def _janitor_runtime_evidence(
    base_evidence: dict[str, Any],
    *,
    started_at: float,
    bridge_attempted: bool = False,
    bridge_status: str = "not_required",
    db_write_attempted: bool = False,
    db_committed: bool = False,
    escrow_status_after: Optional[Any] = None,
    listing_status_after: Optional[Any] = None,
) -> dict[str, Any]:
    evidence = dict(base_evidence)
    evidence.update(
        {
            "settlement_action": "janitor_refund",
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
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
        }
    )
    return evidence


def _merge_upstream_evidence(*items: dict[str, Any]) -> dict[str, list[str]]:
    event_ids: list[str] = []
    source_agents: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_ids = item.get("upstream_event_ids")
        if raw_ids is None:
            telemetry = item.get("telemetry_evidence")
            if isinstance(telemetry, dict):
                raw_ids = telemetry.get("event_ids")
        raw_agents = item.get("upstream_source_agents")
        if raw_agents is None:
            telemetry = item.get("telemetry_evidence")
            if isinstance(telemetry, dict):
                raw_agents = telemetry.get("source_agents")

        for value in raw_ids or []:
            text = str(value)
            if text and text not in event_ids:
                event_ids.append(text)
        for value in raw_agents or []:
            text = str(value)
            if text and text not in source_agents:
                source_agents.append(text)
    return {
        "upstream_event_ids": event_ids,
        "upstream_source_agents": source_agents,
    }


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
                expiry_limit = datetime.utcnow() - timedelta(hours=_ESCROW_EXPIRY_HOURS)
                expired_escrows = db.query(MarketplaceEscrow).filter(
                    MarketplaceEscrow.status == "held",
                    MarketplaceEscrow.created_at < expiry_limit
                ).all()

                for escrow in expired_escrows:
                    attempt_started = time.monotonic()
                    timeout_evidence = _janitor_timeout_evidence()
                    listing = db.query(MarketplaceListing).filter(
                        MarketplaceListing.id == escrow.listing_id
                    ).first()
                    
                    logger.info(f"⏳ Escrow {escrow.id} for listing {escrow.listing_id} expired (no heartbeat)")

                    bridge_evidence = {}
                    bridge_attempted = False
                    bridge_status = "not_required"
                    if escrow.currency == "X0T":
                        bridge = None
                        bridge_attempted = True
                        try:
                            bridge = _get_token_bridge()
                            refunded = await bridge.refund_escrow_on_chain(escrow.id)
                            bridge_evidence = bridge_upstream_evidence(bridge)
                        except Exception as exc:
                            bridge_evidence = bridge_upstream_evidence(bridge)
                            event_settlement_evidence = _janitor_runtime_evidence(
                                timeout_evidence,
                                started_at=attempt_started,
                                bridge_attempted=bridge_attempted,
                                bridge_status="error",
                                db_write_attempted=False,
                                db_committed=False,
                                escrow_status_after=getattr(escrow, "status", None),
                                listing_status_after=getattr(listing, "status", None)
                                if listing
                                else None,
                            )
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
                                settlement_evidence=event_settlement_evidence,
                                **_merge_upstream_evidence(
                                    event_settlement_evidence,
                                    bridge_evidence,
                                ),
                                **event_identity,
                            )
                            continue
                        if not refunded:
                            event_settlement_evidence = _janitor_runtime_evidence(
                                timeout_evidence,
                                started_at=attempt_started,
                                bridge_attempted=bridge_attempted,
                                bridge_status="rejected",
                                db_write_attempted=False,
                                db_committed=False,
                                escrow_status_after=getattr(escrow, "status", None),
                                listing_status_after=getattr(listing, "status", None)
                                if listing
                                else None,
                            )
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
                                settlement_evidence=event_settlement_evidence,
                                **_merge_upstream_evidence(
                                    event_settlement_evidence,
                                    bridge_evidence,
                                ),
                                **event_identity,
                            )
                            continue
                        bridge_status = "refunded"
                    
                    escrow.status = "refunded"
                    if listing:
                        listing.status = "available"
                        listing.renter_id = None
                        listing.mesh_id = None
                    
                    db.commit()
                    event_settlement_evidence = _janitor_runtime_evidence(
                        timeout_evidence,
                        started_at=attempt_started,
                        bridge_attempted=bridge_attempted,
                        bridge_status=bridge_status,
                        db_write_attempted=True,
                        db_committed=True,
                        escrow_status_after=getattr(escrow, "status", None),
                        listing_status_after=getattr(listing, "status", None)
                        if listing
                        else None,
                    )
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
                        settlement_evidence=event_settlement_evidence,
                        **_merge_upstream_evidence(
                            event_settlement_evidence,
                            bridge_evidence,
                        ),
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
