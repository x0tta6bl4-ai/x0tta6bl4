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
from src.services.marketplace_events import (
    bridge_upstream_evidence,
    publish_marketplace_escrow_event,
)
from src.services.service_event_identity import service_event_identity
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

# Settlement Threshold (99.9% uptime required)
SETTLEMENT_UPTIME_THRESHOLD = 0.999

_token_bridge = None
_SERVICE_AGENT = "maas-settlement"
_TELEMETRY_SOURCE_AGENT = "maas-telemetry"
_UPTIME_EVIDENCE_EVENT_ID_LIMIT = 10
_SETTLEMENT_CLAIM_GATE_BOUNDARY = (
    "Marketplace settlement claim gate allows only local escrow lifecycle claims "
    "from this worker. Uptime, DB writes, bridge submission, and marketplace events "
    "do not prove traffic delivery, dataplane delivery, external settlement "
    "finality, or production readiness. This worker never promotes high-risk "
    "claims; those must be evaluated by separate cross-plane proof gates."
)
_SETTLEMENT_HIGH_RISK_BLOCKER_REASON_IDS = (
    "marketplace_settlement_local_lifecycle_only",
    "dataplane_delivery_requires_cross_plane_proof_gate",
    "traffic_delivery_requires_cross_plane_proof_gate",
    "external_settlement_finality_requires_external_proof_gate",
    "production_readiness_requires_cross_plane_proof_gate",
)


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


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _latest_telemetry_event_ids(
    node_id: Any,
    *,
    event_bus: Optional[EventBus] = None,
    project_root: str = ".",
) -> list[str]:
    node_hash = _redacted_sha256_prefix(node_id)
    if node_hash is None:
        return []

    bus = event_bus
    if bus is None:
        try:
            bus = get_event_bus(project_root)
        except Exception:
            return []

    try:
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=_TELEMETRY_SOURCE_AGENT,
            limit=1000,
        )
    except Exception:
        return []

    event_ids = [
        event.event_id
        for event in events
        if event.data.get("node_id_hash") == node_hash
        and event.data.get("operation")
        in {
            "telemetry_snapshot_write",
            "telemetry_snapshot_read",
            "telemetry_history_read",
        }
    ]
    return event_ids[-_UPTIME_EVIDENCE_EVENT_ID_LIMIT:]


def _settlement_uptime_evidence(
    *,
    node_id: Any,
    uptime: float,
    threshold: float = SETTLEMENT_UPTIME_THRESHOLD,
    event_bus: Optional[EventBus] = None,
) -> dict[str, Any]:
    telemetry_event_ids = _latest_telemetry_event_ids(
        node_id,
        event_bus=event_bus,
    )
    return {
        "decision_basis": "uptime_tracker_cached_window",
        "source_quality": (
            "telemetry_eventbus_linked_uptime_tracker"
            if telemetry_event_ids
            else "uptime_tracker_without_eventbus_link"
        ),
        "dataplane_confirmed": False,
        "threshold_met": uptime >= threshold,
        "uptime_percent": round(float(uptime), 6),
        "uptime_threshold": round(float(threshold), 6),
        "measurement_window_hours": 24,
        "telemetry_evidence": {
            "source_agents": [_TELEMETRY_SOURCE_AGENT] if telemetry_event_ids else [],
            "event_ids": telemetry_event_ids,
            "events_total": len(telemetry_event_ids),
            "payloads_redacted": True,
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": (
            "Marketplace settlement uptime evidence is based on cached uptime "
            "tracker observations and optional maas-telemetry EventBus links. It "
            "does not prove live dataplane reachability, current packet delivery, "
            "or remote node authenticity at settlement time."
        ),
    }


def _settlement_runtime_evidence(
    settlement_evidence: dict[str, Any],
    *,
    action: str,
    started_at: float,
    bridge_attempted: bool = False,
    bridge_status: str = "not_required",
    db_write_attempted: bool = False,
    db_committed: bool = False,
    escrow_status_after: Optional[Any] = None,
    listing_status_after: Optional[Any] = None,
) -> dict[str, Any]:
    evidence = dict(settlement_evidence)
    upstream_high_risk_claims_present = any(
        evidence.get(flag) is True
        for flag in (
            "dataplane_confirmed",
            "dataplane_delivery_claim_allowed",
            "traffic_delivery_claim_allowed",
            "customer_traffic_claim_allowed",
            "production_readiness_claim_allowed",
            "production_ready",
        )
    ) or any(
        evidence.get(flag) is True
        for flag in (
            "live_provider_settlement_confirmed",
            "bank_settlement_confirmed",
            "chain_finality_confirmed",
            "external_settlement_finality_confirmed",
            "external_settlement_finality_claim_allowed",
        )
    )
    local_lifecycle_claim_allowed = bool(
        db_committed and action in {"release", "refund"}
    )
    evidence.update(
        {
            "settlement_action": str(action)[:80],
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
            "claim_gate": {
                "decision": (
                    "local_escrow_lifecycle_only"
                    if local_lifecycle_claim_allowed
                    else "blocked_or_uncommitted"
                ),
                "local_escrow_lifecycle_claim_allowed": (
                    local_lifecycle_claim_allowed
                ),
                "traffic_delivery_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_dataplane_evidence_for_delivery_claim": True,
                "requires_external_finality_evidence_for_settlement_claim": True,
                "requires_cross_plane_proof_gate_for_high_risk_claims": True,
                "upstream_high_risk_claims_present": (
                    upstream_high_risk_claims_present
                ),
                "blocker_reason_ids": list(
                    _SETTLEMENT_HIGH_RISK_BLOCKER_REASON_IDS
                ),
                "bridge_status": str(bridge_status)[:80],
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
                "claim_boundary": _SETTLEMENT_CLAIM_GATE_BOUNDARY,
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
                            bridge = None
                            bridge_attempted = True
                            try:
                                bridge = _get_token_bridge()
                                released = await bridge.release_escrow_on_chain(escrow.id)
                                bridge_evidence = bridge_upstream_evidence(bridge)
                            except Exception as exc:
                                bridge_evidence = bridge_upstream_evidence(bridge)
                                event_settlement_evidence = _settlement_runtime_evidence(
                                    settlement_evidence,
                                    action="release",
                                    started_at=attempt_started,
                                    bridge_attempted=bridge_attempted,
                                    bridge_status="error",
                                    db_write_attempted=False,
                                    db_committed=False,
                                    escrow_status_after=getattr(escrow, "status", None),
                                    listing_status_after=getattr(listing, "status", None),
                                )
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
                                    settlement_evidence=event_settlement_evidence,
                                    **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
                                    **event_identity,
                                )
                                continue
                            if not released:
                                event_settlement_evidence = _settlement_runtime_evidence(
                                    settlement_evidence,
                                    action="release",
                                    started_at=attempt_started,
                                    bridge_attempted=bridge_attempted,
                                    bridge_status="rejected",
                                    db_write_attempted=False,
                                    db_committed=False,
                                    escrow_status_after=getattr(escrow, "status", None),
                                    listing_status_after=getattr(listing, "status", None),
                                )
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
                                    settlement_evidence=event_settlement_evidence,
                                    **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
                                    **event_identity,
                                )
                                continue
                            bridge_status = "released"
                        
                        escrow.status = "released"
                        escrow.released_at = datetime.utcnow()
                        # Finalize listing status if rental period ended
                        # (Assume simple hourly/daily model for now)
                        listing.status = "rented" # Still rented, just settled for last 24h
                        db.commit()
                        event_settlement_evidence = _settlement_runtime_evidence(
                            settlement_evidence,
                            action="release",
                            started_at=attempt_started,
                            bridge_attempted=bridge_attempted,
                            bridge_status=bridge_status,
                            db_write_attempted=True,
                            db_committed=True,
                            escrow_status_after=getattr(escrow, "status", None),
                            listing_status_after=getattr(listing, "status", None),
                        )
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
                            settlement_evidence=event_settlement_evidence,
                            **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
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
                            bridge = None
                            bridge_attempted = True
                            try:
                                bridge = _get_token_bridge()
                                refunded = await bridge.refund_escrow_on_chain(escrow.id)
                                bridge_evidence = bridge_upstream_evidence(bridge)
                            except Exception as exc:
                                bridge_evidence = bridge_upstream_evidence(bridge)
                                event_settlement_evidence = _settlement_runtime_evidence(
                                    settlement_evidence,
                                    action="refund",
                                    started_at=attempt_started,
                                    bridge_attempted=bridge_attempted,
                                    bridge_status="error",
                                    db_write_attempted=False,
                                    db_committed=False,
                                    escrow_status_after=getattr(escrow, "status", None),
                                    listing_status_after=getattr(listing, "status", None),
                                )
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
                                    settlement_evidence=event_settlement_evidence,
                                    **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
                                    **event_identity,
                                )
                                continue
                            if not refunded:
                                event_settlement_evidence = _settlement_runtime_evidence(
                                    settlement_evidence,
                                    action="refund",
                                    started_at=attempt_started,
                                    bridge_attempted=bridge_attempted,
                                    bridge_status="rejected",
                                    db_write_attempted=False,
                                    db_committed=False,
                                    escrow_status_after=getattr(escrow, "status", None),
                                    listing_status_after=getattr(listing, "status", None),
                                )
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
                                    settlement_evidence=event_settlement_evidence,
                                    **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
                                    **event_identity,
                                )
                                continue
                            bridge_status = "refunded"
                            
                        escrow.status = "refunded"
                        listing.status = "available"
                        listing.renter_id = None
                        db.commit()
                        event_settlement_evidence = _settlement_runtime_evidence(
                            settlement_evidence,
                            action="refund",
                            started_at=attempt_started,
                            bridge_attempted=bridge_attempted,
                            bridge_status=bridge_status,
                            db_write_attempted=True,
                            db_committed=True,
                            escrow_status_after=getattr(escrow, "status", None),
                            listing_status_after=getattr(listing, "status", None),
                        )
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
                            settlement_evidence=event_settlement_evidence,
                            **_merge_upstream_evidence(event_settlement_evidence, bridge_evidence),
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
