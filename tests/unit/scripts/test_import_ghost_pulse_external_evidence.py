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
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    return candidate


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
    assert report["destination_validation_before"]["status"] == "INVALID"
    assert latest["status"] == "INCOMPLETE"


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
    report = importer.build_report(tmp_path, "dpi_lab", candidate, write_requested=True)

    paths = importer.write_import_outputs(tmp_path, report, candidate, tmp_path / requirement["path"])

    latest = json.loads((tmp_path / requirement["path"]).read_text(encoding="utf-8"))
    assert latest["status"] == "VERIFIED"
    assert report["written"] is True
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
    original_latest = destination.read_bytes()
    candidate = _write_candidate(tmp_path, proof, requirement, "docs/verification/incoming/dpi_lab.json")
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
