from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"
CONTRACT = ROOT / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "verify_external_dpi_proxy_reachability_evidence_test",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_contract(root: Path) -> None:
    path = root / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(CONTRACT.read_bytes())


def _write_candidate(root: Path, payload: dict[str, Any]) -> Path:
    _sync_source_artifacts(root, payload)
    _sync_artifact_hash(payload)
    path = root / "docs/verification/incoming/dpi_lab.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _h(char: str) -> str:
    return char * 64


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sync_artifact_hash(payload: dict[str, Any]) -> None:
    identity = payload.get("artifact_identity")
    if not isinstance(identity, dict) or "artifact_sha256" not in identity:
        return
    normalized = json.loads(_canonical_json(payload))
    normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    identity["artifact_sha256"] = _sha256_text(_canonical_json(normalized))


def _sync_source_artifacts(root: Path, payload: dict[str, Any]) -> None:
    links = payload.get("evidence_links")
    if not isinstance(links, dict):
        return
    source_artifacts = links.get("source_artifacts")
    if not isinstance(source_artifacts, list):
        return
    source_hashes = links.setdefault("source_hashes", [])
    if not isinstance(source_hashes, list):
        return

    for artifact in source_artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            continue
        artifact_path = root / artifact["path"]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            {"fixture": artifact.get("role", "source_artifact")},
            sort_keys=True,
        )
        artifact_path.write_text(text, encoding="utf-8")
        digest = _sha256_text(text)
        for item in source_hashes:
            if isinstance(item, dict) and item.get("path") == artifact["path"]:
                item["sha256"] = digest
                break
        else:
            source_hashes.append({"path": artifact["path"], "sha256": digest})
        if artifact.get("role") in {"redacted_capture", "redacted_probe_summary"}:
            payload["packet_flow_summary"]["capture_artifact_hashes"] = [digest]
            payload["raw_capture_redaction"]["redacted_capture_sha256"] = digest


def _valid_payload() -> dict[str, Any]:
    return {
        "status": "VERIFIED",
        "artifact_identity": {
            "artifact_id": "external-dpi-proxy-reachability-20260530T000000Z",
            "schema_version": "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1",
            "claim_id": "external_dpi_proxy_reachability",
            "captured_at_utc": "2026-05-30T00:00:00Z",
            "collector_kind": "authorized_lab",
            "operator_or_lab_hash": _h("a"),
            "artifact_sha256": _h("b"),
        },
        "authorization_scope": {
            "authorization_present": True,
            "scope_id_hash": _h("c"),
            "scope_summary": "authorized bounded lab run",
            "consent_or_legal_basis_present": True,
            "collection_boundaries": [
                "no customer traffic",
                "no raw target identifiers retained in repository",
            ],
        },
        "environment": {
            "network_region_bucket": "coarse-region-1",
            "network_type": "authorized-lab-network",
            "isp_or_lab_profile_hash": _h("d"),
            "egress_location_bucket": "coarse-egress-1",
            "time_window_utc": "2026-05-30T00:00:00Z/2026-05-30T00:10:00Z",
            "tool_versions": {"collector": "1.0"},
            "policy_context": "authorized external DPI lab",
            "clock_sync_status": "ntp-synced",
        },
        "methodology": {
            "control_path_description": "plain control path",
            "treatment_path_description": "obfuscated proxy treatment path",
            "external_dpi_or_blocking_middlebox_observed": True,
            "probe_payload_class": "synthetic reachability probe",
            "success_criteria": "treatment reaches controlled endpoint while control is blocked",
            "failure_criteria": "control and treatment both fail or treatment leaks raw target metadata",
            "anti_replay_controls": ["unique nonce class without retaining raw nonce"],
        },
        "probe_matrix": {
            "probe_pairs": [
                {
                    "pair_id": "pair-1",
                    "transport": "faketls",
                    "proxy_or_fronting_mode": "fronted-proxy",
                    "target_category": "controlled-endpoint",
                    "probe_target_hash": _h("e"),
                    "control_result_bucket": "http_blocked",
                    "treatment_result_bucket": "http_200",
                    "attempts": 3,
                    "successes": 3,
                    "failure_buckets": ["http_blocked"],
                }
            ],
            "attempt_count": 6,
            "success_count": 3,
            "failure_buckets": ["http_blocked"],
            "control_probe_ids": ["control-1"],
            "treatment_probe_ids": ["treatment-1"],
        },
        "packet_flow_summary": {
            "flows_observed": 2,
            "bytes_bucket": "1k-10k",
            "duration_ms_bucket": "1000-5000",
            "rtt_ms_bucket": "50-100",
            "loss_bucket": "0",
            "dns_result_bucket": "resolved",
            "tls_handshake_bucket": "completed",
            "http_status_bucket": "2xx",
            "capture_artifact_hashes": [_h("f")],
            "packet_payloads_redacted": True,
        },
        "raw_capture_redaction": {
            "redaction_performed": True,
            "redaction_tool": "x0t-redactor",
            "redaction_tool_version": "1.0",
            "redacted_fields": ["addresses", "hosts", "payloads", "headers"],
            "forbidden_raw_fields_absent": True,
            "raw_capture_retention_policy": "raw captures quarantined outside repository",
            "redacted_capture_sha256": _h("1"),
        },
        "repeatability_limits": {
            "sample_window_utc": "2026-05-30T00:00:00Z/2026-05-30T00:10:00Z",
            "sample_count": 6,
            "locations_count": 1,
            "networks_count": 1,
            "known_confounders": ["middlebox policy can change", "CDN routing can change"],
            "not_generalizable_beyond_environment": True,
            "refresh_after_utc": "2026-06-06T00:00:00Z",
        },
        "result_summary": {
            "external_dpi_tested": True,
            "baseline_blocked_or_detected": True,
            "treatment_reachability_observed": True,
            "reachability_observed": True,
            "dpi_bypass_confirmed": True,
            "bypass_confirmed": True,
            "dataplane_confirmed": True,
            "production_ready": False,
            "confidence_bucket": "bounded-lab-single-region",
            "decision": "bounded_external_dpi_bypass_observed",
        },
        "claim_boundary": {
            "summary": "Bounded external lab observation only.",
            "not_proven": [
                "production readiness",
                "durable censorship bypass",
                "anonymity",
                "provider health",
                "customer traffic",
            ],
            "proof_claims": {
                "external_dpi_tested": True,
                "baseline_blocked_or_detected": True,
                "treatment_reachability_observed": True,
                "reachability_observed": True,
                "dpi_bypass_confirmed": True,
                "bypass_confirmed": True,
                "dataplane_confirmed": True,
                "production_ready": False,
                "customer_traffic_confirmed": False,
                "durable_policy_confirmed": False,
                "anonymity_confirmed": False,
                "provider_health_confirmed": False,
                "payment_or_token_settlement_finality_confirmed": False,
            },
            "upgrade_rule": "Only this bounded artifact family can raise DPI flags, never production flags.",
        },
        "evidence_links": {
            "source_artifacts": [
                {
                    "path": "docs/verification/incoming/artifacts/dpi/redacted-capture.json",
                    "role": "redacted_capture",
                }
            ],
            "artifact_roles": ["redacted_capture", "lab_summary"],
            "source_hashes": [
                {
                    "path": "docs/verification/incoming/artifacts/dpi/redacted-capture.json",
                    "sha256": _h("2"),
                }
            ],
            "related_local_evidence_refs": [],
        },
    }


def test_dpi_proxy_validator_accepts_redacted_authorized_candidate(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    _write_candidate(tmp_path, _valid_payload())

    report = validator.build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["decision"] == validator.DECISION_READY
    assert report["summary"]["ready_to_import"] is True
    assert report["summary"]["external_dpi_tested"] is True
    assert report["summary"]["dpi_bypass_confirmed"] is True
    assert report["summary"]["production_ready"] is False
    assert report["failures"] == []
    claim_gate = report["external_dpi_intake_claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.external_dpi_intake.claim_gate.v1"
    assert claim_gate["local_validator_run_claim_allowed"] is True
    assert claim_gate["candidate_file_observed_claim_allowed"] is True
    assert claim_gate[
        "bounded_external_dpi_candidate_ready_to_import_claim_allowed"
    ] is True
    assert claim_gate[
        "bounded_external_dpi_bypass_observation_claim_allowed"
    ] is True
    assert claim_gate["proof_gate_dpi_bypass_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_dpi_proxy_validator_rejects_current_gap_record_candidate(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    _write_candidate(
        tmp_path,
        {
            "schema": "x0tta6bl4.ghost_pulse.claim_evidence.v1",
            "claim_id": "dpi_lab",
            "status": "INCOMPLETE",
            "mode": "EXTERNAL_EVIDENCE_GAP_RECORD",
            "gap_artifact_role": "evidence_gap_record",
            "claim_boundary": {"claim_verified": False},
        },
    )

    report = validator.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == validator.DECISION_REJECTED
    assert "candidate is a gap record, not external DPI/proxy evidence" in report["failures"]
    assert "artifact_identity section is required" in report["failures"]
    assert report["summary"]["ready_to_import"] is False
    claim_gate = report["external_dpi_intake_claim_gate"]
    assert claim_gate[
        "bounded_external_dpi_candidate_ready_to_import_claim_allowed"
    ] is False
    assert claim_gate["validation_failures_present"] is True
    assert claim_gate["proof_gate_dpi_bypass_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_dpi_proxy_validator_rejects_raw_values_and_production_promotion(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    payload = _valid_payload()
    payload["probe_matrix"]["probe_pairs"][0]["raw_url"] = "https://forbidden.invalid/path"
    payload["result_summary"]["production_ready"] = True
    payload["claim_boundary"]["proof_claims"]["production_ready"] = True
    _write_candidate(tmp_path, payload)

    report = validator.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == validator.DECISION_REJECTED
    assert "$.probe_matrix.probe_pairs[0].raw_url is forbidden raw evidence field" in report["failures"]
    assert "production_ready must remain false for this artifact family" in report["failures"]


def test_dpi_proxy_validator_rejects_artifact_content_hash_mismatch(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    candidate = _write_candidate(tmp_path, _valid_payload())
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["artifact_identity"]["artifact_sha256"] = _h("b")
    candidate.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report = validator.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == validator.DECISION_REJECTED
    assert (
        "artifact_identity.artifact_sha256 must match canonical artifact content "
        "with artifact_sha256 set to zeroes"
    ) in report["failures"]


def test_dpi_proxy_validator_rejects_source_artifact_hash_mismatch(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    _write_candidate(tmp_path, _valid_payload())
    source = tmp_path / "docs/verification/incoming/artifacts/dpi/redacted-capture.json"
    source.write_text("tampered", encoding="utf-8")

    report = validator.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == validator.DECISION_REJECTED
    assert "evidence_links.source_artifacts[0].sha256 does not match file bytes" in report["failures"]


def test_dpi_proxy_validator_rejects_source_artifact_outside_intake_artifacts(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    payload = _valid_payload()
    payload["evidence_links"]["source_artifacts"][0]["path"] = (
        "docs/verification/other/redacted-capture.json"
    )
    payload["evidence_links"]["source_hashes"][0]["path"] = (
        "docs/verification/other/redacted-capture.json"
    )
    _write_candidate(tmp_path, payload)

    report = validator.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == validator.DECISION_REJECTED
    assert (
        "evidence_links.source_artifacts[0].path must stay under "
        "docs/verification/incoming/artifacts"
    ) in report["failures"]


def test_dpi_proxy_validator_require_ready_returns_two_for_gap_candidate(tmp_path):
    validator = _load_script()
    _write_contract(tmp_path)
    _write_candidate(
        tmp_path,
        {
            "schema": "x0tta6bl4.ghost_pulse.claim_evidence.v1",
            "claim_id": "dpi_lab",
            "status": "INCOMPLETE",
            "mode": "EXTERNAL_EVIDENCE_GAP_RECORD",
        },
    )

    code = validator.main(["--root", str(tmp_path), "--require-ready", "--json"])

    assert code == 2
