"""Reward settlement event publication helpers."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Reward relay lifecycle event only. It records local reward accounting or "
    "submission attempts and does not prove final live external settlement by itself. "
    "Canonical event payloads retain reward identity fields for compatibility; "
    "trace and ledger surfaces must use redaction or identity_metadata hashes."
)
REWARD_CLAIM_GATE_BOUNDARY = (
    "Reward claim gate allows local reward accounting or pending submission claims "
    "only. Reward events do not prove traffic delivery, dataplane delivery, token "
    "settlement finality, or production readiness unless separate upstream "
    "dataplane and chain-finality evidence exists."
)

_TRANSITION_EVENT_TYPES = {
    "recorded": EventType.REWARD_RELAY_RECORDED,
    "blocked": EventType.REWARD_RELAY_BLOCKED,
}
_UPSTREAM_EVENT_ID_LIMIT = 10
_EVIDENCE_METADATA_KEY_LIMIT = 32
_EVIDENCE_METADATA_LIST_LIMIT = 20
_EVIDENCE_METADATA_STRING_LIMIT = 160
_CLAIM_SUMMARY_LIST_LIMIT = 12
_SENSITIVE_METADATA_FRAGMENTS = (
    "address",
    "wallet",
    "contract",
    "node_id",
    "path",
    "file",
    "secret",
    "password",
    "token",
    "key",
    "private",
    "credential",
    "transaction",
    "tx_hash",
)


def _identity_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _hashed_metadata_value(value: Any) -> Optional[str]:
    digest = _hash_value(value)
    return f"sha256:{digest}" if digest else None


def _identity_metadata(identity: dict[str, Optional[str]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "values_redacted": True,
        "canonical_identity_payload_retained": True,
    }
    for key, value in identity.items():
        metadata[f"{key}_present"] = value is not None
        metadata[f"{key}_hash"] = _hashed_metadata_value(value)
    return metadata


def _is_prehashed_key(key: str) -> bool:
    key_lower = str(key).lower()
    return key_lower.endswith("_hash") or key_lower.endswith("_hashes")


def _is_sensitive_metadata_key(key: str) -> bool:
    key_lower = str(key).lower()
    if _is_prehashed_key(key_lower):
        return False
    return any(fragment in key_lower for fragment in _SENSITIVE_METADATA_FRAGMENTS)


def _safe_metadata_value(key: str, value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, dict) and depth < 3:
        items = list(value.items())[:_EVIDENCE_METADATA_KEY_LIMIT]
        return {
            str(child_key): _safe_metadata_value(str(child_key), child_value, depth + 1)
            for child_key, child_value in items
        }
    if isinstance(value, (list, tuple, set)) and depth < 3:
        return [
            _safe_metadata_value(key, item, depth + 1)
            for item in list(value)[:_EVIDENCE_METADATA_LIST_LIMIT]
        ]

    text = str(value)
    if _is_sensitive_metadata_key(key):
        digest = _hash_value(text)
        return f"sha256:{digest}" if digest else None
    if len(text) > _EVIDENCE_METADATA_STRING_LIMIT:
        digest = _hash_value(text)
        return f"sha256:{digest}" if digest else text[:_EVIDENCE_METADATA_STRING_LIMIT]
    return text


def _safe_evidence_metadata(metadata: Any = None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return {
        str(key): _safe_metadata_value(str(key), value)
        for key, value in list(metadata.items())[:_EVIDENCE_METADATA_KEY_LIMIT]
    }


def _raw_string_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raw_values = [values]
    else:
        try:
            raw_values = list(values)
        except TypeError:
            raw_values = [values]
    return [str(value) for value in raw_values if str(value)]


def _safe_string_list(values: Any, *, limit: int = _UPSTREAM_EVENT_ID_LIMIT) -> list[str]:
    return _raw_string_values(values)[-limit:]


def _safe_claim_id_list(values: Any) -> list[str]:
    return _raw_string_values(values)[-_CLAIM_SUMMARY_LIST_LIMIT:]


def _safe_claim_gate_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"present": False, "payloads_redacted": True}
    return {
        "present": True,
        "schema": _identity_value(value.get("schema")),
        "surface": _identity_value(value.get("surface")),
        "status": _identity_value(value.get("status")),
        "decision": _identity_value(value.get("decision")),
        "local_spine_lifecycle_claim_allowed": _bool_value(
            value.get("local_spine_lifecycle_claim_allowed")
        ),
        "policy_decision_claim_allowed": _bool_value(
            value.get("policy_decision_claim_allowed")
        ),
        "local_actuator_execution_claim_allowed": _bool_value(
            value.get("local_actuator_execution_claim_allowed")
        ),
        "local_reward_adapter_record_claim_allowed": _bool_value(
            value.get("local_reward_adapter_record_claim_allowed")
        ),
        "production_readiness_claim_allowed": _bool_value(
            value.get("production_readiness_claim_allowed")
        ),
        "dataplane_delivery_claim_allowed": _bool_value(
            value.get("dataplane_delivery_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": _bool_value(
            value.get("traffic_delivery_claim_allowed")
        ),
        "customer_traffic_claim_allowed": _bool_value(
            value.get("customer_traffic_claim_allowed")
        ),
        "external_dpi_bypass_claim_allowed": _bool_value(
            value.get("external_dpi_bypass_claim_allowed")
        ),
        "external_settlement_finality_claim_allowed": _bool_value(
            value.get("external_settlement_finality_claim_allowed")
        ),
        "blocked_claim_ids": _safe_claim_id_list(value.get("blocked_claim_ids")),
        "payloads_redacted": True,
    }


def _safe_cross_plane_claim_gate_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"present": False, "payloads_redacted": True}
    return {
        "present": True,
        "schema": _identity_value(value.get("schema")),
        "surface": _identity_value(value.get("surface")),
        "decision": _identity_value(value.get("decision")),
        "allowed": _bool_value(value.get("allowed")),
        "requested_claim_ids": _safe_claim_id_list(value.get("requested_claim_ids")),
        "blockers": _safe_claim_id_list(value.get("blockers")),
        "payloads_redacted": True,
    }


def _upstream_evidence(
    event_ids: Any = None,
    source_agents: Any = None,
    claim_gate: Any = None,
    cross_plane_claim_gate: Any = None,
) -> dict[str, Any]:
    raw_event_ids = _raw_string_values(event_ids)
    safe_event_ids = raw_event_ids[-_UPSTREAM_EVENT_ID_LIMIT:]
    safe_source_agents = _safe_string_list(source_agents)
    return {
        "source_agents": safe_source_agents,
        "event_ids": safe_event_ids,
        "events_total": len(raw_event_ids),
        "event_ids_limit": _UPSTREAM_EVENT_ID_LIMIT,
        "event_ids_truncated": len(raw_event_ids) > _UPSTREAM_EVENT_ID_LIMIT,
        "claim_gate_summary": _safe_claim_gate_summary(claim_gate),
        "cross_plane_claim_gate_summary": _safe_cross_plane_claim_gate_summary(
            cross_plane_claim_gate
        ),
        "payloads_redacted": True,
    }


def _bool_value(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def _reward_claim_gate(
    *,
    submitted_transaction: Any,
    settlement_recorded: Any,
    local_accounting_recorded: Any,
    simulated: Any,
) -> dict[str, Any]:
    submitted = _bool_value(submitted_transaction)
    local_accounting = bool(
        _bool_value(local_accounting_recorded) or _bool_value(settlement_recorded)
    )
    if submitted:
        decision = "pending_token_submission_only"
    elif local_accounting:
        decision = "local_reward_accounting_only"
    else:
        decision = "blocked_or_unrecorded"

    return {
        "decision": decision,
        "local_reward_accounting_claim_allowed": local_accounting,
        "pending_token_submission_claim_allowed": submitted,
        "traffic_delivery_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "token_settlement_finality_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_upstream_dataplane_evidence_for_traffic_claim": True,
        "requires_chain_finality_evidence_for_settlement_claim": True,
        "simulated": _bool_value(simulated),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": REWARD_CLAIM_GATE_BOUNDARY,
    }


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
    upstream_event_ids: Any = None,
    upstream_source_agents: Any = None,
    upstream_claim_gate: Any = None,
    upstream_cross_plane_claim_gate: Any = None,
    evidence_metadata: Any = None,
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
        "identity_metadata": _identity_metadata(reward_identity),
        "packets": _json_value(packets),
        "amount": _json_value(amount),
        "status": _identity_value(status),
        "submitted_transaction": _json_value(submitted_transaction),
        "simulated": _json_value(simulated),
        "settlement_recorded": _json_value(settlement_recorded),
        "local_accounting_recorded": _json_value(local_accounting_recorded),
        "transaction_hash": _identity_value(transaction_hash),
        "upstream_evidence": _upstream_evidence(
            upstream_event_ids,
            upstream_source_agents,
            upstream_claim_gate,
            upstream_cross_plane_claim_gate,
        ),
        "reward_claim_gate": _reward_claim_gate(
            submitted_transaction=submitted_transaction,
            settlement_recorded=settlement_recorded,
            local_accounting_recorded=local_accounting_recorded,
            simulated=simulated,
        ),
        "evidence_metadata": _safe_evidence_metadata(evidence_metadata),
        "evidence_metadata_values_redacted": True,
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
