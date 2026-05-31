"""Event trace helpers bound to registered service and API source agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.coordination.events import Event, EventBus, EventType
from src.services.service_identity_registry import KNOWN_EVENT_TRACE_SERVICES


EVENT_TRACE_CLAIM_BOUNDARY = (
    "Trace filters only bind EventBus source_agent values to registered service "
    "names and layers. They do not authenticate events, expose identity values, "
    "or prove live SPIRE/chain state."
)

REDACTED_EVENT_TRACE_FIELDS = frozenset(
    {
        "api_key",
        "api_token",
        "access_token",
        "actor_id",
        "refresh_token",
        "bot_token",
        "did",
        "escrow_id",
        "listing_id",
        "mesh_id",
        "node_id",
        "password",
        "private_key",
        "raw_vpn_uri",
        "reward_address",
        "renter_id",
        "secret",
        "subscription_link",
        "token",
        "uuid",
        "vpn_uri",
        "wallet_address",
        "spiffe_id",
    }
)
REDACTED_IDENTITY_VALUE = "[redacted]"
RUNTIME_EVIDENCE_TEXT_FIELDS = (
    "component",
    "operation",
    "service_name",
    "source_alias",
    "layer",
    "status",
    "result",
    "stage",
    "mode",
    "source_quality",
)
RUNTIME_EVIDENCE_BOOL_FIELDS = (
    "success",
    "simulated",
    "dataplane_confirmed",
    "mesh_dataplane_confirmed",
    "dpi_bypass_confirmed",
    "bypass_confirmed",
    "external_dpi_tested",
    "policy_required",
    "policy_allowed",
    "submitted_transaction",
    "safe_actuator",
    "safe_actuator_used",
    "post_action_dataplane_revalidated",
    "context_values_redacted",
    "context_payloads_redacted",
    "result_payload_redacted",
    "raw_identifiers_redacted",
    "payloads_redacted",
    "live_spire_svid_confirmed",
    "did_ownership_confirmed",
    "wallet_control_confirmed",
    "chain_identity_finality_confirmed",
    "live_provider_settlement_confirmed",
    "bank_settlement_confirmed",
    "chain_finality_confirmed",
)
RUNTIME_EVIDENCE_NUMERIC_FIELDS = (
    "duration_ms",
    "returncode",
    "return_code",
    "events_total",
    "attempts",
    "commands_total",
)
CLAIM_BOUNDARY_SUMMARY_LIMIT = 8
CROSS_PLANE_EVIDENCE_PROFILE_CLAIM_BOUNDARY = (
    "Cross-plane profile is derived from redacted evidence-summary metadata only. "
    "It classifies local evidence boundaries and does not authenticate events, "
    "prove production readiness, or expose raw payloads."
)
ECONOMY_FINALITY_CLAIM_BOUNDARY = (
    "Economy finality summary is derived from redacted evidence-summary metadata "
    "only. It separates local or pending economy evidence from provider, bank, "
    "token finality, dataplane, and production-readiness claims without copying "
    "raw commerce, wallet, transaction, node, or mesh identifiers."
)
DATAPLANE_CONFIRMATION_FIELDS = frozenset(
    {"dataplane_confirmed", "mesh_dataplane_confirmed"}
)
TRUST_CONFIRMATION_FIELDS = frozenset(
    {
        "trust_confirmed",
        "live_spire_svid_confirmed",
        "did_ownership_confirmed",
        "wallet_control_confirmed",
        "chain_identity_finality_confirmed",
    }
)
SETTLEMENT_CONFIRMATION_FIELDS = frozenset(
    {
        "settlement_confirmed",
        "live_provider_settlement_confirmed",
        "bank_settlement_confirmed",
        "chain_finality_confirmed",
    }
)
CONTROL_ALLOWED_FIELDS = frozenset(
    {"policy_allowed", "safe_actuator", "safe_actuator_used", "submitted_transaction"}
)
DATA_PLANE_LAYER_MARKERS = (
    "anti_censorship",
    "dataplane",
    "mesh",
    "network",
    "obfuscation",
    "proxy",
    "vpn",
    "yggdrasil",
)
CONTROL_PLANE_LAYER_MARKERS = (
    "control",
    "governance",
    "mapek",
    "policy",
    "safe_actuator",
)
ECONOMY_LAYER_MARKERS = (
    "billing",
    "commerce",
    "escrow",
    "marketplace",
    "payment",
    "reward",
    "settlement",
)


def _safe_trace_text(value: Any) -> Optional[str]:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text[:256] if text else None


def _safe_trace_bool(value: Any) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def _safe_trace_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _safe_trace_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return None


def _safe_bool_map(
    value: Any,
    *,
    allowed_keys: Optional[Set[str]] = None,
) -> Dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, bool)
        and (allowed_keys is None or str(key) in allowed_keys)
    }


def _safe_evidence_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _claim_boundary_values(value: Any) -> List[str]:
    if isinstance(value, dict):
        values: List[str] = []
        direct = _safe_trace_text(value.get("claim_boundary"))
        if direct:
            values.append(direct)
        claim_boundaries = value.get("claim_boundaries")
        if isinstance(claim_boundaries, list):
            for item in claim_boundaries:
                boundary = _safe_trace_text(item)
                if boundary:
                    values.append(boundary)
        for child in value.values():
            if isinstance(child, (dict, list, tuple)):
                values.extend(_claim_boundary_values(child))
        return values
    if isinstance(value, (list, tuple)):
        values: List[str] = []
        for child in value:
            values.extend(_claim_boundary_values(child))
        return values
    return []


def _claim_boundary_summary(value: Any) -> Dict[str, Any]:
    distinct = sorted(set(_claim_boundary_values(value)))
    return {
        "present": bool(distinct),
        "claim_boundaries": distinct[:CLAIM_BOUNDARY_SUMMARY_LIMIT],
        "claim_boundaries_total": len(distinct),
        "claim_boundaries_limit": CLAIM_BOUNDARY_SUMMARY_LIMIT,
        "claim_boundaries_truncated": len(distinct) > CLAIM_BOUNDARY_SUMMARY_LIMIT,
        "redacted": True,
    }


UPSTREAM_CLAIM_SUMMARY_LIST_LIMIT = 12


def _safe_trace_text_list(
    value: Any,
    *,
    limit: int = UPSTREAM_CLAIM_SUMMARY_LIST_LIMIT,
) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value[-limit:]:
        text = _safe_trace_text(item)
        if text:
            items.append(text)
    return items


def _upstream_claim_gate_summary(value: Any) -> Dict[str, Any]:
    gate = _safe_evidence_dict(value)
    return {
        "present": _safe_trace_bool(gate.get("present")) is True,
        "schema": _safe_trace_text(gate.get("schema")),
        "surface": _safe_trace_text(gate.get("surface")),
        "status": _safe_trace_text(gate.get("status")),
        "decision": _safe_trace_text(gate.get("decision")),
        "local_spine_lifecycle_claim_allowed": _safe_trace_bool(
            gate.get("local_spine_lifecycle_claim_allowed")
        ),
        "policy_decision_claim_allowed": _safe_trace_bool(
            gate.get("policy_decision_claim_allowed")
        ),
        "local_actuator_execution_claim_allowed": _safe_trace_bool(
            gate.get("local_actuator_execution_claim_allowed")
        ),
        "local_reward_adapter_record_claim_allowed": _safe_trace_bool(
            gate.get("local_reward_adapter_record_claim_allowed")
        ),
        "production_readiness_claim_allowed": _safe_trace_bool(
            gate.get("production_readiness_claim_allowed")
        ),
        "dataplane_delivery_claim_allowed": _safe_trace_bool(
            gate.get("dataplane_delivery_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": _safe_trace_bool(
            gate.get("traffic_delivery_claim_allowed")
        ),
        "customer_traffic_claim_allowed": _safe_trace_bool(
            gate.get("customer_traffic_claim_allowed")
        ),
        "external_dpi_bypass_claim_allowed": _safe_trace_bool(
            gate.get("external_dpi_bypass_claim_allowed")
        ),
        "external_settlement_finality_claim_allowed": _safe_trace_bool(
            gate.get("external_settlement_finality_claim_allowed")
        ),
        "blocked_claim_ids": _safe_trace_text_list(gate.get("blocked_claim_ids")),
        "payloads_redacted": _safe_trace_bool(gate.get("payloads_redacted")),
    }


def _upstream_cross_plane_claim_gate_summary(value: Any) -> Dict[str, Any]:
    gate = _safe_evidence_dict(value)
    return {
        "present": _safe_trace_bool(gate.get("present")) is True,
        "schema": _safe_trace_text(gate.get("schema")),
        "surface": _safe_trace_text(gate.get("surface")),
        "decision": _safe_trace_text(gate.get("decision")),
        "allowed": _safe_trace_bool(gate.get("allowed")),
        "requested_claim_ids": _safe_trace_text_list(gate.get("requested_claim_ids")),
        "blockers": _safe_trace_text_list(gate.get("blockers")),
        "payloads_redacted": _safe_trace_bool(gate.get("payloads_redacted")),
    }


def _upstream_evidence_summary(value: Any) -> Dict[str, Any]:
    evidence = _safe_evidence_dict(value)
    event_ids = evidence.get("event_ids")
    source_agents = evidence.get("source_agents")
    claim_gate_summary = _upstream_claim_gate_summary(
        evidence.get("claim_gate_summary")
    )
    cross_plane_claim_gate_summary = _upstream_cross_plane_claim_gate_summary(
        evidence.get("cross_plane_claim_gate_summary")
    )
    return {
        "present": bool(evidence),
        "source_agents": [
            _safe_trace_text(source_agent)
            for source_agent in source_agents
            if _safe_trace_text(source_agent)
        ] if isinstance(source_agents, list) else [],
        "events_total": _safe_trace_int(evidence.get("events_total")),
        "event_ids_count": len(event_ids) if isinstance(event_ids, list) else 0,
        "event_ids_limit": _safe_trace_int(evidence.get("event_ids_limit")),
        "event_ids_truncated": _safe_trace_bool(evidence.get("event_ids_truncated")),
        "claim_gate_summary": claim_gate_summary,
        "cross_plane_claim_gate_summary": cross_plane_claim_gate_summary,
        "upstream_claim_boundary_present": bool(
            claim_gate_summary["present"]
            or cross_plane_claim_gate_summary["present"]
        ),
        "payloads_redacted": _safe_trace_bool(evidence.get("payloads_redacted")),
    }


def _reward_claim_gate_summary(value: Any) -> Dict[str, Any]:
    gate = _safe_evidence_dict(value)
    return {
        "present": bool(gate),
        "decision": _safe_trace_text(gate.get("decision")),
        "local_reward_accounting_claim_allowed": _safe_trace_bool(
            gate.get("local_reward_accounting_claim_allowed")
        ),
        "pending_token_submission_claim_allowed": _safe_trace_bool(
            gate.get("pending_token_submission_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": _safe_trace_bool(
            gate.get("traffic_delivery_claim_allowed")
        ),
        "dataplane_delivery_claim_allowed": _safe_trace_bool(
            gate.get("dataplane_delivery_claim_allowed")
        ),
        "token_settlement_finality_claim_allowed": _safe_trace_bool(
            gate.get("token_settlement_finality_claim_allowed")
        ),
        "external_settlement_finality_claim_allowed": _safe_trace_bool(
            gate.get("external_settlement_finality_claim_allowed")
        ),
        "production_readiness_claim_allowed": _safe_trace_bool(
            gate.get("production_readiness_claim_allowed")
        ),
        "requires_upstream_dataplane_evidence_for_traffic_claim": _safe_trace_bool(
            gate.get("requires_upstream_dataplane_evidence_for_traffic_claim")
        ),
        "requires_chain_finality_evidence_for_settlement_claim": _safe_trace_bool(
            gate.get("requires_chain_finality_evidence_for_settlement_claim")
        ),
        "simulated": _safe_trace_bool(gate.get("simulated")),
        "raw_identifiers_redacted": _safe_trace_bool(gate.get("raw_identifiers_redacted")),
        "payloads_redacted": _safe_trace_bool(gate.get("payloads_redacted")),
    }


def _request_evidence_summary(value: Any) -> Dict[str, Any]:
    evidence = _safe_evidence_dict(value)
    return {
        "present": bool(evidence),
        "action": _safe_trace_text(evidence.get("action")),
        "route": _safe_trace_text(evidence.get("route")),
        "actor_role": _safe_trace_text(evidence.get("actor_role")),
        "request_scope_hash_present": bool(evidence.get("request_scope_hash")),
        "idempotency_key_present": _safe_trace_bool(
            evidence.get("idempotency_key_present")
        ),
        "idempotency_key_hash_present": bool(evidence.get("idempotency_key_hash")),
        "idempotency_cache_hit": _safe_trace_bool(
            evidence.get("idempotency_cache_hit")
        ),
        "db_write_ready": _safe_trace_bool(evidence.get("db_write_ready")),
        "listing_status": _safe_trace_text(evidence.get("listing_status")),
        "currency": _safe_trace_text(evidence.get("currency")),
        "hours": _safe_trace_int(evidence.get("hours")),
        "renter_matches_listing": _safe_trace_bool(
            evidence.get("renter_matches_listing")
        ),
        "admin_override": _safe_trace_bool(evidence.get("admin_override")),
        "service_identity_present": _safe_bool_map(
            evidence.get("service_identity_present"),
            allowed_keys={"spiffe_id", "did", "wallet_address"},
        ),
        "raw_identifiers_redacted": _safe_trace_bool(
            evidence.get("raw_identifiers_redacted")
        ),
        "payloads_redacted": _safe_trace_bool(evidence.get("payloads_redacted")),
    }


def _settlement_evidence_summary(value: Any) -> Dict[str, Any]:
    evidence = _safe_evidence_dict(value)
    bridge = _safe_evidence_dict(evidence.get("bridge_evidence"))
    db_write = _safe_evidence_dict(evidence.get("db_write_evidence"))
    output = _safe_evidence_dict(evidence.get("output_summary"))
    claim_gate = _safe_evidence_dict(evidence.get("claim_gate"))
    return {
        "present": bool(evidence),
        "decision_basis": _safe_trace_text(evidence.get("decision_basis")),
        "source_quality": _safe_trace_text(evidence.get("source_quality")),
        "settlement_action": _safe_trace_text(evidence.get("settlement_action")),
        "duration_ms": _safe_trace_float(evidence.get("duration_ms")),
        "dataplane_confirmed": _safe_trace_bool(evidence.get("dataplane_confirmed")),
        "provider": _safe_trace_text(evidence.get("provider")),
        "payment_status": _safe_trace_text(evidence.get("payment_status")),
        "live_provider_settlement_confirmed": _safe_trace_bool(
            evidence.get("live_provider_settlement_confirmed")
        ),
        "bank_settlement_confirmed": _safe_trace_bool(
            evidence.get("bank_settlement_confirmed")
        ),
        "chain_finality_confirmed": _safe_trace_bool(
            evidence.get("chain_finality_confirmed")
        ),
        "threshold_met": _safe_trace_bool(evidence.get("threshold_met")),
        "uptime_percent": _safe_trace_float(evidence.get("uptime_percent")),
        "uptime_threshold": _safe_trace_float(evidence.get("uptime_threshold")),
        "measurement_window_hours": _safe_trace_float(
            evidence.get("measurement_window_hours")
        ),
        "telemetry_evidence": _upstream_evidence_summary(
            evidence.get("telemetry_evidence")
        ),
        "bridge_evidence": {
            "present": bool(bridge),
            "attempted": _safe_trace_bool(bridge.get("attempted")),
            "status": _safe_trace_text(bridge.get("status")),
            "source_agent": _safe_trace_text(bridge.get("source_agent")),
            "payloads_redacted": _safe_trace_bool(bridge.get("payloads_redacted")),
        },
        "db_write_evidence": {
            "present": bool(db_write),
            "storage_backend": _safe_trace_text(db_write.get("storage_backend")),
            "attempted": _safe_trace_bool(db_write.get("attempted")),
            "committed": _safe_trace_bool(db_write.get("committed")),
            "payloads_redacted": _safe_trace_bool(db_write.get("payloads_redacted")),
        },
        "output_summary": {
            "present": bool(output),
            "escrow_status_after": _safe_trace_text(output.get("escrow_status_after")),
            "listing_status_after": _safe_trace_text(
                output.get("listing_status_after")
            ),
            "billing_stage": _safe_trace_text(output.get("billing_stage")),
            "invoice_status_after": _safe_trace_text(
                output.get("invoice_status_after")
            ),
            "plan_after": _safe_trace_text(output.get("plan_after")),
            "subscription_status": _safe_trace_text(output.get("subscription_status")),
            "checkout_url_present": _safe_trace_bool(
                output.get("checkout_url_present")
            ),
            "portal_url_present": _safe_trace_bool(output.get("portal_url_present")),
            "stripe_session_present": _safe_trace_bool(
                output.get("stripe_session_present")
            ),
            "raw_identifiers_redacted": _safe_trace_bool(
                output.get("raw_identifiers_redacted")
            ),
            "payloads_redacted": _safe_trace_bool(output.get("payloads_redacted")),
        },
        "claim_gate": {
            "present": bool(claim_gate),
            "decision": _safe_trace_text(claim_gate.get("decision")),
            "local_escrow_lifecycle_claim_allowed": _safe_trace_bool(
                claim_gate.get("local_escrow_lifecycle_claim_allowed")
            ),
            "traffic_delivery_claim_allowed": _safe_trace_bool(
                claim_gate.get("traffic_delivery_claim_allowed")
            ),
            "dataplane_delivery_claim_allowed": _safe_trace_bool(
                claim_gate.get("dataplane_delivery_claim_allowed")
            ),
            "external_settlement_finality_claim_allowed": _safe_trace_bool(
                claim_gate.get("external_settlement_finality_claim_allowed")
            ),
            "production_readiness_claim_allowed": _safe_trace_bool(
                claim_gate.get("production_readiness_claim_allowed")
            ),
            "requires_dataplane_evidence_for_delivery_claim": _safe_trace_bool(
                claim_gate.get("requires_dataplane_evidence_for_delivery_claim")
            ),
            "requires_external_finality_evidence_for_settlement_claim": (
                _safe_trace_bool(
                    claim_gate.get(
                        "requires_external_finality_evidence_for_settlement_claim"
                    )
                )
            ),
            "bridge_status": _safe_trace_text(claim_gate.get("bridge_status")),
            "raw_identifiers_redacted": _safe_trace_bool(
                claim_gate.get("raw_identifiers_redacted")
            ),
            "payloads_redacted": _safe_trace_bool(claim_gate.get("payloads_redacted")),
        },
    }


def _post_action_dataplane_revalidation_summary(value: Any) -> Dict[str, Any]:
    revalidation = _safe_evidence_dict(value)
    evidence = _safe_evidence_dict(revalidation.get("evidence"))
    claim_gate = _safe_evidence_dict(revalidation.get("claim_gate"))
    observed = _safe_evidence_dict(claim_gate.get("observed_evidence"))
    blockers = claim_gate.get("blockers")
    if not isinstance(blockers, list):
        blockers = []
    source_agents = evidence.get("source_agents")
    event_ids = evidence.get("event_ids")
    return {
        "present": bool(revalidation),
        "post_action_dataplane_revalidated": _safe_trace_bool(
            revalidation.get("post_action_dataplane_revalidated")
        ),
        "dataplane_confirmed": _safe_trace_bool(
            revalidation.get("dataplane_confirmed")
        ),
        "probe_attempted": _safe_trace_bool(revalidation.get("probe_attempted")),
        "restored_dataplane_claim_allowed": _safe_trace_bool(
            revalidation.get("restored_dataplane_claim_allowed")
        ),
        "claim_gate": {
            "present": bool(claim_gate),
            "restored_dataplane_claim_allowed": _safe_trace_bool(
                claim_gate.get("restored_dataplane_claim_allowed")
            ),
            "blockers": [
                _safe_trace_text(blocker)
                for blocker in blockers
                if _safe_trace_text(blocker)
            ],
            "post_action_probe_attempted": _safe_trace_bool(
                claim_gate.get("post_action_probe_attempted")
            ),
            "observed_probe_attempted": _safe_trace_bool(
                observed.get("probe_attempted")
            ),
            "observed_dataplane_confirmed": _safe_trace_bool(
                observed.get("dataplane_confirmed")
            ),
            "claim_boundary_present": bool(claim_gate.get("claim_boundary")),
            "redacted": _safe_trace_bool(claim_gate.get("redacted")),
        },
        "evidence": {
            "present": bool(evidence),
            "event_ids_count": _safe_trace_int(evidence.get("event_ids_count"))
            or (len(event_ids) if isinstance(event_ids, list) else 0),
            "events_total": _safe_trace_int(evidence.get("events_total")),
            "source_agents_count": len(source_agents)
            if isinstance(source_agents, list)
            else 0,
            "redacted": _safe_trace_bool(evidence.get("redacted")),
        },
        "claim_boundary_present": bool(
            revalidation.get("claim_boundary") or claim_gate.get("claim_boundary")
        ),
        "redacted": _safe_trace_bool(revalidation.get("redacted")),
    }


def _identity_evidence_summary(data: Any) -> Dict[str, Any]:
    payload = _safe_evidence_dict(data)
    identity = _safe_evidence_dict(payload.get("identity"))
    identity_fields_present = _safe_bool_map(payload.get("identity_fields_present"))
    return {
        "present": bool(identity or identity_fields_present),
        "hash_fields": sorted(
            str(key)
            for key, value in identity.items()
            if str(key).endswith("_hash") and value is not None
        ),
        "identity_fields_present": identity_fields_present,
        "raw_identifiers_redacted": _safe_trace_bool(
            payload.get("raw_identifiers_redacted")
        ),
    }


def _runtime_evidence_summary(data: Any) -> Dict[str, Any]:
    payload = _safe_evidence_dict(data)
    text_fields = {
        key: value
        for key in RUNTIME_EVIDENCE_TEXT_FIELDS
        if (value := _safe_trace_text(payload.get(key))) is not None
    }
    bool_fields = {
        key: value
        for key in RUNTIME_EVIDENCE_BOOL_FIELDS
        if (value := _safe_trace_bool(payload.get(key))) is not None
    }
    numeric_fields = {
        key: value
        for key in RUNTIME_EVIDENCE_NUMERIC_FIELDS
        if (value := _safe_trace_float(payload.get(key))) is not None
    }
    evidence_blocks_present = sorted(
        str(key)
        for key, value in payload.items()
        if str(key).endswith("_evidence") and isinstance(value, dict) and bool(value)
    )
    claim_boundary = _safe_trace_text(payload.get("claim_boundary"))
    claim_boundary_summary = _claim_boundary_summary(payload)
    return {
        "present": bool(
            text_fields
            or bool_fields
            or numeric_fields
            or evidence_blocks_present
            or claim_boundary
            or claim_boundary_summary["present"]
        ),
        "text_fields": text_fields,
        "bool_fields": bool_fields,
        "numeric_fields": numeric_fields,
        "evidence_blocks_present": evidence_blocks_present,
        "claim_boundary_present": claim_boundary is not None,
        "claim_boundaries_present": claim_boundary_summary["present"],
    }


def _any_true(value: Dict[str, Any], keys: Set[str] | frozenset[str]) -> bool:
    return any(value.get(key) is True for key in keys)


def _text_contains_any(value: Any, markers: tuple[str, ...]) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower()
    return any(marker in normalized for marker in markers)


def _runtime_plane_markers(runtime: Dict[str, Any]) -> Dict[str, bool]:
    text_fields = _safe_evidence_dict(runtime.get("text_fields"))
    observed_text = " ".join(
        str(value)
        for key, value in text_fields.items()
        if key in {"component", "operation", "service_name", "source_alias", "layer"}
        and value is not None
    )
    bool_fields = _safe_evidence_dict(runtime.get("bool_fields"))

    return {
        "data_plane": _text_contains_any(observed_text, DATA_PLANE_LAYER_MARKERS),
        "control_plane": (
            _text_contains_any(observed_text, CONTROL_PLANE_LAYER_MARKERS)
            or "policy_allowed" in bool_fields
            or "policy_required" in bool_fields
            or bool_fields.get("safe_actuator") is True
            or bool_fields.get("safe_actuator_used") is True
        ),
        "economy_plane": _text_contains_any(observed_text, ECONOMY_LAYER_MARKERS),
    }


def cross_plane_evidence_profile(summary: Any) -> Dict[str, Any]:
    """Classify redacted evidence-summary metadata without copying raw payloads."""
    evidence = _safe_evidence_dict(summary)
    runtime = _safe_evidence_dict(evidence.get("runtime_evidence"))
    request = _safe_evidence_dict(evidence.get("request_evidence"))
    upstream = _safe_evidence_dict(evidence.get("upstream_evidence"))
    settlement = _safe_evidence_dict(evidence.get("settlement_evidence"))
    post_action_dataplane = _safe_evidence_dict(
        evidence.get("post_action_dataplane_revalidation")
    )
    reward_claim_gate = _safe_evidence_dict(evidence.get("reward_claim_gate"))
    identity = _safe_evidence_dict(evidence.get("identity_evidence"))
    bool_fields = _safe_evidence_dict(runtime.get("bool_fields"))
    plane_markers = _runtime_plane_markers(runtime)

    raw_dataplane_confirmed = (
        _any_true(bool_fields, DATAPLANE_CONFIRMATION_FIELDS)
        or settlement.get("dataplane_confirmed") is True
    )
    post_action_gate = _safe_evidence_dict(post_action_dataplane.get("claim_gate"))
    post_action_gate_allows_dataplane = bool(
        post_action_dataplane.get("present") is True
        and post_action_dataplane.get("post_action_dataplane_revalidated") is True
        and post_action_dataplane.get("dataplane_confirmed") is True
        and post_action_gate.get("restored_dataplane_claim_allowed") is True
    )
    dataplane_confirmed = bool(
        raw_dataplane_confirmed
        and (
            post_action_dataplane.get("present") is not True
            or post_action_gate_allows_dataplane
        )
    )
    dataplane_claim_blockers: List[str] = []
    if raw_dataplane_confirmed and post_action_dataplane.get("present") is True:
        if not post_action_gate_allows_dataplane:
            dataplane_claim_blockers.append("post_action_dataplane_claim_gate_not_allowed")
        gate_blockers = post_action_gate.get("blockers")
        if isinstance(gate_blockers, list):
            dataplane_claim_blockers.extend(
                str(blocker) for blocker in gate_blockers if blocker
            )
    trust_metadata_present = bool(
        identity.get("present")
        or request.get("service_identity_present")
        or bool_fields.get("service_identity_present") is True
    )
    trust_confirmed = _any_true(bool_fields, TRUST_CONFIRMATION_FIELDS)
    settlement_confirmed = (
        _any_true(bool_fields, SETTLEMENT_CONFIRMATION_FIELDS)
        or _any_true(settlement, SETTLEMENT_CONFIRMATION_FIELDS)
    )
    control_allowed = _any_true(bool_fields, CONTROL_ALLOWED_FIELDS)
    control_blocked = bool_fields.get("policy_allowed") is False
    external_dpi_tested = bool_fields.get("external_dpi_tested") is True
    dpi_bypass_confirmed = (
        (
            bool_fields.get("dpi_bypass_confirmed") is True
            or bool_fields.get("bypass_confirmed") is True
        )
        and external_dpi_tested
    )
    economy_evidence_present = (
        bool(settlement.get("present"))
        or bool(reward_claim_gate.get("present"))
        or plane_markers["economy_plane"]
        or request.get("action") in {"rent_node", "pay_invoice"}
    )
    production_ready_candidate = bool(
        dataplane_confirmed
        and trust_confirmed
        and (not economy_evidence_present or settlement_confirmed)
        and not control_blocked
    )
    evidence_available = bool(evidence.get("available"))
    local_only = bool(
        evidence_available
        and not dataplane_confirmed
        and not trust_confirmed
        and not settlement_confirmed
        and not dpi_bypass_confirmed
        and not production_ready_candidate
    )

    if production_ready_candidate:
        primary_status = "production_ready_candidate"
    elif settlement_confirmed:
        primary_status = "settlement_confirmed"
    elif dataplane_confirmed:
        primary_status = "dataplane_confirmed"
    elif trust_confirmed:
        primary_status = "trust_confirmed"
    elif control_allowed:
        primary_status = "control_allowed"
    elif local_only:
        primary_status = "local_only"
    else:
        primary_status = "no_evidence"

    planes_observed = [
        plane
        for plane, present in {
            "data_plane": plane_markers["data_plane"] or dataplane_confirmed,
            "control_plane": plane_markers["control_plane"] or control_allowed,
            "trust_plane": trust_metadata_present or trust_confirmed,
            "evidence_plane": evidence_available,
            "economy_plane": economy_evidence_present or settlement_confirmed,
        }.items()
        if present
    ]

    return {
        "claim_boundary": CROSS_PLANE_EVIDENCE_PROFILE_CLAIM_BOUNDARY,
        "primary_status": primary_status,
        "planes_observed": planes_observed,
        "local_only": local_only,
        "control_allowed": control_allowed,
        "control_blocked": control_blocked,
        "dataplane_confirmed": dataplane_confirmed,
        "raw_dataplane_confirmed": raw_dataplane_confirmed,
        "dataplane_claim_gate_required": post_action_dataplane.get("present") is True,
        "dataplane_claim_gate_allowed": (
            post_action_gate_allows_dataplane
            if post_action_dataplane.get("present") is True
            else None
        ),
        "dataplane_claim_blockers": dataplane_claim_blockers,
        "trust_metadata_present": trust_metadata_present,
        "trust_confirmed": trust_confirmed,
        "settlement_confirmed": settlement_confirmed,
        "economy_evidence_present": economy_evidence_present,
        "external_dpi_tested": external_dpi_tested,
        "dpi_bypass_confirmed": dpi_bypass_confirmed,
        "production_ready_candidate": production_ready_candidate,
        "claim_boundary_present": bool(
            evidence.get("claim_boundary")
            or runtime.get("claim_boundary_present") is True
            or _safe_evidence_dict(evidence.get("claim_boundary_summary")).get(
                "present"
            )
            is True
        ),
    }


def _economy_high_risk_claim_gate(
    *,
    economy_evidence_present: bool,
    local_or_pending_only: bool,
    payment_provider_settlement_confirmed: bool,
    bank_settlement_confirmed: bool,
    token_settlement_finality_confirmed: bool,
    external_finality_confirmed: bool,
    dataplane_confirmed: bool,
    production_ready_candidate: bool,
    claim_gate: Dict[str, Any],
    reward_claim_gate: Dict[str, Any],
) -> Dict[str, Any]:
    dataplane_delivery_allowed = bool(
        dataplane_confirmed
        and (
            claim_gate.get("dataplane_delivery_claim_allowed") is True
            or claim_gate.get("customer_dataplane_delivery_claim_allowed") is True
        )
    )
    traffic_delivery_allowed = bool(
        dataplane_confirmed
        and (
            claim_gate.get("traffic_delivery_claim_allowed") is True
            or reward_claim_gate.get("traffic_delivery_claim_allowed") is True
        )
    )
    external_settlement_allowed = bool(
        external_finality_confirmed
        and (
            payment_provider_settlement_confirmed
            or bank_settlement_confirmed
            or token_settlement_finality_confirmed
            or claim_gate.get("external_settlement_finality_claim_allowed") is True
            or reward_claim_gate.get("token_settlement_finality_claim_allowed") is True
        )
    )
    production_allowed = bool(
        production_ready_candidate
        and dataplane_delivery_allowed
        and external_settlement_allowed
        and (
            claim_gate.get("production_readiness_claim_allowed") is True
            or reward_claim_gate.get("production_readiness_claim_allowed") is True
        )
    )

    blockers: List[str] = []
    if economy_evidence_present and not external_finality_confirmed:
        blockers.append("external_settlement_finality_missing")
    if not dataplane_confirmed:
        blockers.append("dataplane_confirmation_missing")
    if dataplane_confirmed and not dataplane_delivery_allowed:
        blockers.append("dataplane_delivery_claim_gate_missing")
    if dataplane_confirmed and not traffic_delivery_allowed:
        blockers.append("traffic_delivery_claim_gate_missing")
    if not production_ready_candidate:
        blockers.append("production_readiness_cross_plane_missing")
    if production_ready_candidate and not production_allowed:
        blockers.append("production_readiness_claim_gate_missing")

    return {
        "present": economy_evidence_present,
        "local_or_pending_economy_claim_allowed": local_or_pending_only,
        "payment_provider_settlement_claim_allowed": (
            payment_provider_settlement_confirmed
        ),
        "bank_settlement_claim_allowed": bank_settlement_confirmed,
        "token_settlement_finality_claim_allowed": (
            token_settlement_finality_confirmed
        ),
        "external_settlement_finality_claim_allowed": external_settlement_allowed,
        "dataplane_delivery_claim_allowed": dataplane_delivery_allowed,
        "traffic_delivery_claim_allowed": traffic_delivery_allowed,
        "production_readiness_claim_allowed": production_allowed,
        "blockers": blockers,
        "required_for_high_risk_claims": {
            "settlement_finality": "provider, bank, chain, or reward finality evidence",
            "dataplane_delivery": "dataplane confirmation plus delivery claim gate",
            "traffic_delivery": "dataplane confirmation plus traffic claim gate",
            "production_readiness": "production candidate plus dataplane and external finality gates",
        },
        "claim_boundary": ECONOMY_FINALITY_CLAIM_BOUNDARY,
        "redacted": True,
    }


def economy_finality_summary(summary: Any) -> Dict[str, Any]:
    """Separate local economy evidence from external settlement/finality proof."""
    evidence = _safe_evidence_dict(summary)
    runtime = _safe_evidence_dict(evidence.get("runtime_evidence"))
    bool_fields = _safe_evidence_dict(runtime.get("bool_fields"))
    request = _safe_evidence_dict(evidence.get("request_evidence"))
    upstream = _safe_evidence_dict(evidence.get("upstream_evidence"))
    upstream_claim_gate = _safe_evidence_dict(upstream.get("claim_gate_summary"))
    upstream_cross_plane_claim_gate = _safe_evidence_dict(
        upstream.get("cross_plane_claim_gate_summary")
    )
    settlement = _safe_evidence_dict(evidence.get("settlement_evidence"))
    claim_gate = _safe_evidence_dict(settlement.get("claim_gate"))
    reward_claim_gate = _safe_evidence_dict(evidence.get("reward_claim_gate"))
    profile = _safe_evidence_dict(evidence.get("cross_plane_evidence_profile"))

    payment_provider_settlement_confirmed = (
        settlement.get("live_provider_settlement_confirmed") is True
        or bool_fields.get("live_provider_settlement_confirmed") is True
    )
    bank_settlement_confirmed = (
        settlement.get("bank_settlement_confirmed") is True
        or bool_fields.get("bank_settlement_confirmed") is True
    )
    token_settlement_finality_confirmed = (
        settlement.get("chain_finality_confirmed") is True
        or bool_fields.get("chain_finality_confirmed") is True
    )
    submitted_transaction = bool_fields.get("submitted_transaction") is True
    external_finality_confirmed = (
        payment_provider_settlement_confirmed
        or bank_settlement_confirmed
        or token_settlement_finality_confirmed
    )
    economy_evidence_present = bool(
        profile.get("economy_evidence_present") is True
        or settlement.get("present") is True
        or reward_claim_gate.get("present") is True
        or request.get("action") in {"rent_node", "pay_invoice"}
        or submitted_transaction
        or external_finality_confirmed
    )
    local_or_pending_only = bool(
        economy_evidence_present and not external_finality_confirmed
    )
    dataplane_confirmed = profile.get("dataplane_confirmed") is True
    production_ready_candidate = profile.get("production_ready_candidate") is True
    high_risk_claim_gate = _economy_high_risk_claim_gate(
        economy_evidence_present=economy_evidence_present,
        local_or_pending_only=local_or_pending_only,
        payment_provider_settlement_confirmed=payment_provider_settlement_confirmed,
        bank_settlement_confirmed=bank_settlement_confirmed,
        token_settlement_finality_confirmed=token_settlement_finality_confirmed,
        external_finality_confirmed=external_finality_confirmed,
        dataplane_confirmed=dataplane_confirmed,
        production_ready_candidate=production_ready_candidate,
        claim_gate=claim_gate,
        reward_claim_gate=reward_claim_gate,
    )

    return {
        "claim_boundary": ECONOMY_FINALITY_CLAIM_BOUNDARY,
        "present": economy_evidence_present,
        "local_or_pending_only": local_or_pending_only,
        "submitted_transaction_only": bool(
            submitted_transaction and not token_settlement_finality_confirmed
        ),
        "payment_provider_settlement_confirmed": (
            payment_provider_settlement_confirmed
        ),
        "bank_settlement_confirmed": bank_settlement_confirmed,
        "token_settlement_finality_confirmed": (
            token_settlement_finality_confirmed
        ),
        "settlement_confirmed": profile.get("settlement_confirmed") is True,
        "dataplane_confirmed": dataplane_confirmed,
        "production_ready_candidate": production_ready_candidate,
        "payment_status": settlement.get("payment_status"),
        "provider": settlement.get("provider"),
        "settlement_action": settlement.get("settlement_action"),
        "source_quality": settlement.get("source_quality")
        or _safe_evidence_dict(runtime.get("text_fields")).get("source_quality"),
        "telemetry_linked": (
            _safe_evidence_dict(settlement.get("telemetry_evidence")).get("present")
            is True
        ),
        "claim_gate": {
            "present": bool(claim_gate),
            "decision": claim_gate.get("decision"),
            "local_escrow_lifecycle_claim_allowed": (
                claim_gate.get("local_escrow_lifecycle_claim_allowed") is True
            ),
            "traffic_delivery_claim_allowed": (
                claim_gate.get("traffic_delivery_claim_allowed") is True
            ),
            "external_settlement_finality_claim_allowed": (
                claim_gate.get("external_settlement_finality_claim_allowed") is True
            ),
            "production_readiness_claim_allowed": (
                claim_gate.get("production_readiness_claim_allowed") is True
            ),
        },
        "reward_claim_gate": {
            "present": bool(reward_claim_gate),
            "decision": reward_claim_gate.get("decision"),
            "local_reward_accounting_claim_allowed": (
                reward_claim_gate.get("local_reward_accounting_claim_allowed") is True
            ),
            "pending_token_submission_claim_allowed": (
                reward_claim_gate.get("pending_token_submission_claim_allowed") is True
            ),
            "traffic_delivery_claim_allowed": (
                reward_claim_gate.get("traffic_delivery_claim_allowed") is True
            ),
            "token_settlement_finality_claim_allowed": (
                reward_claim_gate.get("token_settlement_finality_claim_allowed") is True
            ),
            "production_readiness_claim_allowed": (
                reward_claim_gate.get("production_readiness_claim_allowed") is True
            ),
        },
        "high_risk_claim_gate": high_risk_claim_gate,
        "upstream_events_total": upstream.get("events_total"),
        "upstream_event_ids_count": upstream.get("event_ids_count"),
        "upstream_claim_boundary_present": (
            upstream.get("upstream_claim_boundary_present") is True
        ),
        "upstream_claim_gate": {
            "present": upstream_claim_gate.get("present") is True,
            "surface": upstream_claim_gate.get("surface"),
            "local_actuator_execution_claim_allowed": (
                upstream_claim_gate.get("local_actuator_execution_claim_allowed")
                is True
            ),
            "external_settlement_finality_claim_allowed": (
                upstream_claim_gate.get("external_settlement_finality_claim_allowed")
                is True
            ),
            "production_readiness_claim_allowed": (
                upstream_claim_gate.get("production_readiness_claim_allowed") is True
            ),
            "payloads_redacted": upstream_claim_gate.get("payloads_redacted") is True,
        },
        "upstream_cross_plane_claim_gate": {
            "present": upstream_cross_plane_claim_gate.get("present") is True,
            "surface": upstream_cross_plane_claim_gate.get("surface"),
            "decision": upstream_cross_plane_claim_gate.get("decision"),
            "allowed": upstream_cross_plane_claim_gate.get("allowed") is True,
            "payloads_redacted": (
                upstream_cross_plane_claim_gate.get("payloads_redacted") is True
            ),
        },
    }


def event_trace_evidence_summary(data: Any) -> Dict[str, Any]:
    """Summarize redacted evidence metadata without copying raw evidence payloads."""
    payload = _safe_evidence_dict(data)
    request = _request_evidence_summary(payload.get("request_evidence"))
    upstream = _upstream_evidence_summary(payload.get("upstream_evidence"))
    settlement = _settlement_evidence_summary(payload.get("settlement_evidence"))
    post_action_dataplane = _post_action_dataplane_revalidation_summary(
        payload.get("post_action_dataplane_revalidation")
    )
    reward_claim_gate = _reward_claim_gate_summary(payload.get("reward_claim_gate"))
    identity = _identity_evidence_summary(payload)
    runtime = _runtime_evidence_summary(payload)
    claim_boundary_summary = _claim_boundary_summary(payload)
    summary = {
        "available": any(
            item["present"]
            for item in (
                request,
                upstream,
                settlement,
                post_action_dataplane,
                reward_claim_gate,
                identity,
                runtime,
            )
        ),
        "claim_boundary": _safe_trace_text(payload.get("claim_boundary")),
        "claim_boundary_summary": claim_boundary_summary,
        "runtime_evidence": runtime,
        "request_evidence": request,
        "upstream_evidence": upstream,
        "settlement_evidence": settlement,
        "post_action_dataplane_revalidation": post_action_dataplane,
        "reward_claim_gate": reward_claim_gate,
        "identity_evidence": identity,
    }
    summary["cross_plane_evidence_profile"] = cross_plane_evidence_profile(summary)
    summary["economy_finality_summary"] = economy_finality_summary(summary)
    return summary


def _matching_registrations(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> List[Dict[str, str]]:
    return [
        dict(registration)
        for registration in KNOWN_EVENT_TRACE_SERVICES
        if (service_name is None or registration["service_name"] == service_name)
        and (layer is None or registration["layer"] == layer)
    ]


def _registration_source_agent(registration: Dict[str, str]) -> str:
    return registration.get("source_agent") or registration["service_name"]


def service_event_trace_filter(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> Dict[str, object]:
    """Return a redacted EventBus trace filter for registered services."""
    services = _matching_registrations(service_name=service_name, layer=layer)
    known_service_names = {
        registration["service_name"]
        for registration in KNOWN_EVENT_TRACE_SERVICES
    }
    known_layers = {
        registration["layer"]
        for registration in KNOWN_EVENT_TRACE_SERVICES
    }

    unknown_service = (
        service_name is not None and service_name not in known_service_names
    )
    unknown_layer = layer is not None and layer not in known_layers
    status = "ok"
    if unknown_service or unknown_layer:
        status = "unknown_filter"
    elif (service_name is not None or layer is not None) and not services:
        status = "no_match"

    return {
        "status": status,
        "claim_boundary": EVENT_TRACE_CLAIM_BOUNDARY,
        "redacted": True,
        "service_name": service_name,
        "layer": layer,
        "source_agents": sorted(
            _registration_source_agent(service) for service in services
        ),
        "services_total": len(services),
        "registered_services_total": len(KNOWN_EVENT_TRACE_SERVICES),
        "known_layers": sorted(known_layers),
        "services": services,
    }


def _source_agents_for_filter(
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
) -> Optional[Set[str]]:
    if service_name is None and layer is None:
        return None
    trace_filter = service_event_trace_filter(
        service_name=service_name,
        layer=layer,
    )
    return set(trace_filter["source_agents"])


def get_service_event_history(
    bus: EventBus,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> List[Event]:
    """Read EventBus history through registered service/layer filters."""
    source_agents = _source_agents_for_filter(service_name=service_name, layer=layer)
    if source_agents == set():
        return []
    return bus.get_event_history(
        event_type=event_type,
        since=since,
        limit=limit,
        source_agents=source_agents,
    )


def get_service_event_replay(
    bus: EventBus,
    agent_id: str,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    since: Optional[datetime] = None,
) -> List[Event]:
    """Replay events through registered service/layer filters."""
    source_agents = _source_agents_for_filter(service_name=service_name, layer=layer)
    if source_agents == set():
        return []
    return bus.replay_events(agent_id, since=since, source_agents=source_agents)


def _redact_identity_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in REDACTED_EVENT_TRACE_FIELDS and child is not None:
                redacted[key_text] = (
                    child if isinstance(child, bool) else REDACTED_IDENTITY_VALUE
                )
            else:
                redacted[key_text] = _redact_identity_values(child)
        return redacted

    if isinstance(value, list):
        return [_redact_identity_values(item) for item in value]

    if isinstance(value, tuple):
        return [_redact_identity_values(item) for item in value]

    return value


def serialize_service_event_trace(event: Event) -> Dict[str, object]:
    """Serialize an EventBus event without exposing identity values."""
    redacted_data = _redact_identity_values(event.data)
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "source_agent": event.source_agent,
        "timestamp": event.timestamp.isoformat(),
        "target_agents": sorted(event.target_agents) if event.target_agents else None,
        "priority": event.priority,
        "requires_ack": event.requires_ack,
        "acked_by": sorted(event.acked_by),
        "data": redacted_data,
        "evidence_summary": event_trace_evidence_summary(redacted_data),
        "redacted": True,
    }


def service_event_trace_history(
    bus: EventBus,
    *,
    service_name: Optional[str] = None,
    layer: Optional[str] = None,
    event_type: Optional[EventType] = None,
    replay_agent: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> Dict[str, object]:
    """Return redacted EventBus traces through registered service/layer filters."""
    trace_filter = service_event_trace_filter(
        service_name=service_name,
        layer=layer,
    )
    bounded_limit = max(1, min(limit, 1000))

    if trace_filter["status"] == "unknown_filter":
        events: List[Event] = []
    elif replay_agent:
        events = get_service_event_replay(
            bus,
            replay_agent,
            service_name=service_name,
            layer=layer,
            since=since,
        )
        if event_type:
            events = [event for event in events if event.event_type == event_type]
        events = events[-bounded_limit:]
    else:
        events = get_service_event_history(
            bus,
            service_name=service_name,
            layer=layer,
            event_type=event_type,
            since=since,
            limit=bounded_limit,
        )

    return {
        "status": trace_filter["status"],
        "claim_boundary": EVENT_TRACE_CLAIM_BOUNDARY,
        "redacted": True,
        "filter": trace_filter,
        "replay_agent": replay_agent,
        "event_type": event_type.value if event_type else None,
        "limit": bounded_limit,
        "events_total": len(events),
        "events": [serialize_service_event_trace(event) for event in events],
    }
