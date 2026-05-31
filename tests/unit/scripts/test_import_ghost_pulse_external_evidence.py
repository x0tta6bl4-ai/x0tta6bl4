import importlib.util
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _measurement_value(expectation):
    if expectation in (True, False):
        return expectation
    if expectation == 0:
        return 0
    if expectation == "nonempty":
        return "recorded"
    if expectation == "positive_int":
        return 3
    if expectation == "sha256":
        return "a" * 64
    if expectation == "bool_true":
        return True
    raise AssertionError(f"unhandled expectation: {expectation!r}")


def _artifact_by_role(payload, role):
    for artifact in payload["artifacts"]:
        if artifact.get("role") == role:
            return artifact
    raise AssertionError(f"missing artifact role: {role}")


def _write_artifact_json(root: Path, proof, artifact, value):
    artifact_path = root / artifact["path"]
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    artifact["sha256"] = proof.sha256_file(artifact_path)


def _h(char: str) -> str:
    return char * 64


def _canonical_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sync_dpi_proxy_integrity(root: Path, payload: dict) -> None:
    links = payload.get("evidence_links")
    if not isinstance(links, dict):
        return
    source_artifacts = links.get("source_artifacts")
    source_hashes = links.setdefault("source_hashes", [])
    if not isinstance(source_artifacts, list) or not isinstance(source_hashes, list):
        return

    for artifact in source_artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            continue
        artifact_path = root / artifact["path"]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"fixture": artifact.get("role", "source_artifact")}, sort_keys=True)
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

    identity = payload.get("artifact_identity")
    if isinstance(identity, dict):
        normalized = json.loads(_canonical_json(payload))
        normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
        identity["artifact_sha256"] = _sha256_text(_canonical_json(normalized))


def _dpi_proxy_sections() -> dict:
    return {
        "artifact_identity": {
            "artifact_id": "external-dpi-proxy-reachability-20260522T000000Z",
            "schema_version": "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1",
            "claim_id": "dpi_lab",
            "captured_at_utc": "2026-05-22T00:00:00Z",
            "collector_kind": "authorized_lab",
            "operator_or_lab_hash": _h("a"),
            "artifact_sha256": _h("b"),
        },
        "authorization_scope": {
            "authorization_present": True,
            "scope_id_hash": _h("c"),
            "scope_summary": "authorized bounded lab fixture",
            "consent_or_legal_basis_present": True,
            "collection_boundaries": ["no customer traffic", "no raw targets retained"],
        },
        "environment": {
            "network_region_bucket": "coarse-region-1",
            "network_type": "authorized-lab-network",
            "isp_or_lab_profile_hash": _h("d"),
            "egress_location_bucket": "coarse-egress-1",
            "time_window_utc": "2026-05-22T00:00:00Z/2026-05-22T00:10:00Z",
            "tool_versions": {"collector": "test"},
            "policy_context": "authorized external DPI fixture",
            "clock_sync_status": "ntp-synced",
        },
        "methodology": {
            "control_path_description": "plain control path",
            "treatment_path_description": "obfuscated treatment path",
            "external_dpi_or_blocking_middlebox_observed": True,
            "probe_payload_class": "synthetic reachability probe",
            "success_criteria": "treatment succeeds while control is blocked",
            "failure_criteria": "treatment fails or leaks raw target metadata",
            "anti_replay_controls": ["bounded nonce class"],
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
            "redaction_tool": "x0t-redactor-test",
            "redaction_tool_version": "1",
            "redacted_fields": ["addresses", "hosts", "payloads", "headers"],
            "forbidden_raw_fields_absent": True,
            "raw_capture_retention_policy": "raw captures quarantined outside repository",
            "redacted_capture_sha256": _h("1"),
        },
        "repeatability_limits": {
            "sample_window_utc": "2026-05-22T00:00:00Z/2026-05-22T00:10:00Z",
            "sample_count": 6,
            "locations_count": 1,
            "networks_count": 1,
            "known_confounders": ["middlebox policy can change", "CDN routing can change"],
            "not_generalizable_beyond_environment": True,
            "refresh_after_utc": "2026-05-29T00:00:00Z",
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


def _dpi_proxy_claim_boundary() -> dict:
    return {
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
        "upgrade_rule": "Only bounded DPI/proxy evidence can raise DPI flags, never production flags.",
    }


def _sync_linked_json_artifacts(root: Path, proof, requirement, payload):
    for role, payload_key in requirement.get("json_artifact_payload_links", {}).items():
        _write_artifact_json(
            root,
            proof,
            _artifact_by_role(payload, role),
            payload[payload_key],
        )
    for role, payload_keys in requirement.get("json_artifact_object_field_links", {}).items():
        _write_artifact_json(
            root,
            proof,
            _artifact_by_role(payload, role),
            {key: payload[key] for key in payload_keys},
        )


def _write_candidate(root: Path, proof, requirement, rel_path: str):
    candidate = root / rel_path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    artifacts = []
    roles = requirement.get("required_artifact_roles")
    if roles:
        for role in roles:
            artifact_path = (
                root
                / "docs/verification/external-import-fixtures"
                / requirement["claim_id"]
                / f"{role}.txt"
            )
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                f"{requirement['claim_id']} {role} external import fixture\n",
                encoding="utf-8",
            )
            artifacts.append(
                {
                    "role": role,
                    "path": proof.display_path(root, artifact_path),
                    "sha256": proof.sha256_file(artifact_path),
                }
            )
    else:
        artifact_path = root / "docs/verification/external-import-fixtures" / f"{requirement['claim_id']}.txt"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{requirement['claim_id']} external import fixture\n", encoding="utf-8")
        artifacts.append(
            {
                "path": proof.display_path(root, artifact_path),
                "sha256": proof.sha256_file(artifact_path),
            }
        )
    measurements = {
        key: _measurement_value(expectation)
        for key, expectation in requirement["measurements"].items()
    }
    payload = {
        "schema": proof.EVIDENCE_SCHEMA,
        "claim_id": requirement["claim_id"],
        "status": "VERIFIED",
        "observed_at_utc": "2026-05-22T00:00:00Z",
        "simulated": False,
        "dry_run": False,
        "template": False,
        "commands": [
            {
                "args": ["external-import-fixture", requirement["claim_id"]],
                "exit_code": 0,
            }
        ],
        "artifacts": artifacts,
        "measurements": measurements,
    }
    if "json_artifact_payload_links" in requirement or "json_artifact_object_field_links" in requirement:
        payload["failures"] = []
        payload["claim_boundary"] = {
            f"{requirement['claim_id']}_verified": True,
        }
        payload["interface_scan"] = {
            "parse_status": "OK",
            "interface_count": 1,
            "interfaces": [measurements.get("interface", "recorded")],
            "xdp_interfaces": [{"ifname": measurements.get("interface", "recorded")}],
        }
        payload["candidate_audit"] = {
            "status": "HAS_ACCEPTED_CANDIDATE",
            "accepted": [],
            "candidates": [],
            "claim_boundary": "fixture only",
        }
        for payload_keys in requirement.get("json_artifact_object_field_links", {}).values():
            for key in payload_keys:
                payload.setdefault(key, {"fixture": requirement["claim_id"]})
    if requirement["claim_id"] == "dpi_lab":
        payload.update(_dpi_proxy_sections())
        payload.setdefault("claim_boundary", {})
        payload["claim_boundary"].update(_dpi_proxy_claim_boundary())
        _sync_dpi_proxy_integrity(root, payload)
    if "required_references" in requirement:
        requirements = {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}
        payload["references"] = []
        for claim_id in requirement["required_references"]:
            validation = proof.validate_external_evidence(root, requirements[claim_id])
            payload["references"].append(
                {
                    "claim_id": claim_id,
                    "status": validation["status"],
                    "evidence": validation["evidence"],
                    "sha256": validation["sha256"],
                }
            )
    _sync_linked_json_artifacts(root, proof, requirement, payload)
    if requirement["claim_id"] == "dpi_lab":
        _sync_dpi_proxy_integrity(root, payload)
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    return candidate


def _write_gap_audit(root: Path, claim_id: str = "dpi_lab") -> Path:
    scaffold = _load_script(
        f"scaffold_ghost_pulse_external_evidence_gaps_for_import_{claim_id}",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        f"audit_ghost_pulse_external_evidence_gaps_for_import_{claim_id}",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    scaffold.scaffold(root, [claim_id])
    report = audit.build_report(root, [claim_id])
    paths = audit.write_report_outputs(
        root,
        report,
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json",
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.md",
    )
    return paths["latest_json"]


def _write_fresh_import_preflight_reports(root: Path, claim_id: str = "dpi_lab") -> None:
    audit_path = _write_gap_audit(root, claim_id)
    scaffold = _load_script(
        f"scaffold_ghost_pulse_external_evidence_examples_for_import_{claim_id}",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    replacement = _load_script(
        f"verify_ghost_pulse_replacement_candidates_for_import_{claim_id}",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    intake = _load_script(
        f"verify_ghost_pulse_external_evidence_intake_for_import_{claim_id}",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    scaffold.write_incoming_examples(root, audit_payload.get("replacement_required", [claim_id]))
    replacement_report = replacement.build_report(root, audit_path)
    replacement_paths = replacement.write_report_outputs(
        root,
        replacement_report,
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md",
    )
    intake_report = intake.build_report(root, replacement_paths["latest_json"])
    intake.write_report_outputs(
        root,
        intake_report,
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md",
    )


def test_external_import_rejects_gap_record_candidate(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_reject",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_reject",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes((tmp_path / "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json").read_bytes())

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["written"] is False
    assert "dpi_lab: status must be VERIFIED" in report["failures"]
    assert report["requirement_contract"]["claim_id"] == "dpi_lab"
    assert report["destination_validation_before"]["status"] == "INVALID"


def test_external_import_rejects_unstaged_candidate_path_without_hashing(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_unstaged",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/import-candidates/dpi_lab.json")

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["candidate_sha256"] is None
    assert report["validation"] is None
    assert report["failures"] == [
        "candidate evidence must be staged at docs/verification/incoming/dpi_lab.json"
    ]


def test_external_import_rejects_candidate_directory_without_validation(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_candidate_directory",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    candidate.mkdir(parents=True)

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["candidate_sha256"] is None
    assert report["validation"] is None
    assert report["failures"] == [
        "candidate evidence is not a regular file: docs/verification/incoming/dpi_lab.json"
    ]


def test_external_import_rejects_candidate_symlink_without_hashing(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_candidate_symlink",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    target = tmp_path / "outside-candidate.json"
    target.write_text("{not json", encoding="utf-8")
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    candidate.parent.mkdir(parents=True)
    candidate.symlink_to(target)

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["candidate_exists"] is True
    assert report["candidate_is_file"] is True
    assert report["candidate_is_symlink"] is True
    assert report["candidate_sha256"] is None
    assert report["validation"] is None
    assert report["failures"] == [
        "candidate evidence must not be a symlink: docs/verification/incoming/dpi_lab.json"
    ]


def test_external_import_rejects_symlink_incoming_root_without_hashing(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_incoming_root_symlink",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    incoming_parent = tmp_path / "docs/verification"
    incoming_parent.mkdir(parents=True)
    target_dir = tmp_path / "external-incoming"
    target_dir.mkdir()
    candidate = incoming_parent / "incoming/dpi_lab.json"
    (target_dir / "dpi_lab.json").write_text("{not json", encoding="utf-8")
    (incoming_parent / "incoming").symlink_to(target_dir, target_is_directory=True)

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["incoming_root"]["is_symlink"] is True
    assert report["candidate_exists"] is True
    assert report["candidate_is_file"] is True
    assert report["candidate_is_symlink"] is False
    assert report["candidate_sha256"] is None
    assert report["validation"] is None
    assert report["failures"] == [
        "incoming evidence directory must not be a symlink: docs/verification/incoming"
    ]


def test_external_import_rejects_incoming_root_symlink_component_without_hashing(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_incoming_root_symlink_component",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    target_verification = tmp_path / "external-verification"
    target_verification.mkdir()
    verification = docs / "verification"
    verification.symlink_to(target_verification, target_is_directory=True)
    candidate = verification / "incoming/dpi_lab.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("{not json", encoding="utf-8")

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["incoming_root"]["is_symlink"] is False
    assert report["incoming_root"]["has_symlink_component"] is True
    assert report["incoming_root"]["symlink_component"] == "docs/verification"
    assert report["candidate_exists"] is True
    assert report["candidate_is_file"] is True
    assert report["candidate_is_symlink"] is False
    assert report["candidate_sha256"] is None
    assert report["validation"] is None
    assert report["failures"] == [
        "incoming evidence directory must not include symlink components: docs/verification"
    ]


def test_external_import_dry_run_does_not_replace_latest(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_dry_run",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_dry_run",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")

    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=False)

    latest = json.loads((tmp_path / requirement["path"]).read_text(encoding="utf-8"))
    assert report["decision"] == importer.DECISION_READY
    assert report["written"] is False
    assert report["requirement_contract"]["required_artifact_roles"] == requirement["required_artifact_roles"]
    assert report["external_dpi_proxy_validation"]["decision"] == importer.DECISION_READY
    claim_gate = report["external_dpi_intake_claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.external_dpi_intake.claim_gate.v1"
    assert claim_gate["local_import_preflight_claim_allowed"] is True
    assert claim_gate["candidate_ready_to_import_claim_allowed"] is True
    assert claim_gate["external_dpi_proxy_validator_ready_claim_allowed"] is True
    assert claim_gate["local_latest_evidence_copy_claim_allowed"] is False
    assert claim_gate["proof_gate_dpi_bypass_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert report["destination_validation_before"]["status"] == "INVALID"
    assert latest["status"] == "INCOMPLETE"


def test_external_import_rejects_dpi_lab_without_dpi_proxy_validator_readiness(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_dpi_proxy_reject",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_dpi_proxy_reject",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload.pop("artifact_identity")
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=False)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["validation"]["status"] == "VERIFIED"
    assert report["external_dpi_proxy_validation"]["decision"] == importer.DECISION_REJECTED
    assert report["external_dpi_intake_claim_gate"][
        "candidate_ready_to_import_claim_allowed"
    ] is False
    assert report["external_dpi_intake_claim_gate"][
        "external_dpi_proxy_validator_ready_claim_allowed"
    ] is False
    assert report["external_dpi_intake_claim_gate"][
        "validation_failures_present"
    ] is True
    assert report["external_dpi_intake_claim_gate"][
        "production_readiness_claim_allowed"
    ] is False
    assert (
        "dpi_lab: external DPI/proxy validator: artifact_identity section is required"
        in report["failures"]
    )


def test_external_import_write_requires_fresh_preflight_reports(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_write_freshness",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_write_freshness",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")

    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=True)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["written"] is False
    assert report["write_freshness"]["fresh"] is False
    assert any(
        failure.startswith("write freshness: replacement preflight: missing replacement candidate report")
        for failure in report["failures"]
    )
    assert any(
        failure.startswith("write freshness: external evidence intake: missing external evidence intake report")
        for failure in report["failures"]
    )
    assert report["external_dpi_intake_claim_gate"][
        "write_freshness_claim_allowed"
    ] is False


def test_external_import_write_rejects_stale_preflight_reports(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_write_stale",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_write_stale",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")
    _write_fresh_import_preflight_reports(tmp_path)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["environment"]["policy_context"] = "changed after saved preflight"
    _sync_dpi_proxy_integrity(tmp_path, payload)
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=True)

    assert report["decision"] == importer.DECISION_REJECTED
    assert report["write_freshness"]["fresh"] is False
    assert (
        "write freshness: replacement preflight: replacement candidate stable fields "
        "do not match current passport/candidate state"
    ) in report["failures"]
    assert any(
        "candidate sha256 must match current file" in failure
        for failure in report["failures"]
    )


def test_external_import_write_replaces_latest_and_writes_trace(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_write",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_write",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")
    _write_fresh_import_preflight_reports(tmp_path)
    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=True)

    paths = importer.write_import_outputs(tmp_path, report, candidate, tmp_path / requirement["path"])

    latest = json.loads((tmp_path / requirement["path"]).read_text(encoding="utf-8"))
    assert latest["status"] == "VERIFIED"
    assert report["external_dpi_proxy_validation"]["decision"] == importer.DECISION_READY
    assert report["write_freshness"]["fresh"] is True
    assert report["written"] is True
    assert report["external_dpi_intake_claim_gate"][
        "local_latest_evidence_copy_claim_allowed"
    ] is True
    assert report["external_dpi_intake_claim_gate"][
        "proof_gate_dpi_bypass_claim_allowed"
    ] is False
    assert report["external_dpi_intake_claim_gate"][
        "production_readiness_claim_allowed"
    ] is False
    assert report["destination_sha256_before"]
    assert report["destination_sha256_after"] == proof.sha256_file(tmp_path / requirement["path"])
    assert report["destination_validation_before"]["status"] == "INVALID"
    assert report["destination_validation_after"]["status"] == "VERIFIED"
    assert paths["bundle_report"].exists()
    assert paths["bundle_previous"].exists()
    assert paths["destination_md"].exists()
    assert "Validation status: `VERIFIED`" in paths["destination_md"].read_text(encoding="utf-8")


def test_external_import_write_rejects_bad_candidate_markdown_before_replacing_latest(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_import_bad_md",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_bad_md",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    destination = tmp_path / requirement["path"]
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")
    _write_fresh_import_preflight_reports(tmp_path)
    original_latest = destination.read_bytes()
    candidate_md = tmp_path / "docs/verification/import-candidates/dpi_lab.md"
    candidate_md.mkdir(parents=True)

    code = importer.main(
        [
            "--root",
            str(tmp_path),
            "--claim",
            "dpi_lab",
            "--candidate",
            str(candidate),
            "--candidate-md",
            str(candidate_md),
            "--write",
            "--json",
        ]
    )

    assert code == 1
    assert destination.read_bytes() == original_latest
    latest = json.loads(destination.read_text(encoding="utf-8"))
    assert latest["status"] == "INCOMPLETE"
    import_bundles = list((tmp_path / "docs/verification").glob("ghost-pulse-external-evidence-import-*"))
    assert import_bundles == []


def test_external_import_rejects_claim_mismatch(tmp_path):
    importer = _load_script(
        "import_ghost_pulse_external_evidence_mismatch",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    security_requirement = proof.EXTERNAL_REQUIREMENTS[5]
    candidate = _write_candidate(
        tmp_path,
        proof,
        security_requirement,
        "docs/verification/incoming/dpi_lab.json",
    )

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert "dpi_lab: claim_id must be dpi_lab" in report["failures"]
