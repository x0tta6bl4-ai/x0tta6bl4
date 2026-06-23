from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"

REQUIRED_SECTIONS = {
    "artifact_identity",
    "authorization_scope",
    "environment",
    "methodology",
    "probe_matrix",
    "packet_flow_summary",
    "raw_capture_redaction",
    "repeatability_limits",
    "result_summary",
    "claim_boundary",
    "evidence_links",
}

HIGH_RISK_FALSE_FLAGS = {
    "external_dpi_tested",
    "reachability_observed",
    "dpi_bypass_confirmed",
    "bypass_confirmed",
    "dataplane_confirmed",
    "production_ready",
    "customer_traffic_confirmed",
    "durable_policy_confirmed",
    "anonymity_confirmed",
    "provider_health_confirmed",
}


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_external_dpi_proxy_evidence_shape_is_schema_not_proof():
    schema = _load_schema()

    assert schema["artifact_kind"] == "verification_contract_not_evidence"
    assert schema["status"] == "SCHEMA_ONLY_NOT_PRODUCTION_PROOF"
    assert schema["claim_status"] == "current_evidence_contract_not_proof"
    assert "not evidence" in schema["claim_boundary"]["summary"].lower()
    assert "production readiness" in schema["claim_boundary"]["not_proven_by_this_shape"]

    proof_flags = schema["claim_boundary"]["proof_claims_default_false"]
    for flag in HIGH_RISK_FALSE_FLAGS:
        assert proof_flags[flag] is False, flag


def test_external_dpi_proxy_evidence_shape_requires_bounded_sections():
    schema = _load_schema()

    assert set(schema["required_top_level_sections"]) == REQUIRED_SECTIONS
    assert set(schema["required_sections"]) == REQUIRED_SECTIONS

    environment_fields = set(schema["required_sections"]["environment"]["required_fields"])
    assert {
        "network_region_bucket",
        "isp_or_lab_profile_hash",
        "egress_location_bucket",
        "time_window_utc",
        "tool_versions",
        "policy_context",
    }.issubset(environment_fields)

    packet_fields = set(schema["required_sections"]["packet_flow_summary"]["required_fields"])
    assert {
        "bytes_bucket",
        "rtt_ms_bucket",
        "capture_artifact_hashes",
        "packet_payloads_redacted",
    }.issubset(packet_fields)

    repeatability_fields = set(schema["required_sections"]["repeatability_limits"]["required_fields"])
    assert {
        "sample_window_utc",
        "sample_count",
        "locations_count",
        "networks_count",
        "known_confounders",
        "not_generalizable_beyond_environment",
        "refresh_after_utc",
    }.issubset(repeatability_fields)


def test_external_dpi_proxy_evidence_shape_keeps_raw_values_out():
    schema = _load_schema()
    redaction = schema["redaction_rules"]

    assert {
        "raw_ip_address",
        "raw_domain",
        "raw_url",
        "raw_sni",
        "raw_host_header",
        "raw_http_headers",
        "raw_payload",
        "subscriber_id",
        "customer_id",
        "wallet_address",
        "spiffe_id",
        "did",
        "api_token",
        "private_key",
    }.issubset(set(redaction["forbidden_raw_fields"]))

    assert {
        "probe_target_hash",
        "redacted_capture_sha256",
        "artifact_sha256",
    }.issubset(set(redaction["hash_fields"]))

    raw_capture_fields = set(schema["required_sections"]["raw_capture_redaction"]["required_fields"])
    assert {
        "redaction_performed",
        "forbidden_raw_fields_absent",
        "raw_capture_retention_policy",
        "redacted_capture_sha256",
    }.issubset(raw_capture_fields)


def test_external_dpi_proxy_evidence_shape_requires_control_treatment_logic():
    schema = _load_schema()
    result_logic = schema["result_logic"]

    required_logic = set(result_logic["dpi_bypass_confirmed_requires_all"])
    assert {
        "authorization_scope.authorization_present=true",
        "methodology.external_dpi_or_blocking_middlebox_observed=true",
        "result_summary.external_dpi_tested=true",
        "result_summary.baseline_blocked_or_detected=true",
        "result_summary.treatment_reachability_observed=true",
        "raw_capture_redaction.redaction_performed=true",
        "raw_capture_redaction.forbidden_raw_fields_absent=true",
        "claim_boundary.proof_claims.production_ready=false",
    }.issubset(required_logic)

    assert set(result_logic["must_remain_false_without_external_artifact"]) == {
        "external_dpi_tested",
        "reachability_observed",
        "dpi_bypass_confirmed",
        "bypass_confirmed",
        "dataplane_confirmed",
    }
    assert "production_ready" in result_logic["must_always_remain_false_for_this_artifact_family"]


def test_external_dpi_proxy_minimal_example_is_incomplete_and_redacted():
    schema = _load_schema()
    example = schema["minimal_redacted_candidate_shape"]

    assert example["status"] == "INCOMPLETE_EXAMPLE_NOT_EVIDENCE"
    assert REQUIRED_SECTIONS.issubset(example)
    assert example["authorization_scope"]["authorization_present"] is False
    assert example["authorization_scope"]["consent_or_legal_basis_present"] is False
    assert example["packet_flow_summary"]["packet_payloads_redacted"] is True
    assert example["raw_capture_redaction"]["redaction_performed"] is True
    assert example["raw_capture_redaction"]["forbidden_raw_fields_absent"] is True
    assert example["repeatability_limits"]["not_generalizable_beyond_environment"] is True

    for flag in {
        "external_dpi_tested",
        "reachability_observed",
        "dpi_bypass_confirmed",
        "bypass_confirmed",
        "dataplane_confirmed",
        "production_ready",
    }:
        assert example["result_summary"][flag] is False, flag
        assert example["claim_boundary"]["proof_claims"][flag] is False, flag


def test_external_dpi_proxy_related_artifact_paths_exist():
    schema = _load_schema()

    for artifact in schema["related_current_artifacts"]:
        path = ROOT / artifact["path"]
        assert path.exists(), artifact["path"]

    for path_text in schema["candidate_paths"].values():
        assert (ROOT / path_text).exists(), path_text
