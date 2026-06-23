from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import customer_traffic_artifact_evidence


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_customer_traffic_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_customer_traffic_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_proof(
    tmp_path: Path,
    *,
    end_to_end_customer_path_confirmed: bool = True,
    customer_request_observed: bool = True,
    customer_response_validated: bool = True,
    environment: str = "production",
    status: str = "VERIFIED",
    source_artifact_role: str = "redacted_end_to_end_customer_path_probe_report",
) -> Path:
    path = tmp_path / "customer_traffic.json"
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.customer_traffic.local_evidence_input.v1",
                "status": status,
                "observed_evidence": {
                    "environment": environment,
                    "end_to_end_customer_path_confirmed": (
                        end_to_end_customer_path_confirmed
                    ),
                    "customer_request_observed": customer_request_observed,
                    "customer_response_validated": customer_response_validated,
                    "customer_payloads_redacted": True,
                },
                "source_artifacts": [
                    {
                        "role": source_artifact_role,
                        "sha256": "b" * 64,
                        "redacted": True,
                    }
                ],
                "raw_identifiers_redacted": True,
                "raw_values_redacted": True,
                "payloads_redacted": True,
                "authorization_scope_redacted": True,
                "claim_boundary": (
                    "Redacted end-to-end production customer-path evidence only; "
                    "not dataplane, trust, settlement, or production readiness proof."
                ),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_collect_blocks_without_explicit_redacted_proof_authorization(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path)
    args = collector.parse_args(["--root", str(tmp_path), "--proof-json", str(proof)])

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_PROOF_INTAKE_NOT_AUTHORIZED"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "allow_redacted_local_proof_intake_required" in report["blockers"]


def test_collect_writes_event_recognized_by_cross_plane_proof_gate(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path)
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "CUSTOMER_TRAFFIC_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True

    artifact = customer_traffic_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["production_customer_traffic_confirmed"] is True
    assert artifact["selected_event"]["environment"] == "production"
    assert artifact["selected_event"]["redacted"] is True


def test_collect_non_production_or_partial_proof_writes_non_promoting_event(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(
        tmp_path,
        environment="lab",
        customer_response_validated=False,
    )
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "CUSTOMER_TRAFFIC_PROOF_NOT_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False
    assert "customer_traffic_input_environment_not_production" in report["blockers"]
    assert "customer_traffic_input_response_not_validated" in report["blockers"]

    artifact = customer_traffic_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_customer_traffic_event_not_found" in artifact["blockers"]
    assert "customer_traffic_not_confirmed" in artifact["candidate_blockers"]


def test_collect_blocks_verified_proof_without_required_customer_probe_artifact_role(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path, source_artifact_role="generic_redacted_log")
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "CUSTOMER_TRAFFIC_PROOF_NOT_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False
    assert "customer_traffic_input_required_source_artifact_missing" in report[
        "blockers"
    ]

    artifact = customer_traffic_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_customer_traffic_event_not_found" in artifact["blockers"]
    assert "customer_traffic_not_confirmed" in artifact["candidate_blockers"]


def test_collect_rejects_hidden_overclaim_fields_in_proof_json(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path)
    payload = json.loads(proof.read_text(encoding="utf-8"))
    payload["production_readiness_claim_allowed"] = True
    payload["observed_evidence"]["settlement_finality_confirmed"] = True
    proof.write_text(json.dumps(payload), encoding="utf-8")
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_INVALID_PROOF_JSON"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "customer_traffic_input_schema_validation_failed" in report["blockers"]


def test_collect_exposes_template_without_writing_event(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        ["--root", str(tmp_path), "--print-template", "--json"]
    )

    report = collector.collect(args)

    assert report["decision"] == "CUSTOMER_TRAFFIC_TEMPLATE"
    assert report["event_written"] is False
    assert report["template"]["raw_identifiers_redacted"] is True
    assert report["template"]["payloads_redacted"] is True
