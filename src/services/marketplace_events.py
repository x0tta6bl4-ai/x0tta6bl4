"""Marketplace escrow event publication helpers."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from src.coordination.events import EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)

CLAIM_BOUNDARY = (
    "Marketplace escrow lifecycle event only. It records local state transitions "
    "or fail-closed blocked attempts and does not prove live external settlement "
    "by itself. Escrow, actor, node, mesh, wallet, and free-form reason values "
    "are represented by safe slugs or hashes on trace-facing payloads."
)

_TRANSITION_EVENT_TYPES = {
    "held": EventType.MARKETPLACE_ESCROW_HELD,
    "released": EventType.MARKETPLACE_ESCROW_RELEASED,
    "refunded": EventType.MARKETPLACE_ESCROW_REFUNDED,
    "blocked": EventType.MARKETPLACE_ESCROW_BLOCKED,
}
_UPSTREAM_EVENT_ID_LIMIT = 10
_REQUEST_EVIDENCE_KEY_LIMIT = 32
_REQUEST_EVIDENCE_STRING_LIMIT = 256
_SAFE_REASON_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_SENSITIVE_REQUEST_EVIDENCE_FRAGMENTS = (
    "address",
    "did",
    "email",
    "id",
    "key",
    "secret",
    "spiffe",
    "token",
    "wallet",
)
_SOURCE_AGENT_LAYERS = {
    "maas-marketplace": "api_to_commerce",
    "maas-nodes-heartbeat": "api_mesh_to_commerce",
    "maas-settlement": "commerce_settlement_to_events",
    "maas-janitor": "commerce_maintenance_to_events",
    "token-bridge": "dao_chain_bridge",
}


def _identity_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    normalized = _identity_value(value)
    if normalized is None:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _safe_reason(value: Any) -> dict[str, Any]:
    normalized = _identity_value(value)
    if normalized is None:
        return {
            "reason": "",
            "reason_hash": None,
            "reason_redacted": False,
        }

    digest = _redacted_sha256_prefix(normalized)
    if _SAFE_REASON_PATTERN.fullmatch(normalized):
        return {
            "reason": normalized,
            "reason_hash": digest,
            "reason_redacted": False,
        }

    return {
        "reason": f"sha256:{digest}" if digest else "[redacted]",
        "reason_hash": digest,
        "reason_redacted": True,
    }


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


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


def _upstream_evidence(
    event_ids: Any = None,
    source_agents: Any = None,
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
        "payloads_redacted": True,
    }


def _source_layer(source_agent: str) -> str:
    normalized = _identity_value(source_agent) or ""
    return _SOURCE_AGENT_LAYERS.get(normalized, "commerce_escrow_lifecycle")


def bridge_upstream_evidence(bridge: Any, *, default_source_agent: str = "token-bridge") -> dict[str, Any]:
    if bridge is None:
        return {}

    raw_event_ids = getattr(bridge, "last_chain_write_event_ids", None)
    if callable(raw_event_ids):
        raw_event_ids = raw_event_ids()
    if raw_event_ids is None:
        raw_event_ids = getattr(bridge, "_last_chain_write_event_ids", None)
    if raw_event_ids is None:
        return {}
    event_ids = _raw_string_values(raw_event_ids)
    if not event_ids:
        return {}

    source_agent = _identity_value(getattr(bridge, "source_agent", None))
    return {
        "upstream_event_ids": event_ids,
        "upstream_source_agents": [source_agent or default_source_agent],
    }


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def _safe_request_evidence_value(key: str, value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    key_lower = str(key).lower()
    if key_lower.endswith("_hash") or key_lower.endswith("_hashes"):
        text = str(value).strip()
        return text[:_REQUEST_EVIDENCE_STRING_LIMIT] if text else None
    if isinstance(value, dict):
        return _request_evidence(value)
    if isinstance(value, (list, tuple, set)):
        return [
            _safe_request_evidence_value(key, item)
            for item in list(value)[:_REQUEST_EVIDENCE_KEY_LIMIT]
        ]
    if any(fragment in key_lower for fragment in _SENSITIVE_REQUEST_EVIDENCE_FRAGMENTS):
        digest = _redacted_sha256_prefix(value)
        return f"sha256:{digest}" if digest else None
    text = str(value).strip()
    return text[:_REQUEST_EVIDENCE_STRING_LIMIT] if text else None


def _request_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe = {
        str(key): _safe_request_evidence_value(str(key), item)
        for key, item in list(value.items())[:_REQUEST_EVIDENCE_KEY_LIMIT]
    }
    safe["raw_identifiers_redacted"] = True
    safe["payloads_redacted"] = True
    return safe


def _claim_gate_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe = {
        "decision": _identity_value(value.get("decision")),
        "local_escrow_lifecycle_claim_allowed": _safe_bool(
            value.get("local_escrow_lifecycle_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": _safe_bool(
            value.get("traffic_delivery_claim_allowed")
        ),
        "dataplane_delivery_claim_allowed": _safe_bool(
            value.get("dataplane_delivery_claim_allowed")
        ),
        "external_settlement_finality_claim_allowed": _safe_bool(
            value.get("external_settlement_finality_claim_allowed")
        ),
        "production_readiness_claim_allowed": _safe_bool(
            value.get("production_readiness_claim_allowed")
        ),
        "requires_dataplane_evidence_for_delivery_claim": _safe_bool(
            value.get("requires_dataplane_evidence_for_delivery_claim")
        ),
        "requires_external_finality_evidence_for_settlement_claim": _safe_bool(
            value.get("requires_external_finality_evidence_for_settlement_claim")
        ),
        "bridge_status": _identity_value(value.get("bridge_status")),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    claim_boundary = _identity_value(value.get("claim_boundary"))
    if claim_boundary:
        safe["claim_boundary"] = claim_boundary[:300]
    return safe


def _settlement_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    telemetry_evidence = value.get("telemetry_evidence")
    if not isinstance(telemetry_evidence, dict):
        telemetry_evidence = {}

    safe = {
        "decision_basis": _identity_value(value.get("decision_basis")),
        "source_quality": _identity_value(value.get("source_quality")),
        "settlement_action": _identity_value(value.get("settlement_action")),
        "duration_ms": _safe_float(value.get("duration_ms")),
        "dataplane_confirmed": _safe_bool(value.get("dataplane_confirmed")),
        "threshold_met": _safe_bool(value.get("threshold_met")),
        "uptime_percent": _safe_float(value.get("uptime_percent")),
        "uptime_threshold": _safe_float(value.get("uptime_threshold")),
        "measurement_window_hours": _safe_float(
            value.get("measurement_window_hours")
        ),
        "bridge_evidence": _request_evidence(value.get("bridge_evidence")),
        "db_write_evidence": _request_evidence(value.get("db_write_evidence")),
        "output_summary": _request_evidence(value.get("output_summary")),
        "claim_gate": _claim_gate_evidence(value.get("claim_gate")),
        "telemetry_evidence": _upstream_evidence(
            telemetry_evidence.get("event_ids"),
            telemetry_evidence.get("source_agents"),
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }
    claim_boundary = _identity_value(value.get("claim_boundary"))
    if claim_boundary:
        safe["claim_boundary"] = claim_boundary[:300]
    return safe


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
    upstream_event_ids: Any = None,
    upstream_source_agents: Any = None,
    request_evidence: Any = None,
    settlement_evidence: Any = None,
    reason: str = "",
    event_bus: Optional[EventBus] = None,
    project_root: str = ".",
) -> Optional[str]:
    """Publish a best-effort escrow lifecycle event with canonical identity fields."""
    event_type = _TRANSITION_EVENT_TYPES.get(transition, EventType.MARKETPLACE_ESCROW_BLOCKED)
    source_alias = _identity_value(source_agent) or "unknown"
    reason_metadata = _safe_reason(reason)
    escrow_identity = {
        "escrow_id_hash": _redacted_sha256_prefix(escrow_id),
        "listing_id_hash": _redacted_sha256_prefix(listing_id),
        "renter_id_hash": _redacted_sha256_prefix(renter_id),
        "actor_id_hash": _redacted_sha256_prefix(actor_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "spiffe_id_hash": _redacted_sha256_prefix(spiffe_id),
        "did_hash": _redacted_sha256_prefix(did),
        "wallet_address_hash": _redacted_sha256_prefix(wallet_address),
    }
    identity_fields_present = {
        "escrow_id": _identity_value(escrow_id) is not None,
        "listing_id": _identity_value(listing_id) is not None,
        "renter_id": _identity_value(renter_id) is not None,
        "actor_id": _identity_value(actor_id) is not None,
        "node_id": _identity_value(node_id) is not None,
        "mesh_id": _identity_value(mesh_id) is not None,
        "spiffe_id": _identity_value(spiffe_id) is not None,
        "did": _identity_value(did) is not None,
        "wallet_address": _identity_value(wallet_address) is not None,
    }
    payload = {
        "component": "services.marketplace_events",
        "transition": transition,
        "operation": "marketplace_escrow_lifecycle",
        "service_name": source_alias,
        "source_alias": source_alias,
        "layer": _source_layer(source_alias),
        "escrow_id_hash": escrow_identity["escrow_id_hash"],
        "listing_id_hash": escrow_identity["listing_id_hash"],
        "renter_id_hash": escrow_identity["renter_id_hash"],
        "actor_id_hash": escrow_identity["actor_id_hash"],
        "currency": _identity_value(currency),
        "status": _identity_value(status),
        "node_id_hash": escrow_identity["node_id_hash"],
        "mesh_id_hash": escrow_identity["mesh_id_hash"],
        "spiffe_id_hash": escrow_identity["spiffe_id_hash"],
        "did_hash": escrow_identity["did_hash"],
        "wallet_address_hash": escrow_identity["wallet_address_hash"],
        "amount_cents": _json_value(amount_cents),
        "amount_token": _json_value(amount_token),
        "upstream_evidence": _upstream_evidence(
            upstream_event_ids,
            upstream_source_agents,
        ),
        "request_evidence": _request_evidence(request_evidence),
        "settlement_evidence": _settlement_evidence(settlement_evidence),
        "reason": reason_metadata["reason"],
        "reason_hash": reason_metadata["reason_hash"],
        "reason_redacted": reason_metadata["reason_redacted"],
        "identity": escrow_identity,
        "identity_fields_present": identity_fields_present,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    try:
        bus = event_bus or get_event_bus(project_root)
        event = bus.publish(event_type, source_agent, payload, priority=5)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish marketplace escrow event: %s", exc)
        return None
