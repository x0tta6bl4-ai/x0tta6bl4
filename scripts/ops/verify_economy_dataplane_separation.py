#!/usr/bin/env python3
"""Verify local economy evidence cannot promote dataplane or production claims.

This verifier is intentionally local-only. It builds representative operator
handoff reports and EventBus economy events, then checks that economy finality,
pending token submission, and local escrow/accounting signals stay separated
from dataplane delivery, customer traffic, revenue recognition, and production
readiness claims.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.coordination.events import EventBus, EventType
from src.api.maas.auth import UserContext
from src.api.maas.billing_helpers import compute_hmac_signature
from src.api.maas.endpoints import billing as modular_billing
from src.integration.external_settlement_operator_handoff import (
    build_report as build_external_settlement_handoff_report,
)
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.reward_events import publish_reward_settlement_event
from src.services.service_event_trace import event_trace_evidence_summary


SCHEMA = "x0tta6bl4.economy_dataplane_separation.v1"
DECISION_VERIFIED = "ECONOMY_DATAPLANE_SEPARATION_VERIFIED"
DECISION_GAPS = "ECONOMY_DATAPLANE_SEPARATION_GAPS"
CLAIM_BOUNDARY = (
    "Economy/dataplane separation verifier is a local simulated report and "
    "EventBus smoke test only. It proves representative local economy surfaces "
    "keep high-risk claims fail-closed; it does not prove dataplane delivery, "
    "customer traffic, external settlement finality, bank settlement, revenue "
    "recognition, production SLOs, or production readiness."
)

OPERATOR_ENTRYPOINTS = (
    "src/integration/external_settlement.py",
    "scripts/ops/verify_x0t_external_settlement_evidence.py",
    "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
    "scripts/ops/run_integration_spine_production_input_pipeline.py",
    "scripts/ops/run_integration_spine_completion_gate.py",
)

HANDOFF_STRONG_FALSE_KEYS = (
    "dataplane_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "customer_dataplane_delivery_claim_allowed",
    "bank_settlement_claim_allowed",
    "revenue_recognition_claim_allowed",
    "production_slo_claim_allowed",
    "production_readiness_claim_allowed",
    "mutates_chain",
    "runs_live_rpc",
    "submits_transaction",
)

REWARD_STRONG_FALSE_KEYS = (
    "traffic_delivery_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "token_settlement_finality_claim_allowed",
    "external_settlement_finality_claim_allowed",
    "economy_finality_claim_allowed",
    "bank_settlement_claim_allowed",
    "revenue_recognition_claim_allowed",
    "production_readiness_claim_allowed",
)

MARKETPLACE_STRONG_FALSE_KEYS = (
    "traffic_delivery_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "external_settlement_finality_claim_allowed",
    "economy_finality_claim_allowed",
    "bank_settlement_claim_allowed",
    "revenue_recognition_claim_allowed",
    "production_readiness_claim_allowed",
)

MODULAR_BILLING_STRONG_FALSE_KEYS = (
    "payment_provider_settlement_claim_allowed",
    "bank_settlement_claim_allowed",
    "external_settlement_finality_claim_allowed",
    "serviceability_claim_allowed",
    "paid_customer_serviceability_claim_allowed",
    "customer_access_claim_allowed",
    "vpn_access_claim_allowed",
    "node_provisioning_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "customer_dataplane_delivery_claim_allowed",
    "traffic_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "revenue_recognition_claim_allowed",
    "production_slo_claim_allowed",
    "production_readiness_claim_allowed",
)

ECONOMY_HIGH_RISK_FALSE_KEYS = (
    "external_settlement_finality_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "traffic_delivery_claim_allowed",
    "production_readiness_claim_allowed",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _write_json(root: Path, relative: str, payload: Mapping[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_operator_entrypoints(root: Path) -> None:
    for relative in OPERATOR_ENTRYPOINTS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# local verifier entrypoint placeholder\n", encoding="utf-8")


def _write_external_settlement_sources(root: Path, *, ready: bool) -> None:
    _write_operator_entrypoints(root)
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-capture-preflight-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
            "summary": {
                "capture_inputs_ready": ready,
                "errors_total": 0 if ready else 1,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-evidence-gate-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "x0t_external_settlement_decision": (
                "READY" if ready else "BLOCKED_ON_EVIDENCE"
            ),
            "summary": {
                "evidence_file_found": ready,
                "evidence_file_valid": ready,
                "x0t_external_settlement_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-live-rpc-gate-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "x0t_external_settlement_live_rpc_decision": (
                "READY" if ready else "BLOCKED_ON_EVIDENCE"
            ),
            "summary": {
                "evidence_file_found": ready,
                "retained_evidence_ready": ready,
                "live_rpc_checked": ready,
                "x0t_external_settlement_live_rpc_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-current-blocker-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_PROMOTE"
            if ready
            else "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
            "summary": {
                "expected_evidence_file_exists": ready,
                "live_rpc_ready": ready,
                "x0t_external_settlement_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-import-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-evidence-import-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {"production_evidence_complete": ready},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json",
        {
            "schema_version": (
                "x0tta6bl4-integration-spine-completion-gate-runner-v4-repo-generated"
            ),
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "summary": {
                "external_settlement_ready": ready,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )


def _validate_false_keys(
    payload: Mapping[str, Any],
    *,
    keys: Sequence[str],
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}:{key}_not_false:{payload.get(key)!r}"
        for key in keys
        if payload.get(key) is not False
    ]


def validate_external_handoff_report(
    report: Mapping[str, Any],
    *,
    expected_finality_allowed: bool,
    case_id: str,
) -> list[str]:
    failures: list[str] = []
    claim_gate = _mapping(report.get("claim_gate"))
    summary = _mapping(report.get("summary"))
    if report.get("ok") is not True:
        failures.append(f"{case_id}:handoff_report_not_ok")
    if not claim_gate:
        failures.append(f"{case_id}:claim_gate_missing")
        return failures
    if (
        claim_gate.get("schema")
        != "x0tta6bl4.external_settlement.operator_handoff.claim_gate.v1"
    ):
        failures.append(f"{case_id}:claim_gate_schema_invalid")
    for key in (
        "external_settlement_finality_claim_allowed",
        "economy_finality_claim_allowed",
    ):
        if claim_gate.get(key) is not expected_finality_allowed:
            failures.append(
                f"{case_id}:{key}_unexpected:{claim_gate.get(key)!r}"
            )
    for key in ("retained_evidence_claim_allowed", "live_rpc_receipt_claim_allowed"):
        if claim_gate.get(key) is not expected_finality_allowed:
            failures.append(
                f"{case_id}:{key}_unexpected:{claim_gate.get(key)!r}"
            )
    failures.extend(
        _validate_false_keys(
            claim_gate,
            keys=HANDOFF_STRONG_FALSE_KEYS,
            prefix=f"{case_id}:claim_gate",
        )
    )
    failures.extend(
        _validate_false_keys(
            report,
            keys=("mutates_chain", "runs_live_rpc", "submits_transaction"),
            prefix=f"{case_id}:report",
        )
    )
    for key in (
        "dataplane_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "revenue_recognition_claim_allowed",
        "production_readiness_claim_allowed",
    ):
        if summary.get(key) is not False:
            failures.append(f"{case_id}:summary:{key}_not_false:{summary.get(key)!r}")
    if "never allows dataplane" not in str(claim_gate.get("claim_boundary", "")):
        failures.append(f"{case_id}:claim_boundary_missing_dataplane_limit")
    return failures


def _build_external_handoff_case(root: Path, *, ready: bool) -> dict[str, Any]:
    case_root = root / ("external-handoff-ready" if ready else "external-handoff-blocked")
    _write_external_settlement_sources(case_root, ready=ready)
    report = build_external_settlement_handoff_report(case_root)
    failures = validate_external_handoff_report(
        report,
        expected_finality_allowed=ready,
        case_id="external_settlement_handoff_ready"
        if ready
        else "external_settlement_handoff_blocked",
    )
    return {
        "case": "external_settlement_handoff_ready"
        if ready
        else "external_settlement_handoff_blocked",
        "ok": not failures,
        "handoff_decision": report.get("handoff_decision", ""),
        "external_settlement_finality_claim_allowed": _mapping(
            report.get("claim_gate")
        ).get("external_settlement_finality_claim_allowed"),
        "economy_finality_claim_allowed": _mapping(report.get("claim_gate")).get(
            "economy_finality_claim_allowed"
        ),
        "dataplane_delivery_claim_allowed": _mapping(report.get("claim_gate")).get(
            "dataplane_delivery_claim_allowed"
        ),
        "production_readiness_claim_allowed": _mapping(report.get("claim_gate")).get(
            "production_readiness_claim_allowed"
        ),
        "mutates_chain": report.get("mutates_chain"),
        "runs_live_rpc": report.get("runs_live_rpc"),
        "submits_transaction": report.get("submits_transaction"),
        "failures": failures,
    }


def validate_reward_payload(
    payload: Mapping[str, Any],
    *,
    case_id: str = "reward_event",
) -> list[str]:
    failures: list[str] = []
    reward_claim_gate = _mapping(payload.get("reward_claim_gate"))
    if not reward_claim_gate:
        failures.append(f"{case_id}:reward_claim_gate_missing")
        return failures
    if reward_claim_gate.get("pending_token_submission_claim_allowed") is not True:
        failures.append(f"{case_id}:pending_token_submission_not_recorded")
    if reward_claim_gate.get("raw_identifiers_redacted") is not True:
        failures.append(f"{case_id}:raw_identifiers_not_redacted")
    if reward_claim_gate.get("payloads_redacted") is not True:
        failures.append(f"{case_id}:payloads_not_redacted")
    failures.extend(
        _validate_false_keys(
            reward_claim_gate,
            keys=REWARD_STRONG_FALSE_KEYS,
            prefix=f"{case_id}:reward_claim_gate",
        )
    )
    if "do not prove traffic delivery" not in str(
        reward_claim_gate.get("claim_boundary", "")
    ):
        failures.append(f"{case_id}:reward_claim_boundary_missing_limits")
    upstream = _mapping(payload.get("upstream_evidence"))
    if upstream.get("payloads_redacted") is not True:
        failures.append(f"{case_id}:upstream_evidence_not_redacted")
    return failures


def validate_economy_summary(
    summary: Mapping[str, Any],
    *,
    case_id: str,
    expected_local_or_pending: bool = True,
) -> list[str]:
    failures: list[str] = []
    economy = _mapping(summary.get("economy_finality_summary"))
    high_risk = _mapping(economy.get("high_risk_claim_gate"))
    if not economy:
        failures.append(f"{case_id}:economy_summary_missing")
        return failures
    if economy.get("present") is not True:
        failures.append(f"{case_id}:economy_summary_not_present")
    if economy.get("local_or_pending_only") is not expected_local_or_pending:
        failures.append(
            f"{case_id}:local_or_pending_only_unexpected:"
            f"{economy.get('local_or_pending_only')!r}"
        )
    if not high_risk:
        failures.append(f"{case_id}:high_risk_claim_gate_missing")
        return failures
    failures.extend(
        _validate_false_keys(
            high_risk,
            keys=ECONOMY_HIGH_RISK_FALSE_KEYS,
            prefix=f"{case_id}:high_risk_claim_gate",
        )
    )
    if high_risk.get("local_or_pending_economy_claim_allowed") is not True:
        failures.append(f"{case_id}:local_or_pending_claim_not_allowed")
    if high_risk.get("redacted") is not True:
        failures.append(f"{case_id}:high_risk_claim_gate_not_redacted")
    blockers = high_risk.get("blockers")
    if not isinstance(blockers, list) or "dataplane_confirmation_missing" not in blockers:
        failures.append(f"{case_id}:dataplane_blocker_missing")
    if "production_readiness_cross_plane_missing" not in list(blockers or []):
        failures.append(f"{case_id}:production_blocker_missing")
    return failures


def _last_event_payload(
    event_bus: EventBus,
    *,
    event_type: EventType,
    source_agent: str,
) -> Mapping[str, Any]:
    events = event_bus.get_event_history(
        event_type=event_type,
        source_agent=source_agent,
        limit=10,
    )
    if not events:
        return {}
    return events[-1].data


class _ModularBillingRequest:
    def __init__(
        self,
        event_bus: EventBus,
        payload: dict[str, Any] | bytes | None = None,
    ):
        self.state = SimpleNamespace(event_bus=event_bus)
        self._payload = payload if payload is not None else {}

    async def body(self) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")


class _FakeModularBillingService:
    webhook_secret = "local-verifier-secret"

    async def create_payment_session(self, user_id: str, plan: str) -> dict[str, Any]:
        return {
            "payment_url": "https://checkout.stripe.test/session/raw-verifier-secret",
            "session_id": "cs_raw_verifier_secret",
            "status": "created",
        }

    def get_plan_limits(self, plan: str) -> dict[str, Any]:
        return {"plan": plan, "max_nodes": 20, "max_meshes": 3}

    async def process_webhook(
        self,
        *,
        event_type: str,
        event_data: dict[str, Any],
        event_id: str,
        include_idempotency_metadata: bool,
    ) -> dict[str, Any]:
        assert event_type == "invoice.paid"
        assert event_id == "evt_modular_webhook_secret"
        assert include_idempotency_metadata is True
        assert event_data["customer"] == "cus_payload_secret"
        return {
            "status": "processed",
            "action": "subscription_extended",
            "customer_id": "cus_result_secret",
            "user_id": "modular-webhook-user-secret",
            "_idempotent": False,
        }


def validate_modular_billing_payload(
    payload: Mapping[str, Any],
    *,
    case_id: str = "modular_billing_event",
    expected_local_claim_key: str = "checkout_intent_claim_allowed",
    expected_settlement_action: str | None = None,
) -> list[str]:
    failures: list[str] = []
    settlement = _mapping(payload.get("settlement_evidence"))
    claim_gate = _mapping(settlement.get("claim_gate"))
    cross_plane_gate = _mapping(payload.get("cross_plane_claim_gate"))
    if not settlement:
        failures.append(f"{case_id}:settlement_evidence_missing")
        return failures
    if not claim_gate:
        failures.append(f"{case_id}:claim_gate_missing")
        return failures
    if claim_gate.get(expected_local_claim_key) is not True:
        failures.append(f"{case_id}:{expected_local_claim_key}_not_recorded")
    if (
        expected_settlement_action is not None
        and settlement.get("settlement_action") != expected_settlement_action
    ):
        failures.append(
            f"{case_id}:settlement_action_unexpected:"
            f"{settlement.get('settlement_action')!r}"
        )
    if settlement.get("live_provider_settlement_confirmed") is not False:
        failures.append(f"{case_id}:provider_settlement_overpromoted")
    if settlement.get("bank_settlement_confirmed") is not False:
        failures.append(f"{case_id}:bank_settlement_overpromoted")
    if settlement.get("chain_finality_confirmed") is not False:
        failures.append(f"{case_id}:chain_finality_overpromoted")
    failures.extend(
        _validate_false_keys(
            claim_gate,
            keys=MODULAR_BILLING_STRONG_FALSE_KEYS,
            prefix=f"{case_id}:claim_gate",
        )
    )
    if cross_plane_gate.get("allowed") is not False:
        failures.append(f"{case_id}:cross_plane_gate_not_fail_closed")
    if cross_plane_gate.get("blocked_claim_ids") != [
        "settlement_finality",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "production_readiness",
    ]:
        failures.append(f"{case_id}:cross_plane_blocked_claims_unexpected")
    if payload.get("raw_identifiers_redacted") is not True:
        failures.append(f"{case_id}:raw_identifiers_not_redacted")
    if payload.get("payloads_redacted") is not True:
        failures.append(f"{case_id}:payloads_not_redacted")
    if "does not prove dataplane delivery" not in str(payload.get("claim_boundary", "")):
        failures.append(f"{case_id}:claim_boundary_missing_dataplane_limit")
    return failures


def validate_modular_billing_payment_response(
    response: Mapping[str, Any],
    *,
    case_id: str = "modular_billing_response",
) -> list[str]:
    failures: list[str] = []
    claim_gate = _mapping(response.get("claim_gate"))
    cross_plane_gate = _mapping(response.get("cross_plane_claim_gate"))
    if not claim_gate:
        failures.append(f"{case_id}:claim_gate_missing")
        return failures
    if claim_gate.get("checkout_intent_claim_allowed") is not True:
        failures.append(f"{case_id}:checkout_intent_not_recorded")
    failures.extend(
        _validate_false_keys(
            claim_gate,
            keys=MODULAR_BILLING_STRONG_FALSE_KEYS,
            prefix=f"{case_id}:claim_gate",
        )
    )
    if claim_gate.get("requires_service_runtime_evidence_for_access_claim") is not True:
        failures.append(f"{case_id}:service_runtime_evidence_requirement_missing")
    if cross_plane_gate.get("allowed") is not False:
        failures.append(f"{case_id}:cross_plane_gate_not_fail_closed")
    if "does not prove dataplane delivery" not in str(
        response.get("claim_boundary", "")
    ):
        failures.append(f"{case_id}:claim_boundary_missing_dataplane_limit")
    return failures


def _build_modular_billing_payment_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "modular-billing-eventbus"))
    request = _ModularBillingRequest(event_bus)
    previous_service = getattr(modular_billing, "_billing_service", None)
    modular_billing._billing_service = _FakeModularBillingService()
    raw_user_id = "modular-billing-user-secret"
    raw_session_id = "cs_raw_verifier_secret"
    raw_url = "https://checkout.stripe.test/session/raw-verifier-secret"
    try:
        response = asyncio.run(
            modular_billing.create_payment(
                plan="pro",
                method="stripe",
                user=UserContext(user_id=raw_user_id, plan="free"),
                request=request,  # type: ignore[arg-type]
            )
        )
    finally:
        modular_billing._billing_service = previous_service

    payload = _last_event_payload(
        event_bus,
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=modular_billing._MODULAR_BILLING_PAYMENT_SOURCE_AGENT,
    )
    failures: list[str] = []
    if not payload:
        failures.append("modular_billing_event:payload_missing")
    else:
        failures.extend(validate_modular_billing_payload(payload))
        failures.extend(validate_modular_billing_payment_response(response))
        failures.extend(
            validate_economy_summary(
                event_trace_evidence_summary(payload),
                case_id="modular_billing_event_trace",
            )
        )
        serialized = json.dumps(payload, sort_keys=True)
        raw_log = (
            root
            / "modular-billing-eventbus"
            / ".agent_coordination"
            / "events.log"
        ).read_text(encoding="utf-8")
        for raw_value in (raw_user_id, raw_session_id, raw_url):
            if raw_value in serialized or raw_value in raw_log:
                failures.append("modular_billing_event:raw_value_leaked")
                break
    economy = (
        _mapping(event_trace_evidence_summary(payload).get("economy_finality_summary"))
        if payload
        else {}
    )
    high_risk = _mapping(economy.get("high_risk_claim_gate"))
    return {
        "case": "modular_billing_payment_intent",
        "ok": not failures,
        "payment_url_returned_to_caller": bool(response.get("payment_url")),
        "checkout_intent_claim_allowed": _mapping(
            _mapping(payload.get("settlement_evidence")).get("claim_gate")
        ).get("checkout_intent_claim_allowed")
        if payload
        else None,
        "response_claim_gate_present": bool(response.get("claim_gate")),
        "response_serviceability_claim_allowed": _mapping(
            response.get("claim_gate")
        ).get("serviceability_claim_allowed"),
        "response_customer_access_claim_allowed": _mapping(
            response.get("claim_gate")
        ).get("customer_access_claim_allowed"),
        "response_node_provisioning_claim_allowed": _mapping(
            response.get("claim_gate")
        ).get("node_provisioning_claim_allowed"),
        "external_settlement_finality_claim_allowed": high_risk.get(
            "external_settlement_finality_claim_allowed"
        ),
        "dataplane_delivery_claim_allowed": high_risk.get(
            "dataplane_delivery_claim_allowed"
        ),
        "production_readiness_claim_allowed": high_risk.get(
            "production_readiness_claim_allowed"
        ),
        "failures": failures,
    }


def _build_modular_billing_webhook_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "modular-billing-webhook-eventbus"))
    payload_body = {
        "type": "invoice.paid",
        "data": {
            "customer": "cus_payload_secret",
            "subscription": "sub_payload_secret",
        },
    }
    body = json.dumps(payload_body).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = compute_hmac_signature(
        f"{timestamp}.{body.decode('utf-8')}",
        _FakeModularBillingService.webhook_secret,
    )
    request = _ModularBillingRequest(event_bus, body)
    previous_service = getattr(modular_billing, "_billing_service", None)
    modular_billing._billing_service = _FakeModularBillingService()
    try:
        response = asyncio.run(
            modular_billing.billing_webhook(
                request,  # type: ignore[arg-type]
                x_signature=signature,
                x_timestamp=timestamp,
                x_event_id="evt_modular_webhook_secret",
            )
        )
    finally:
        modular_billing._billing_service = previous_service

    payload = _last_event_payload(
        event_bus,
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=modular_billing._MODULAR_BILLING_WEBHOOK_SOURCE_AGENT,
    )
    failures: list[str] = []
    if not payload:
        failures.append("modular_billing_webhook_event:payload_missing")
    else:
        failures.extend(
            validate_modular_billing_payload(
                payload,
                case_id="modular_billing_webhook_event",
                expected_local_claim_key="webhook_lifecycle_claim_allowed",
                expected_settlement_action="webhook_local_lifecycle_only",
            )
        )
        failures.extend(
            validate_economy_summary(
                event_trace_evidence_summary(payload),
                case_id="modular_billing_webhook_event_trace",
            )
        )
        serialized = json.dumps(payload, sort_keys=True)
        raw_log = (
            root
            / "modular-billing-webhook-eventbus"
            / ".agent_coordination"
            / "events.log"
        ).read_text(encoding="utf-8")
        for raw_value in (
            "evt_modular_webhook_secret",
            "cus_payload_secret",
            "sub_payload_secret",
            "cus_result_secret",
            "modular-webhook-user-secret",
            signature,
        ):
            if raw_value in serialized or raw_value in raw_log:
                failures.append("modular_billing_webhook_event:raw_value_leaked")
                break
    settlement = _mapping(payload.get("settlement_evidence")) if payload else {}
    claim_gate = _mapping(settlement.get("claim_gate"))
    economy = (
        _mapping(event_trace_evidence_summary(payload).get("economy_finality_summary"))
        if payload
        else {}
    )
    high_risk = _mapping(economy.get("high_risk_claim_gate"))
    return {
        "case": "modular_billing_webhook_lifecycle",
        "ok": not failures,
        "response_status": response.get("status"),
        "webhook_lifecycle_claim_allowed": claim_gate.get(
            "webhook_lifecycle_claim_allowed"
        ),
        "db_write_attempted": _mapping(settlement.get("db_write_evidence")).get(
            "attempted"
        ),
        "db_write_committed": _mapping(settlement.get("db_write_evidence")).get(
            "committed"
        ),
        "external_settlement_finality_claim_allowed": high_risk.get(
            "external_settlement_finality_claim_allowed"
        ),
        "dataplane_delivery_claim_allowed": high_risk.get(
            "dataplane_delivery_claim_allowed"
        ),
        "production_readiness_claim_allowed": high_risk.get(
            "production_readiness_claim_allowed"
        ),
        "failures": failures,
    }


def _build_reward_event_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "reward-eventbus"))
    upstream_claim_gate = {
        "schema": "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1",
        "surface": "token_bridge.push_rewards_to_chain",
        "decision": "pending_chain_submission_only",
        "local_actuator_execution_claim_allowed": True,
        "external_settlement_finality_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "payloads_redacted": True,
    }
    upstream_cross_plane_claim_gate = {
        "schema": "x0tta6bl4.token_bridge.safe_actuator_cross_plane_claim_gate.v1",
        "surface": "token_bridge.push_rewards_to_chain",
        "decision": "blocked_without_external_finality",
        "allowed": False,
        "requested_claim_ids": ["settlement_finality", "dataplane_delivery"],
        "blockers": ["external_settlement_finality_missing"],
        "payloads_redacted": True,
    }
    event_id = publish_reward_settlement_event(
        transition="recorded",
        source_agent="token-bridge",
        node_address="0xRewardRuntime",
        node_id="node-reward-runtime",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/token-bridge",
        did="did:mesh:reward-runtime",
        wallet_address="0xRewardWallet",
        packets=42,
        amount=12.5,
        status="submitted",
        submitted_transaction=True,
        simulated=False,
        settlement_recorded=True,
        local_accounting_recorded=False,
        transaction_hash="0xreward-runtime",
        upstream_event_ids=["safe-actuator-event-1"],
        upstream_source_agents=["token-bridge"],
        upstream_claim_gate=upstream_claim_gate,
        upstream_cross_plane_claim_gate=upstream_cross_plane_claim_gate,
        event_bus=event_bus,
        project_root=str(root),
    )
    payload = _last_event_payload(
        event_bus,
        event_type=EventType.REWARD_RELAY_RECORDED,
        source_agent="token-bridge",
    )
    failures: list[str] = []
    if not event_id:
        failures.append("reward_event:event_id_missing")
    if not payload:
        failures.append("reward_event:payload_missing")
    else:
        failures.extend(validate_reward_payload(payload))
        failures.extend(
            validate_economy_summary(
                event_trace_evidence_summary(payload),
                case_id="reward_event_trace",
            )
        )
    reward_claim_gate = _mapping(payload.get("reward_claim_gate")) if payload else {}
    economy = (
        _mapping(event_trace_evidence_summary(payload).get("economy_finality_summary"))
        if payload
        else {}
    )
    high_risk = _mapping(economy.get("high_risk_claim_gate"))
    return {
        "case": "reward_event_pending_submission",
        "ok": not failures,
        "event_id": event_id or "",
        "pending_token_submission_claim_allowed": reward_claim_gate.get(
            "pending_token_submission_claim_allowed"
        ),
        "token_settlement_finality_claim_allowed": reward_claim_gate.get(
            "token_settlement_finality_claim_allowed"
        ),
        "dataplane_delivery_claim_allowed": high_risk.get(
            "dataplane_delivery_claim_allowed"
        ),
        "production_readiness_claim_allowed": high_risk.get(
            "production_readiness_claim_allowed"
        ),
        "failures": failures,
    }


def validate_marketplace_payload(
    payload: Mapping[str, Any],
    *,
    case_id: str = "marketplace_event",
) -> list[str]:
    failures: list[str] = []
    settlement = _mapping(payload.get("settlement_evidence"))
    claim_gate = _mapping(settlement.get("claim_gate"))
    if not claim_gate:
        failures.append(f"{case_id}:settlement_claim_gate_missing")
        return failures
    if claim_gate.get("local_escrow_lifecycle_claim_allowed") is not True:
        failures.append(f"{case_id}:local_escrow_lifecycle_not_recorded")
    failures.extend(
        _validate_false_keys(
            claim_gate,
            keys=MARKETPLACE_STRONG_FALSE_KEYS,
            prefix=f"{case_id}:claim_gate",
        )
    )
    if claim_gate.get("requires_dataplane_evidence_for_delivery_claim") is not True:
        failures.append(f"{case_id}:dataplane_evidence_requirement_missing")
    if claim_gate.get("requires_external_finality_evidence_for_settlement_claim") is not True:
        failures.append(f"{case_id}:external_finality_requirement_missing")
    if claim_gate.get("payloads_redacted") is not True:
        failures.append(f"{case_id}:claim_gate_payloads_not_redacted")
    if payload.get("payloads_redacted") is not True:
        failures.append(f"{case_id}:payloads_not_redacted")
    return failures


def _build_marketplace_event_case(root: Path) -> dict[str, Any]:
    event_bus = EventBus(str(root / "marketplace-eventbus"))
    event_id = publish_marketplace_escrow_event(
        transition="held",
        source_agent="maas-marketplace",
        escrow_id="escrow-runtime-1",
        listing_id="listing-runtime-1",
        renter_id="renter-runtime-1",
        actor_id="actor-runtime-1",
        currency="X0T",
        status="held",
        node_id="node-marketplace-runtime",
        mesh_id="mesh-runtime",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-marketplace",
        did="did:mesh:marketplace-runtime",
        wallet_address="0xMarketplaceWallet",
        amount_token=3.5,
        settlement_evidence={
            "decision_basis": "local_escrow_lifecycle_only",
            "source_quality": "local_eventbus_smoke",
            "settlement_action": "lock_escrow_on_chain",
            "claim_gate": {
                "decision": "local_escrow_lifecycle_only",
                "local_escrow_lifecycle_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "economy_finality_claim_allowed": False,
                "bank_settlement_claim_allowed": False,
                "revenue_recognition_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_dataplane_evidence_for_delivery_claim": True,
                "requires_external_finality_evidence_for_settlement_claim": True,
                "payloads_redacted": True,
                "claim_boundary": (
                    "local escrow lifecycle only; not external settlement or dataplane proof"
                ),
            },
        },
        event_bus=event_bus,
        project_root=str(root),
    )
    payload = _last_event_payload(
        event_bus,
        event_type=EventType.MARKETPLACE_ESCROW_HELD,
        source_agent="maas-marketplace",
    )
    failures: list[str] = []
    if not event_id:
        failures.append("marketplace_event:event_id_missing")
    if not payload:
        failures.append("marketplace_event:payload_missing")
    else:
        failures.extend(validate_marketplace_payload(payload))
        failures.extend(
            validate_economy_summary(
                event_trace_evidence_summary(payload),
                case_id="marketplace_event_trace",
            )
        )
    economy = (
        _mapping(event_trace_evidence_summary(payload).get("economy_finality_summary"))
        if payload
        else {}
    )
    high_risk = _mapping(economy.get("high_risk_claim_gate"))
    return {
        "case": "marketplace_local_escrow_lifecycle",
        "ok": not failures,
        "event_id": event_id or "",
        "local_escrow_lifecycle_claim_allowed": _mapping(
            _mapping(payload.get("settlement_evidence")).get("claim_gate")
        ).get("local_escrow_lifecycle_claim_allowed")
        if payload
        else None,
        "dataplane_delivery_claim_allowed": high_risk.get(
            "dataplane_delivery_claim_allowed"
        ),
        "production_readiness_claim_allowed": high_risk.get(
            "production_readiness_claim_allowed"
        ),
        "failures": failures,
    }


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = [
        _build_external_handoff_case(root, ready=False),
        _build_external_handoff_case(root, ready=True),
        _build_reward_event_case(root),
        _build_marketplace_event_case(root),
        _build_modular_billing_payment_case(root),
        _build_modular_billing_webhook_case(root),
    ]
    failures = [
        f"{case['case']}:{failure}"
        for case in cases
        for failure in case.get("failures", [])
    ]
    ok = not failures and all(case.get("ok") is True for case in cases)
    return {
        "schema": SCHEMA,
        "status": "VERIFIED HERE" if ok else "BLOCKED",
        "ok": ok,
        "decision": DECISION_VERIFIED if ok else DECISION_GAPS,
        "generated_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "cases_run": len(cases),
            "cases_checked": sum(1 for case in cases if case.get("ok") is True),
            "external_settlement_handoff_cases": 2,
            "reward_events_checked": 1,
            "marketplace_events_checked": 1,
            "modular_billing_events_checked": 1,
            "modular_billing_webhook_events_checked": 1,
            "modular_billing_response_claim_gates_checked": 1,
            "service_trace_economy_summaries_checked": 4,
            "high_risk_claim_gates_fail_closed": ok,
            "local_simulated_harness": True,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "dataplane_or_production_claimed": False,
            "customer_traffic_claimed": False,
            "revenue_recognition_claimed": False,
            "production_readiness_claimed": False,
        },
        "cases": cases,
        "failures": failures,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify economy surfaces stay separated from dataplane claims."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Temporary verifier root. Defaults to an isolated temp directory.",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON to stdout")
    parser.add_argument(
        "--require-separated",
        action="store_true",
        help="Exit 2 when economy/dataplane separation is not verified.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args(argv)


def _write_output(path_text: str, report: Mapping[str, Any]) -> None:
    output_path = Path(path_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )  # nosec - diagnostic report, no secrets


def _build_report_for_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.root is not None:
        return build_report(args.root)
    with tempfile.TemporaryDirectory(prefix="x0t-economy-dataplane-") as temp_root:
        return build_report(Path(temp_root))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = _build_report_for_args(args)
    if args.output_json:
        _write_output(args.output_json, report)
    if args.json or not args.output_json:
        print(json.dumps(report, ensure_ascii=True, indent=2))  # nosec - diagnostic report, no secrets
    if args.require_separated and not report.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
