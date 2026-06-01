from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_economy_dataplane_separation.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_economy_dataplane_separation",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_economy_dataplane_separation_passes_in_local_harness(
    tmp_path: Path,
) -> None:
    module = load_module()

    report = module.build_report(tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["ok"] is True
    assert report["decision"] == module.DECISION_VERIFIED
    assert report["summary"]["cases_run"] == 5
    assert report["summary"]["cases_checked"] == 5
    assert report["summary"]["external_settlement_handoff_cases"] == 2
    assert report["summary"]["reward_events_checked"] == 1
    assert report["summary"]["marketplace_events_checked"] == 1
    assert report["summary"]["modular_billing_events_checked"] == 1
    assert report["summary"]["modular_billing_response_claim_gates_checked"] == 1
    assert report["summary"]["service_trace_economy_summaries_checked"] == 3
    assert report["summary"]["high_risk_claim_gates_fail_closed"] is True
    assert report["summary"]["mutates_chain"] is False
    assert report["summary"]["runs_live_rpc"] is False
    assert report["summary"]["submits_transaction"] is False
    assert report["summary"]["dataplane_or_production_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["failures"] == []
    case_ids = {case["case"] for case in report["cases"]}
    assert "external_settlement_handoff_ready" in case_ids
    assert "reward_event_pending_submission" in case_ids
    assert "marketplace_local_escrow_lifecycle" in case_ids
    assert "modular_billing_payment_intent" in case_ids


def test_external_handoff_validator_rejects_dataplane_overpromotion() -> None:
    module = load_module()
    report = {
        "ok": True,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "summary": {
            "dataplane_delivery_claim_allowed": True,
            "customer_traffic_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
            "production_readiness_claim_allowed": False,
        },
        "claim_gate": {
            "schema": "x0tta6bl4.external_settlement.operator_handoff.claim_gate.v1",
            "external_settlement_finality_claim_allowed": True,
            "economy_finality_claim_allowed": True,
            "retained_evidence_claim_allowed": True,
            "live_rpc_receipt_claim_allowed": True,
            "dataplane_delivery_claim_allowed": True,
            "customer_traffic_claim_allowed": False,
            "customer_dataplane_delivery_claim_allowed": False,
            "bank_settlement_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "claim_boundary": "never allows dataplane",
        },
    }

    failures = module.validate_external_handoff_report(
        report,
        expected_finality_allowed=True,
        case_id="tampered_handoff",
    )

    assert (
        "tampered_handoff:claim_gate:dataplane_delivery_claim_allowed_not_false:True"
        in failures
    )
    assert (
        "tampered_handoff:summary:dataplane_delivery_claim_allowed_not_false:True"
        in failures
    )


def test_reward_payload_validator_rejects_settlement_finality_overpromotion() -> None:
    module = load_module()
    payload = {
        "reward_claim_gate": {
            "pending_token_submission_claim_allowed": True,
            "traffic_delivery_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "token_settlement_finality_claim_allowed": True,
            "external_settlement_finality_claim_allowed": False,
            "economy_finality_claim_allowed": False,
            "bank_settlement_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": "Reward events do not prove traffic delivery",
        },
        "upstream_evidence": {"payloads_redacted": True},
    }

    failures = module.validate_reward_payload(payload)

    assert (
        "reward_event:reward_claim_gate:token_settlement_finality_claim_allowed_not_false:True"
        in failures
    )


def test_modular_billing_payload_validator_rejects_dataplane_overpromotion() -> None:
    module = load_module()
    payload = {
        "settlement_evidence": {
            "live_provider_settlement_confirmed": False,
            "bank_settlement_confirmed": False,
            "chain_finality_confirmed": False,
            "claim_gate": {
                "checkout_intent_claim_allowed": True,
                "payment_provider_settlement_claim_allowed": False,
                "bank_settlement_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "dataplane_delivery_claim_allowed": True,
                "customer_dataplane_delivery_claim_allowed": False,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "revenue_recognition_claim_allowed": False,
                "production_slo_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
        },
        "cross_plane_claim_gate": {
            "allowed": False,
            "blocked_claim_ids": [
                "settlement_finality",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
                "production_readiness",
            ],
        },
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": "modular billing event; does not prove dataplane delivery",
    }

    failures = module.validate_modular_billing_payload(payload)

    assert (
        "modular_billing_event:claim_gate:dataplane_delivery_claim_allowed_not_false:True"
        in failures
    )


def test_modular_billing_response_validator_rejects_serviceability_overpromotion() -> None:
    module = load_module()
    response = {
        "claim_gate": {
            "checkout_intent_claim_allowed": True,
            "payment_provider_settlement_claim_allowed": False,
            "bank_settlement_claim_allowed": False,
            "external_settlement_finality_claim_allowed": False,
            "serviceability_claim_allowed": True,
            "paid_customer_serviceability_claim_allowed": False,
            "customer_access_claim_allowed": False,
            "vpn_access_claim_allowed": False,
            "node_provisioning_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "customer_dataplane_delivery_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "requires_service_runtime_evidence_for_access_claim": True,
        },
        "cross_plane_claim_gate": {"allowed": False},
        "claim_boundary": "modular billing response; does not prove dataplane delivery",
    }

    failures = module.validate_modular_billing_payment_response(response)

    assert (
        "modular_billing_response:claim_gate:serviceability_claim_allowed_not_false:True"
        in failures
    )


def test_economy_dataplane_separation_cli_require_separated(
    tmp_path: Path,
) -> None:
    output = tmp_path / "economy-dataplane.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path / "run"),
            "--require-separated",
            "--output-json",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["decision"] == "ECONOMY_DATAPLANE_SEPARATION_VERIFIED"
