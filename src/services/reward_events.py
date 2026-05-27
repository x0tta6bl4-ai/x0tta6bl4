"""Reward settlement event publication helpers."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Reward relay lifecycle event only. It records local reward accounting or "
    "submission attempts and does not prove final live external settlement by itself."
)

_TRANSITION_EVENT_TYPES = {
    "recorded": EventType.REWARD_RELAY_RECORDED,
    "blocked": EventType.REWARD_RELAY_BLOCKED,
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


def publish_reward_settlement_event(
    *,
    transition: str,
    source_agent: str,
    node_address: Any,
    node_id: Any = None,
    spiffe_id: Any = None,
    did: Any = None,
    wallet_address: Any = None,
    packets: Any = None,
    amount: Any = None,
    status: Any = None,
    submitted_transaction: Any = None,
    simulated: Any = None,
    settlement_recorded: Any = None,
    local_accounting_recorded: Any = None,
    transaction_hash: Any = None,
    reason: str = "",
    event_bus: Optional[EventBus] = None,
    project_root: str = ".",
) -> Optional[str]:
    """Publish a best-effort reward settlement event with canonical identity fields."""
    event_type = _TRANSITION_EVENT_TYPES.get(transition, EventType.REWARD_RELAY_BLOCKED)
    reward_identity = {
        "node_id": _identity_value(node_id),
        "spiffe_id": _identity_value(spiffe_id),
        "did": _identity_value(did),
        "wallet_address": _identity_value(wallet_address),
        "reward_address": _identity_value(node_address),
    }
    payload = {
        "transition": transition,
        "node_id": reward_identity["node_id"],
        "spiffe_id": reward_identity["spiffe_id"],
        "did": reward_identity["did"],
        "wallet_address": reward_identity["wallet_address"],
        "reward_address": reward_identity["reward_address"],
        "packets": _json_value(packets),
        "amount": _json_value(amount),
        "status": _identity_value(status),
        "submitted_transaction": _json_value(submitted_transaction),
        "simulated": _json_value(simulated),
        "settlement_recorded": _json_value(settlement_recorded),
        "local_accounting_recorded": _json_value(local_accounting_recorded),
        "transaction_hash": _identity_value(transaction_hash),
        "reason": reason,
        "identity": reward_identity,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    try:
        bus = event_bus or get_event_bus(project_root)
        event = bus.publish(event_type, source_agent, payload, priority=5)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish reward settlement event: %s", exc)
        return None
