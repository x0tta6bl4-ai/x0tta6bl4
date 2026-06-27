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
                / "docs/verification/external-intake-fixtures"
                / requirement["claim_id"]
                / f"{role}.txt"
            )
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                f"{requirement['claim_id']} {role} external evidence fixture\n",
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
        artifact_path = root / "docs/verification/external-intake-fixtures" / f"{requirement['claim_id']}.txt"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{requirement['claim_id']} external evidence fixture\n", encoding="utf-8")
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
    commands = [{"args": ["external-fixture", requirement["claim_id"]], "exit_code": 0}]
    if "required_commands" in requirement:
        commands = [
            {
                "args": [
                    measurements[part[1:-1]]
                    if isinstance(part, str) and part.startswith("<") and part.endswith(">")
                    else part
                    for part in template
                ],
                "exit_code": 0,
            }
            for template in requirement["required_commands"]
        ]
    payload = {
        "schema": proof.EVIDENCE_SCHEMA,
        "claim_id": requirement["claim_id"],
        "status": "VERIFIED",
        "observed_at_utc": "2026-05-22T00:00:00Z",
        "simulated": False,
        "dry_run": False,
        "template": False,
        "commands": commands,
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
    if "required_references" in requirement:
        requirements = {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}
        references = []
        for claim_id in requirement["required_references"]:
            validation = proof.validate_external_evidence(root, requirements[claim_id])
            references.append(
                {
                    "claim_id": claim_id,
                    "status": validation["status"],
                    "evidence": validation["evidence"],
                    "sha256": validation["sha256"],
                }
            )
        payload["references"] = references
    _sync_linked_json_artifacts(root, proof, requirement, payload)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    return evidence_path


def test_external_evidence_intake_fails_on_gap_records(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_intake",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )

    scaffold.scaffold(tmp_path, ["dpi_lab"])

    report = verifier.build_report(tmp_path, ["dpi_lab"])

    assert report["status"] == "FAIL"
    assert report["rows"][0]["status"] == "INVALID"
    assert "dpi_lab: status must be VERIFIED" in report["failures"]


def test_external_evidence_intake_passes_complete_fixture(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_fixture",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )
    proof = verifier.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    _write_external_evidence(tmp_path, proof, requirement)

    report = verifier.build_report(tmp_path, ["dpi_lab"])

    assert report["status"] == "PASS"
    assert report["failures"] == []
    assert report["rows"][0]["claim_id"] == "dpi_lab"
    assert report["rows"][0]["status"] == "VERIFIED"


def test_external_evidence_intake_rejects_kernel_attach_without_required_commands(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_kernel_commands",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )
    proof = verifier.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["commands"] = [{"args": ["external-fixture", "kernel_attach"], "exit_code": 0}]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = verifier.build_report(tmp_path, ["kernel_attach"])

    assert report["status"] == "FAIL"
    assert "kernel_attach: required command not observed: bpftool prog show" in report["failures"]


def test_external_evidence_intake_rejects_dpi_lab_without_required_artifact_roles(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_dpi_artifact_roles",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )
    proof = verifier.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"] = payload["artifacts"][:1]
    payload["artifacts"][0].pop("role")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = verifier.build_report(tmp_path, ["dpi_lab"])

    assert report["status"] == "FAIL"
    assert "dpi_lab: artifacts[0].role is required" in report["failures"]
    assert "dpi_lab: required artifact role missing: lab_scope" in report["failures"]


def test_external_evidence_intake_rejects_production_readiness_without_references(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_production_refs",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )
    proof = verifier.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[-1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload.pop("references")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    report = verifier.build_report(tmp_path, ["production_readiness"])

    assert report["status"] == "FAIL"
    assert "production_readiness: references must be a non-empty list" in report["failures"]


def test_external_evidence_intake_reports_unknown_claim(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_external_evidence_unknown",
        "scripts/ops/verify_ghost_pulse_external_evidence.py",
    )

    report = verifier.build_report(tmp_path, ["unknown_claim"])

    assert report["status"] == "FAIL"
    assert report["rows"] == []
    assert "unknown claim: unknown_claim" in report["failures"]
