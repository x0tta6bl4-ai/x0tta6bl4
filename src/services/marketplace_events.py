"""Marketplace escrow event publication helpers."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Marketplace escrow lifecycle event only. It records local state transitions "
    "or fail-closed blocked attempts and does not prove live external settlement "
    "by itself."
)

_TRANSITION_EVENT_TYPES = {
    "held": EventType.MARKETPLACE_ESCROW_HELD,
    "released": EventType.MARKETPLACE_ESCROW_RELEASED,
    "refunded": EventType.MARKETPLACE_ESCROW_REFUNDED,
    "blocked": EventType.MARKETPLACE_ESCROW_BLOCKED,
}


def _identity_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def publish_marketplace_escrow_event(
    *,
    transition: str,
    source_agent: str,
    escrow_id: Any,
    listing_id: Any,
    renter_id: Any = None,
    actor_id: Any = None,
    currency: Any = None,
    status: Any = None,
    node_id: Any = None,
    mesh_id: Any = None,
    spiffe_id: Any = None,
    did: Any = None,
    wallet_address: Any = None,
    amount_cents: Any = None,
    amount_token: Any = None,
    reason: str = "",
    event_bus: Optional[EventBus] = None,
    project_root: str = ".",
) -> Optional[str]:
    """Publish a best-effort escrow lifecycle event with canonical identity fields."""
    event_type = _TRANSITION_EVENT_TYPES.get(transition, EventType.MARKETPLACE_ESCROW_BLOCKED)
    escrow_identity = {
        "escrow_id": _identity_value(escrow_id),
        "listing_id": _identity_value(listing_id),
        "renter_id": _identity_value(renter_id),
        "actor_id": _identity_value(actor_id),
        "node_id": _identity_value(node_id),
        "mesh_id": _identity_value(mesh_id),
        "spiffe_id": _identity_value(spiffe_id),
        "did": _identity_value(did),
        "wallet_address": _identity_value(wallet_address),
    }
    payload = {
        "transition": transition,
        "escrow_id": escrow_identity["escrow_id"],
        "listing_id": escrow_identity["listing_id"],
        "renter_id": escrow_identity["renter_id"],
        "actor_id": escrow_identity["actor_id"],
        "currency": _identity_value(currency),
        "status": _identity_value(status),
        "node_id": escrow_identity["node_id"],
        "mesh_id": escrow_identity["mesh_id"],
        "spiffe_id": escrow_identity["spiffe_id"],
        "did": escrow_identity["did"],
        "wallet_address": escrow_identity["wallet_address"],
        "amount_cents": _json_value(amount_cents),
        "amount_token": _json_value(amount_token),
        "reason": reason,
        "identity": escrow_identity,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    try:
        bus = event_bus or get_event_bus(project_root)
        event = bus.publish(event_type, source_agent, payload, priority=5)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish marketplace escrow event: %s", exc)
        return None
