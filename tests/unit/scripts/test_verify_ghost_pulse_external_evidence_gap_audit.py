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


def _write_gap_audit(root: Path, claim_id: str = "dpi_lab") -> Path:
    scaffold = _load_script(
        f"scaffold_ghost_pulse_external_evidence_gaps_for_gap_audit_verify_{claim_id}",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        f"audit_ghost_pulse_external_evidence_gaps_for_verify_{claim_id}",
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


def test_gap_audit_verifier_accepts_current_gap_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert failures == []


def test_gap_audit_verifier_rejects_stale_replacement_list(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_stale",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["replacement_required"] = []
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "replacement_required does not match non-VERIFIED rows" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_promoted_claim_boundary(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_boundary",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["claim_boundary"]["stealth_verified"] = True
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "claim_boundary.stealth_verified must be false" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_bundle_mismatch(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_bundle",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path, "security_review")
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    bundle_json = tmp_path / payload["artifacts"]["audit_bundle_json"]
    bundle_json.write_text("{}", encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "audit latest JSON does not match bundle JSON" in failures


def test_gap_audit_verifier_rejects_missing_artifact_role_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_roles",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("artifact_role_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: artifact_role_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_blocking_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_blocking",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("blocking_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: blocking_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_cleared_non_verified_blocking_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_blocking_clear",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["blocking_audit"] = {
        "status": "CLEAR",
        "blocking_categories": [],
        "categories": {},
    }
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: non-VERIFIED row blocking_audit must be BLOCKED" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_record_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_record",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("record_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: record_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_record_audit_marker_object(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_record_marker",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["record_audit"]["observed"].pop("gap_record_markers")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: record_audit.observed.gap_record_markers must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_command_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_commands",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("command_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: command_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_command_audit_field(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_command_field",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["command_audit"].pop("missing_commands")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: command_audit.missing_commands must be a list" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_artifact_file_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_files",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("artifact_file_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: artifact_file_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_artifact_file_audit_list(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_file_list",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["artifact_file_audit"].pop("artifacts")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: artifact_file_audit.artifacts must be a list" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_artifact_role_anomaly_field(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_role_anomaly_field",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["artifact_role_audit"].pop("path_scope_errors")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: artifact_role_audit.path_scope_errors must be a list" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_gap_record_role_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_gap_role",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("gap_record_role_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: gap_record_role_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_gap_record_role_audit_missing_list(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_gap_role_list",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["gap_record_role_audit"].pop("declared_required_roles_on_gap_record")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert (
        "dpi_lab: gap_record_role_audit.declared_required_roles_on_gap_record must be a list"
        in failures
    )
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_reference_audit(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_reference",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("reference_audit")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: reference_audit must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_replacement_contract(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_contract",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0].pop("replacement_contract")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: replacement_contract must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_missing_replacement_passport(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_passport",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload.pop("replacement_passport")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "replacement_passport must be an object" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_drifted_replacement_contract(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_contract_drift",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["rows"][0]["replacement_contract"]["required_artifact_roles"] = []
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: replacement_contract does not match proof-gate contract" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_drifted_replacement_passport_command(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_passport_command_drift",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["replacement_passport"]["claims"][0]["read_only_import_command"] = ["python3", "unexpected.py"]
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: replacement_passport.read_only_import_command does not match audit row" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_drifted_replacement_passport_example_path(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_passport_example_drift",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["replacement_passport"]["claims"][0]["candidate_example_path"] = (
        "docs/verification/incoming/examples/unexpected.example.json"
    )
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: replacement_passport.candidate_example_path does not match audit row" in failures
    assert "audit stable fields do not match current external evidence state" in failures


def test_gap_audit_verifier_rejects_drifted_replacement_passport_contract(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_gap_audit_passport_contract_drift",
        "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload["replacement_passport"]["claims"][0]["replacement_contract"]["required_artifact_roles"] = []
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_audit(audit_path, tmp_path)

    assert "dpi_lab: replacement_passport.replacement_contract does not match audit row" in failures
    assert "audit stable fields do not match current external evidence state" in failures
