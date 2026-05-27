import importlib.util
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


def _write_external_evidence(root: Path, proof, requirement):
    evidence_path = root / requirement["path"]
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = []
    roles = requirement.get("required_artifact_roles")
    if roles:
        for role in roles:
            artifact_path = (
                root
                / "docs/verification/external-gap-audit-fixtures"
                / requirement["claim_id"]
                / f"{role}.txt"
            )
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                f"{requirement['claim_id']} {role} external gap audit fixture\n",
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
        artifact_path = root / "docs/verification/external-gap-audit-fixtures" / f"{requirement['claim_id']}.txt"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{requirement['claim_id']} external gap audit fixture\n", encoding="utf-8")
        artifacts.append(
            {
                "path": proof.display_path(root, artifact_path),
                "sha256": proof.sha256_file(artifact_path),
            }
        )
    measurements = {}
    for key, expectation in requirement["measurements"].items():
        if expectation == "nonempty":
            measurements[key] = "recorded"
        elif expectation == "positive_int":
            measurements[key] = 3
        elif expectation == "sha256":
            measurements[key] = "a" * 64
        elif expectation == "bool_true":
            measurements[key] = True
        else:
            measurements[key] = expectation
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
                "args": ["external-gap-audit-fixture", requirement["claim_id"]],
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
    _sync_linked_json_artifacts(root, proof, requirement, payload)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")


def test_gap_audit_reports_gap_record_as_action_required(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_gap_audit",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    scaffold.scaffold(tmp_path, ["dpi_lab"])

    report = audit.build_report(tmp_path, ["dpi_lab"])

    assert report["status"] == audit.STATUS_ACTION_REQUIRED
    assert report["replacement_required"] == ["dpi_lab"]
    row = report["rows"][0]
    assert row["status"] == "INVALID"
    assert row["replacement_required"] is True
    assert "authorized lab identity and scope" in row["missing_inputs"]
    assert "dpi_lab: status must be VERIFIED" in report["failures"]
    assert row["blocking_audit"]["status"] == "BLOCKED"
    assert row["blocking_audit"]["blocking_categories"] == [
        "artifact_roles",
        "measurements",
        "missing_inputs",
        "proof_errors",
        "record",
    ]
    assert row["blocking_audit"]["categories"]["artifact_roles"]["missing_roles"] == [
        "lab_scope",
        "baseline_result",
        "pulse_result",
        "lab_conclusion",
    ]
    assert row["record_audit"]["status"] == "FAIL"
    assert row["record_audit"]["observed"]["status"] == "INCOMPLETE"
    assert row["record_audit"]["observed"]["flags"] == {
        "simulated": False,
        "dry_run": False,
        "template": False,
    }
    assert row["record_audit"]["observed"]["gap_record_markers"] == {
        "mode": "EXTERNAL_EVIDENCE_GAP_RECORD",
        "missing_inputs_present": True,
        "failures_present": True,
        "claim_boundary_claim_verified_false": True,
    }
    assert "mode must not be EXTERNAL_EVIDENCE_GAP_RECORD" in row["record_audit"]["failures"]
    assert row["measurement_audit"][0]["status"] == "FAIL"
    assert row["command_audit"]["status"] == "NOT_REQUIRED"
    assert row["command_audit"]["required_commands"] == []
    assert row["command_audit"]["missing_commands"] == []
    assert row["command_audit"]["failed_commands"] == []
    assert row["artifact_file_audit"]["status"] == "PASS"
    assert row["artifact_file_audit"]["malformed_artifact_indexes"] == []
    assert row["artifact_file_audit"]["artifacts"][0]["sha256_matches"] is True
    assert row["artifact_role_audit"]["status"] == "FAIL"
    assert row["artifact_role_audit"]["missing_roles"] == [
        "lab_scope",
        "baseline_result",
        "pulse_result",
        "lab_conclusion",
    ]
    assert row["artifact_role_audit"]["observed_roles"] == [
        scaffold.GAP_ARTIFACT_ROLE,
    ]
    assert row["artifact_role_audit"]["artifacts_without_role"] == []
    assert row["artifact_role_audit"]["duplicate_roles"] == []
    assert row["artifact_role_audit"]["required_roles_without_path"] == []
    assert row["artifact_role_audit"]["reused_required_paths"] == []
    assert row["artifact_role_audit"]["path_scope_errors"] == []
    assert row["gap_record_role_audit"] == {
        "status": "PASS",
        "expected_gap_artifact_role": "evidence_gap_record",
        "observed_gap_artifact_role": "evidence_gap_record",
        "observed_roles": ["evidence_gap_record"],
        "required_roles": [
            "lab_scope",
            "baseline_result",
            "pulse_result",
            "lab_conclusion",
        ],
        "declared_required_roles_on_gap_record": [],
        "failures": [],
    }
    assert row["reference_audit"]["status"] == "NOT_REQUIRED"
    assert row["replacement_contract"]["claim_id"] == "dpi_lab"
    assert row["replacement_contract"]["destination"] == "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
    assert row["replacement_contract"]["required_status"] == "VERIFIED"
    assert row["replacement_contract"]["required_flags"] == {
        "simulated": False,
        "dry_run": False,
        "template": False,
    }
    assert row["replacement_contract"]["required_artifact_roles"] == [
        "lab_scope",
        "baseline_result",
        "pulse_result",
        "lab_conclusion",
    ]
    assert row["replacement_contract"]["acceptance_commands"][0] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--require-pass",
        "--json",
    ]
    passport = report["replacement_passport"]
    assert passport["schema"] == audit.REPLACEMENT_PASSPORT_SCHEMA
    assert passport["status"] == audit.REPLACEMENT_PASSPORT_ACTION_REQUIRED
    assert passport["claim_boundary"]["stealth_verified"] is False
    assert passport["claim_boundary"]["whitelist_verified"] is False
    assert passport["claim_boundary"]["kernel_attach_verified"] is False
    assert passport["claim_boundary"]["production_ready"] is False
    assert [claim["claim_id"] for claim in passport["claims"]] == ["dpi_lab"]
    passport_claim = passport["claims"][0]
    assert passport_claim["destination"] == "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
    assert passport_claim["current_status"] == row["status"]
    assert passport_claim["current_sha256"] == row["sha256"]
    assert passport_claim["blocking_categories"] == row["blocking_audit"]["blocking_categories"]
    assert passport_claim["replacement_contract"] == row["replacement_contract"]
    assert passport_claim["candidate_path"] == "docs/verification/incoming/dpi_lab.json"
    assert passport_claim["candidate_example_path"] == (
        "docs/verification/incoming/examples/dpi_lab.example.json"
    )
    assert passport_claim["incoming_example_command"] == [
        "python3",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        "--examples-only",
    ]
    assert passport_claim["read_only_import_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    assert passport_claim["write_import_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--write",
        "--json",
    ]
    assert passport_claim["acceptance_commands"] == row["replacement_contract"]["acceptance_commands"]
    assert report["claim_boundary"]["stealth_verified"] is False


def test_gap_audit_passes_complete_external_fixture(tmp_path):
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_fixture",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    proof = audit.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    _write_external_evidence(tmp_path, proof, requirement)

    report = audit.build_report(tmp_path, ["dpi_lab"])

    assert report["status"] == audit.STATUS_ALL_VERIFIED
    assert report["replacement_required"] == []
    assert report["failures"] == []
    assert report["rows"][0]["status"] == "VERIFIED"
    assert report["rows"][0]["blocking_audit"] == {
        "status": "CLEAR",
        "blocking_categories": [],
        "categories": {},
    }
    assert report["rows"][0]["record_audit"]["status"] == "PASS"
    assert report["rows"][0]["record_audit"]["failures"] == []
    assert all(item["status"] == "PASS" for item in report["rows"][0]["measurement_audit"])
    assert report["rows"][0]["command_audit"]["status"] == "NOT_REQUIRED"
    assert report["rows"][0]["artifact_file_audit"]["status"] == "PASS"
    assert report["rows"][0]["artifact_role_audit"]["status"] == "PASS"
    assert report["rows"][0]["artifact_role_audit"]["missing_roles"] == []
    assert report["rows"][0]["artifact_role_audit"]["duplicate_roles"] == []
    assert report["rows"][0]["artifact_role_audit"]["reused_required_paths"] == []
    assert report["rows"][0]["artifact_role_audit"]["path_scope_errors"] == []
    assert report["rows"][0]["gap_record_role_audit"]["status"] == "NOT_APPLICABLE"
    assert report["rows"][0]["gap_record_role_audit"]["failures"] == []
    assert report["rows"][0]["reference_audit"]["status"] == "NOT_REQUIRED"
    assert report["replacement_passport"]["status"] == audit.REPLACEMENT_PASSPORT_ALL_REPLACED
    assert report["replacement_passport"]["claims"] == []


def test_gap_audit_reports_gap_record_role_masking(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_gap_role_masking",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_gap_role_masking",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    scaffold.scaffold(tmp_path, ["dpi_lab"])
    latest = tmp_path / "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["artifacts"].append(dict(payload["artifacts"][0], role="lab_scope"))
    latest.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.build_report(tmp_path, ["dpi_lab"])

    row = report["rows"][0]
    gap_roles = row["gap_record_role_audit"]
    assert "gap_record_roles" in row["blocking_audit"]["blocking_categories"]
    assert gap_roles["status"] == "FAIL"
    assert gap_roles["declared_required_roles_on_gap_record"] == ["lab_scope"]
    assert "gap record must not declare proof-gate required artifact roles" in gap_roles["failures"]


def test_gap_audit_reports_required_command_gaps(tmp_path):
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_command_gaps",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    proof = audit.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = tmp_path / requirement["path"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["commands"] = [
        {"args": ["uname", "-r"], "exit_code": 0},
        {"args": ["ip", "-j", "link", "show", "recorded"], "exit_code": 0},
        {"args": ["bpftool", "prog", "show"], "exit_code": 1},
        {"args": [], "exit_code": 0},
    ]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.build_report(tmp_path, ["kernel_attach"])

    command_audit = report["rows"][0]["command_audit"]
    assert "commands" in report["rows"][0]["blocking_audit"]["blocking_categories"]
    assert report["rows"][0]["blocking_audit"]["categories"]["commands"]["failed_commands"] == [
        {
            "index": 2,
            "args": ["bpftool", "prog", "show"],
            "exit_code": 1,
        }
    ]
    assert command_audit["status"] == "FAIL"
    assert command_audit["required_commands"][0] == ["uname", "-r"]
    assert ["ip", "-d", "-j", "link", "show", "recorded"] in command_audit["missing_commands"]
    assert ["bpftool", "net"] in command_audit["missing_commands"]
    assert command_audit["failed_commands"] == [
        {
            "index": 2,
            "args": ["bpftool", "prog", "show"],
            "exit_code": 1,
        }
    ]
    assert command_audit["commands_without_args"] == [3]


def test_gap_audit_reports_artifact_file_anomalies(tmp_path):
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_artifact_file_anomalies",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    proof = audit.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = tmp_path / requirement["path"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["sha256"] = "0" * 64
    payload["artifacts"][1]["path"] = "docs/verification/external-gap-audit-fixtures/missing.pcap"
    payload["artifacts"][1]["sha256"] = "1" * 64
    payload["artifacts"][2]["path"] = "/tmp/outside.pcap"
    payload["artifacts"].append("not-an-artifact-object")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.build_report(tmp_path, ["packet_capture"])

    file_audit = report["rows"][0]["artifact_file_audit"]
    assert "artifact_files" in report["rows"][0]["blocking_audit"]["blocking_categories"]
    assert file_audit["status"] == "FAIL"
    assert file_audit["malformed_artifact_indexes"] == [5]
    assert file_audit["artifacts"][0]["exists"] is True
    assert file_audit["artifacts"][0]["sha256_matches"] is False
    assert file_audit["artifacts"][1]["exists"] is False
    assert file_audit["artifacts"][1]["sha256_matches"] is False
    assert file_audit["artifacts"][2]["exists"] is None
    assert file_audit["artifacts"][2]["path_errors"] == [
        "artifact path must be repo-relative: /tmp/outside.pcap",
    ]


def test_gap_audit_reports_symlink_artifact_path_as_blocker(tmp_path):
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_symlink_artifact",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    proof = audit.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = tmp_path / requirement["path"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    target_path = tmp_path / payload["artifacts"][0]["path"]
    symlink_path = tmp_path / "docs/verification/external-gap-audit-fixtures/sender-pcap-symlink.pcap"
    symlink_path.symlink_to(target_path)
    symlink_rel = proof.display_path(tmp_path, symlink_path)
    payload["artifacts"][0]["path"] = symlink_rel
    payload["artifacts"][0]["sha256"] = proof.sha256_file(target_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.build_report(tmp_path, ["packet_capture"])

    row = report["rows"][0]
    file_audit = row["artifact_file_audit"]
    role_audit = row["artifact_role_audit"]
    symlink_error = f"artifact path must not include symlink components: {symlink_rel}"
    assert "artifact_files" in row["blocking_audit"]["blocking_categories"]
    assert "artifact_roles" in row["blocking_audit"]["blocking_categories"]
    assert file_audit["status"] == "FAIL"
    assert file_audit["artifacts"][0]["exists"] is None
    assert file_audit["artifacts"][0]["actual_sha256"] is None
    assert file_audit["artifacts"][0]["path_errors"] == [symlink_error]
    assert role_audit["status"] == "FAIL"
    assert role_audit["path_scope_errors"] == [
        {
            "artifact_index": 0,
            "path": symlink_rel,
            "error": symlink_error,
        }
    ]


def test_gap_audit_reports_artifact_role_and_path_anomalies(tmp_path):
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_artifact_anomalies",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    proof = audit.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = tmp_path / requirement["path"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    outside = tmp_path / "outside-artifact.txt"
    outside.write_text("outside artifact\n", encoding="utf-8")
    payload["artifacts"][1]["role"] = "sender_pcap"
    payload["artifacts"][2]["path"] = proof.display_path(tmp_path, outside)
    payload["artifacts"][2]["sha256"] = proof.sha256_file(outside)
    payload["artifacts"][3]["path"] = payload["artifacts"][0]["path"]
    payload["artifacts"][3]["sha256"] = payload["artifacts"][0]["sha256"]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.build_report(tmp_path, ["packet_capture"])

    role_audit = report["rows"][0]["artifact_role_audit"]
    assert role_audit["status"] == "FAIL"
    assert role_audit["duplicate_roles"] == ["sender_pcap"]
    assert role_audit["missing_roles"] == ["receiver_pcap"]
    assert role_audit["reused_required_paths"] == [
        {
            "path": payload["artifacts"][0]["path"],
            "first_role": "sender_pcap",
            "second_role": "receiver_events",
        }
    ]
    assert role_audit["path_scope_errors"] == [
        {
            "artifact_index": 2,
            "path": "outside-artifact.txt",
            "error": "artifact path must stay under docs/verification: outside-artifact.txt",
        }
    ]


def test_gap_audit_reports_missing_production_readiness_references(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_gap_audit_production",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_production",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    scaffold.scaffold(tmp_path, ["production_readiness"])

    report = audit.build_report(tmp_path, ["production_readiness"])

    row = report["rows"][0]
    reference_audit = row["reference_audit"]
    assert "references" in row["blocking_audit"]["blocking_categories"]
    assert "kernel_attach" in row["blocking_audit"]["categories"]["references"]["unverified_claims"]
    assert reference_audit["status"] == "FAIL"
    assert reference_audit["missing_claims"] == [
        "kernel_attach",
        "packet_capture",
        "baseline_timing_comparison",
        "dpi_lab",
        "whitelist_lab",
        "security_review",
    ]
    assert reference_audit["observed_claims"] == []
    assert "kernel_attach" in reference_audit["unverified_claims"]
    assert row["replacement_contract"]["required_references"] == [
        "kernel_attach",
        "packet_capture",
        "baseline_timing_comparison",
        "dpi_lab",
        "whitelist_lab",
        "security_review",
    ]
    assert row["replacement_contract"]["acceptance_commands"][1] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
        "--require-all-proven",
        "--json",
    ]


def test_gap_audit_writes_latest_and_bundle_outputs(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_gap_audit_write",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        "audit_ghost_pulse_external_evidence_gaps_write",
        "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    )
    scaffold.scaffold(tmp_path, ["security_review"])
    report = audit.build_report(tmp_path, ["security_review"])

    paths = audit.write_report_outputs(
        tmp_path,
        report,
        tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json",
        tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.md",
    )

    assert paths["latest_json"].exists()
    assert paths["latest_md"].exists()
    assert paths["bundle_json"].exists()
    assert paths["bundle_md"].exists()
    assert paths["latest_json"].read_text(encoding="utf-8") == paths["bundle_json"].read_text(encoding="utf-8")
    assert list(paths["latest_json"].parent.glob(".*.tmp")) == []
    assert list(paths["bundle_json"].parent.glob(".*.tmp")) == []
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert payload["schema"] == audit.SCHEMA
    assert payload["replacement_required"] == ["security_review"]
