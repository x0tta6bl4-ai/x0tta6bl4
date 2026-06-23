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


def _write_gap_audit(root: Path, claim_id: str = "dpi_lab") -> Path:
    scaffold = _load_script(
        f"scaffold_ghost_pulse_external_evidence_gaps_for_replacement_candidates_{claim_id}",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit = _load_script(
        f"audit_ghost_pulse_external_evidence_gaps_for_replacement_candidates_{claim_id}",
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


def _write_candidate(root: Path, proof, requirement):
    candidate = root / "docs/verification/incoming" / f"{requirement['claim_id']}.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for role in requirement.get("required_artifact_roles", []):
        artifact_path = (
            root
            / "docs/verification/replacement-candidate-fixtures"
            / requirement["claim_id"]
            / f"{role}.txt"
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            f"{requirement['claim_id']} {role} replacement candidate fixture\n",
            encoding="utf-8",
        )
        artifacts.append(
            {
                "role": role,
                "path": proof.display_path(root, artifact_path),
                "sha256": proof.sha256_file(artifact_path),
            }
        )
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
                "args": ["replacement-candidate-fixture", requirement["claim_id"]],
                "exit_code": 0,
            }
        ],
        "artifacts": artifacts,
        "measurements": {
            key: _measurement_value(expectation)
            for key, expectation in requirement["measurements"].items()
        },
    }
    if "json_artifact_payload_links" in requirement or "json_artifact_object_field_links" in requirement:
        payload["failures"] = []
        payload["claim_boundary"] = {
            f"{requirement['claim_id']}_verified": True,
        }
        payload["interface_scan"] = {
            "parse_status": "OK",
            "interface_count": 1,
            "interfaces": [payload["measurements"].get("interface", "recorded")],
            "xdp_interfaces": [{"ifname": payload["measurements"].get("interface", "recorded")}],
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
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    return candidate


def test_replacement_candidates_reports_missing_incoming_candidate(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_missing",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_NOT_READY
    assert report["audit_sha256"] == verifier.sha256_file(audit_path)
    assert report["replacement_required"] == ["dpi_lab"]
    assert report["ready"] == []
    assert report["not_ready"] == ["dpi_lab"]
    assert report["missing_candidates"] == ["dpi_lab"]
    assert report["failures"] == []
    assert report["claim_boundary"]["stealth_verified"] is False
    assert report["candidate_intake_plan"]["status"] == "ACTION_REQUIRED"
    assert report["candidate_intake_plan"]["ready_claims"] == []
    assert report["candidate_intake_plan"]["not_ready_claims"] == ["dpi_lab"]
    assert report["candidate_intake_plan"]["missing_candidate_paths"] == [
        "docs/verification/incoming/dpi_lab.json"
    ]
    assert report["candidate_intake_plan"]["currently_ready_write_commands"] == []
    assert report["candidate_intake_plan"]["write_commands_after_ready"] == [
        [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            "docs/verification/incoming/dpi_lab.json",
            "--write",
            "--json",
        ]
    ]
    assert report["candidate_intake_plan"]["post_import_refresh_commands"] == verifier.refresh_command_sequence()
    row = report["rows"][0]
    assert row["claim_id"] == "dpi_lab"
    assert row["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert row["candidate_exists"] is False
    assert row["candidate_is_file"] is False
    assert row["candidate_is_symlink"] is False
    assert row["candidate_example_path"] == "docs/verification/incoming/examples/dpi_lab.example.json"
    assert row["incoming_example_command"] == [
        "python3",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        "--examples-only",
    ]
    assert row["passport_current_status"] == "INVALID"
    assert row["passport_current_sha256"]
    assert row["passport_blocking_categories"]
    assert row["import_decision"] == "REJECTED"
    assert row["ready_to_import"] is False
    assert row["failures"] == [
        "candidate evidence is missing: docs/verification/incoming/dpi_lab.json"
    ]
    assert row["read_only_import_report"]["decision"] == "REJECTED"
    assert row["read_only_import_report"]["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert row["read_only_import_report"]["written"] is False
    assert row["read_only_import_report"]["claim_boundary"]["stealth_verified"] is False
    assert row["read_only_import_report"]["destination_validation_before"]["status"] == "INVALID"
    assert row["read_only_import_report"]["validation"] is None


def test_replacement_candidates_accepts_ready_incoming_candidate(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_ready",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_replacement_candidates_ready",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    audit_path = _write_gap_audit(tmp_path)
    candidate = _write_candidate(tmp_path, proof, requirement)

    report = verifier.build_report(tmp_path, audit_path)

    assert candidate.exists()
    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_READY
    assert report["ready"] == ["dpi_lab"]
    assert report["not_ready"] == []
    assert report["missing_candidates"] == []
    assert report["candidate_intake_plan"]["status"] == "READY_TO_IMPORT"
    assert report["candidate_intake_plan"]["ready_claims"] == ["dpi_lab"]
    assert report["candidate_intake_plan"]["not_ready_claims"] == []
    assert report["candidate_intake_plan"]["missing_candidate_paths"] == []
    assert report["candidate_intake_plan"]["currently_ready_write_commands"] == [
        [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            "docs/verification/incoming/dpi_lab.json",
            "--write",
            "--json",
        ]
    ]
    row = report["rows"][0]
    assert row["candidate_exists"] is True
    assert row["candidate_is_file"] is True
    assert row["candidate_is_symlink"] is False
    assert row["candidate_sha256"] == proof.sha256_file(candidate)
    assert row["import_decision"] == "READY_TO_IMPORT"
    assert row["ready_to_import"] is True
    assert row["validation_status"] == "VERIFIED"
    assert row["failures"] == []
    assert row["read_only_import_report"]["decision"] == "READY_TO_IMPORT"
    assert row["read_only_import_report"]["candidate_sha256"] == proof.sha256_file(candidate)
    assert row["read_only_import_report"]["written"] is False
    assert row["read_only_import_report"]["validation"]["status"] == "VERIFIED"
    assert row["read_only_import_report"]["claim_boundary"]["production_ready"] is False


def test_replacement_candidates_rejects_invalid_passport(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_invalid_passport",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    payload.pop("replacement_passport")
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == verifier.DECISION_PASSPORT_INVALID
    assert "gap audit: replacement_passport must be an object" in report["failures"]
    assert report["rows"] == []


def test_replacement_candidates_reports_unsafe_symlink_candidate(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_symlink_candidate",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    target = tmp_path / "outside-candidate.json"
    target.write_text("{not json", encoding="utf-8")
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    candidate.parent.mkdir(parents=True)
    candidate.symlink_to(target)

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_NOT_READY
    assert report["missing_candidates"] == []
    assert report["non_file_candidates"] == []
    assert report["unsafe_candidates"] == ["dpi_lab"]
    row = report["rows"][0]
    assert row["candidate_exists"] is True
    assert row["candidate_is_file"] is True
    assert row["candidate_is_symlink"] is True
    assert row["candidate_sha256"] is None
    assert row["validation_status"] is None
    assert row["failures"] == [
        "candidate evidence must not be a symlink: docs/verification/incoming/dpi_lab.json"
    ]


def test_replacement_candidates_reports_unsafe_symlink_incoming_root(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_symlink_incoming_root",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    incoming_parent = tmp_path / "docs/verification"
    target_dir = tmp_path / "external-incoming"
    target_dir.mkdir()
    incoming = incoming_parent / "incoming"
    if incoming.exists():
        incoming.rmdir()
    incoming.symlink_to(target_dir, target_is_directory=True)
    (target_dir / "dpi_lab.json").write_text("{not json", encoding="utf-8")

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_NOT_READY
    assert report["missing_candidates"] == []
    assert report["non_file_candidates"] == []
    assert report["unsafe_candidates"] == ["dpi_lab"]
    row = report["rows"][0]
    assert row["incoming_root"]["is_symlink"] is True
    assert row["candidate_exists"] is True
    assert row["candidate_is_file"] is True
    assert row["candidate_is_symlink"] is False
    assert row["candidate_sha256"] is None
    assert row["validation_status"] is None
    assert row["failures"] == [
        "incoming evidence directory must not be a symlink: docs/verification/incoming"
    ]


def test_replacement_candidates_reports_unsafe_incoming_root_symlink_component(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_symlink_component",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    docs = tmp_path / "docs"
    verification = docs / "verification"
    target_verification = tmp_path / "external-verification"
    docs.mkdir()
    target_verification.mkdir()
    verification.symlink_to(target_verification, target_is_directory=True)
    candidate = verification / "incoming/dpi_lab.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("{not json", encoding="utf-8")

    row = verifier.row_for_passport_claim(
        tmp_path,
        verifier.load_importer(tmp_path),
        {
            "claim_id": "dpi_lab",
            "candidate_path": "docs/verification/incoming/dpi_lab.json",
        },
    )

    assert row["incoming_root"]["is_symlink"] is False
    assert row["incoming_root"]["has_symlink_component"] is True
    assert row["incoming_root"]["symlink_component"] == "docs/verification"
    assert row["candidate_exists"] is True
    assert row["candidate_is_file"] is True
    assert row["candidate_is_symlink"] is False
    assert row["candidate_sha256"] is None
    assert row["validation_status"] is None
    assert row["failures"] == [
        "incoming evidence directory must not include symlink components: docs/verification"
    ]


def test_replacement_candidates_reports_non_file_incoming_candidate(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_non_file_candidate",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    candidate.mkdir(parents=True)

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_NOT_READY
    assert report["missing_candidates"] == []
    assert report["non_file_candidates"] == ["dpi_lab"]
    assert report["unsafe_candidates"] == []
    row = report["rows"][0]
    assert row["candidate_exists"] is True
    assert row["candidate_is_file"] is False
    assert row["candidate_is_symlink"] is False
    assert row["candidate_sha256"] is None
    assert row["validation_status"] is None
    assert row["failures"] == [
        "candidate evidence is not a regular file: docs/verification/incoming/dpi_lab.json"
    ]


def test_replacement_candidates_rejects_directory_audit_path(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_directory_audit",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
    audit_path.mkdir(parents=True)

    report = verifier.build_report(tmp_path, audit_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == verifier.DECISION_PASSPORT_INVALID
    assert report["audit_sha256"] is None
    assert report["failures"] == [
        "gap audit is not a regular file: "
        "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json"
    ]
    assert report["rows"] == []


def test_replacement_candidates_writes_and_verifies_latest_bundle(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_write_bundle",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    report = verifier.build_report(tmp_path, audit_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md"

    paths = verifier.write_report_outputs(tmp_path, report, output_json, output_md)
    failures = verifier.verify_saved_report(paths["latest_json"], tmp_path)

    assert failures == []
    assert paths["bundle_dir"].name.startswith("ghost-pulse-replacement-candidates-")
    assert paths["bundle_json"].read_text(encoding="utf-8") == paths["latest_json"].read_text(encoding="utf-8")
    assert paths["bundle_md"].read_text(encoding="utf-8") == paths["latest_md"].read_text(encoding="utf-8")
    assert list(paths["latest_json"].parent.glob(".*.tmp")) == []
    assert list(paths["bundle_json"].parent.glob(".*.tmp")) == []
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert saved["artifacts"]["preflight_latest_json"] == (
        "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    )
    assert saved["audit_sha256"] == verifier.sha256_file(audit_path)
    assert saved["decision"] == verifier.DECISION_NOT_READY


def test_replacement_candidates_saved_report_rejects_directory_report_path(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_directory_report",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    report_path = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    report_path.mkdir(parents=True)

    failures = verifier.verify_saved_report(report_path, tmp_path)

    assert failures == [
        "replacement candidate report is not a regular file: "
        "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    ]


def test_replacement_candidates_saved_report_rejects_directory_artifact_path(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_directory_artifact",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    report = verifier.build_report(tmp_path, audit_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md"
    paths = verifier.write_report_outputs(tmp_path, report, output_json, output_md)
    directory_artifact = tmp_path / "docs/verification/directory-artifact.json"
    directory_artifact.mkdir()
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    saved["artifacts"]["preflight_bundle_json"] = verifier.display_path(tmp_path, directory_artifact)
    paths["latest_json"].write_text(json.dumps(saved, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_saved_report(paths["latest_json"], tmp_path)

    assert "preflight latest JSON does not match bundle JSON" in failures


def test_replacement_candidates_saved_report_detects_stale_candidates(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_stale_bundle",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_replacement_candidates_stale",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    audit_path = _write_gap_audit(tmp_path)
    report = verifier.build_report(tmp_path, audit_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md"
    paths = verifier.write_report_outputs(tmp_path, report, output_json, output_md)

    _write_candidate(tmp_path, proof, requirement)
    failures = verifier.verify_saved_report(paths["latest_json"], tmp_path)

    assert "replacement candidate stable fields do not match current passport/candidate state" in failures


def _write_replacement_preflight(root: Path, audit_path: Path):
    verifier = _load_script(
        "verify_ghost_pulse_replacement_candidates_for_intake_preflight",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    )
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_intake_preflight",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    scaffold.write_incoming_examples(root, audit_payload.get("replacement_required", []))
    report = verifier.build_report(root, audit_path)
    output_json = root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    output_md = root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md"
    paths = verifier.write_report_outputs(root, report, output_json, output_md)
    return verifier, paths["latest_json"]


def test_external_evidence_intake_reports_action_required_from_preflight(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_action_required",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)

    report = intake.build_report(tmp_path, preflight_path)

    assert report["status"] == "PASS"
    assert report["decision"] == intake.DECISION_ACTION_REQUIRED
    assert report["replacement_required"] == ["dpi_lab"]
    assert report["ready"] == []
    assert report["not_ready"] == ["dpi_lab"]
    assert report["missing_candidate_paths"] == ["docs/verification/incoming/dpi_lab.json"]
    assert report["incoming_examples_manifest"] == "docs/verification/incoming/examples/manifest.json"
    assert report["incoming_examples_verification"]["status"] == "PASS"
    assert report["incoming_examples_verification"]["example_count"] == 1
    assert report["incoming_examples_verification"]["collection_task_count"] == 1
    assert report["incoming_examples_verification"]["collection_tasks"][0]["claim_id"] == "dpi_lab"
    assert report["incoming_examples_verification"]["collection_tasks"][0]["required_measurements"] == {
        "authorized_lab": True,
        "baseline_detected_or_blocked": True,
        "dpi_bypass_verified": True,
        "pulse_result_recorded": True,
    }
    assert report["currently_ready_write_commands"] == []
    assert report["write_commands_after_ready"] == [
        [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            "docs/verification/incoming/dpi_lab.json",
            "--write",
            "--json",
        ]
    ]
    assert len(report["post_import_refresh_commands"]) == 9
    assert report["post_import_refresh_commands"][-1] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
        "--write-report",
        "--json",
    ]
    assert report["collection_tasks_verification"] == {"status": "PASS", "failures": []}
    assert report["collection_tasks"] == [
        {
            "claim_id": "dpi_lab",
            "status": "MISSING_CANDIDATE",
            "candidate": "docs/verification/incoming/dpi_lab.json",
            "candidate_exists": False,
            "candidate_is_file": False,
            "candidate_is_symlink": False,
            "candidate_sha256": None,
            "example": "docs/verification/incoming/examples/dpi_lab.example.json",
            "title": "Authorized DPI lab result",
            "artifact_root": "docs/verification/incoming/artifacts/dpi_lab",
            "required_artifact_roles": [
                "lab_scope",
                "baseline_result",
                "pulse_result",
                "lab_conclusion",
            ],
            "required_measurements": {
                "authorized_lab": True,
                "baseline_detected_or_blocked": True,
                "dpi_bypass_verified": True,
                "pulse_result_recorded": True,
            },
            "required_commands": [],
            "required_references": [],
            "read_only_import_command": [
                "python3",
                "scripts/ops/import_ghost_pulse_external_evidence.py",
                "--claim",
                "dpi_lab",
                "--candidate",
                "docs/verification/incoming/dpi_lab.json",
                "--require-ready",
                "--json",
            ],
            "write_import_command": [
                "python3",
                "scripts/ops/import_ghost_pulse_external_evidence.py",
                "--claim",
                "dpi_lab",
                "--candidate",
                "docs/verification/incoming/dpi_lab.json",
                "--write",
                "--json",
            ],
            "acceptance_commands": [
                [
                    "python3",
                    "scripts/ops/verify_ghost_pulse_external_evidence.py",
                    "--claim",
                    "dpi_lab",
                    "--require-pass",
                    "--json",
                ]
            ],
            "ready_to_import": False,
            "import_decision": "REJECTED",
            "validation_status": None,
            "failures": [
                "candidate evidence is missing: docs/verification/incoming/dpi_lab.json"
            ],
            "blocking_reasons": [
                "candidate_file_missing",
                "preflight_failures_present",
            ],
        }
    ]
    assert report["claim_boundary"]["stealth_verified"] is False
    assert report["claim_boundary"]["kernel_attach_verified"] is False


def test_external_evidence_intake_reports_ready_not_written(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_ready",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_intake_ready",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    audit_path = _write_gap_audit(tmp_path)
    _write_candidate(tmp_path, proof, requirement)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)

    report = intake.build_report(tmp_path, preflight_path)

    assert report["status"] == "PASS"
    assert report["decision"] == intake.DECISION_READY_NOT_WRITTEN
    assert report["ready"] == ["dpi_lab"]
    assert report["not_ready"] == []
    assert report["missing_candidate_paths"] == []
    assert report["incoming_examples_verification"]["status"] == "PASS"
    assert report["collection_tasks"][0]["status"] == "READY_TO_IMPORT"
    assert report["collection_tasks"][0]["ready_to_import"] is True
    assert report["collection_tasks"][0]["blocking_reasons"] == []
    assert report["currently_ready_write_commands"] == [
        [
            "python3",
            "scripts/ops/import_ghost_pulse_external_evidence.py",
            "--claim",
            "dpi_lab",
            "--candidate",
            "docs/verification/incoming/dpi_lab.json",
            "--write",
            "--json",
        ]
    ]
    assert report["claim_boundary"]["production_ready"] is False


def test_external_evidence_intake_writes_and_verifies_latest_bundle(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_write_bundle",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)
    report = intake.build_report(tmp_path, preflight_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md"

    paths = intake.write_report_outputs(tmp_path, report, output_json, output_md)
    failures = intake.verify_saved_report(paths["latest_json"], tmp_path)

    assert failures == []
    assert paths["bundle_dir"].name.startswith("ghost-pulse-external-evidence-intake-")
    assert paths["bundle_json"].read_text(encoding="utf-8") == paths["latest_json"].read_text(encoding="utf-8")
    assert paths["bundle_md"].read_text(encoding="utf-8") == paths["latest_md"].read_text(encoding="utf-8")
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert saved["artifacts"]["intake_latest_json"] == (
        "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    )
    assert saved["decision"] == intake.DECISION_ACTION_REQUIRED


def test_external_evidence_intake_saved_report_detects_stale_preflight(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_stale_preflight",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_intake_stale_preflight",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )
    proof = importer.load_proof_gate(tmp_path)
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    audit_path = _write_gap_audit(tmp_path)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)
    report = intake.build_report(tmp_path, preflight_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md"
    paths = intake.write_report_outputs(tmp_path, report, output_json, output_md)

    _write_candidate(tmp_path, proof, requirement)
    failures = intake.verify_saved_report(paths["latest_json"], tmp_path)

    assert (
        "external evidence intake stable fields do not match current replacement preflight/incoming examples state"
        in failures
    )


def test_external_evidence_intake_saved_report_detects_stale_examples_manifest(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_stale_examples",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)
    report = intake.build_report(tmp_path, preflight_path)
    output_json = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md"
    paths = intake.write_report_outputs(tmp_path, report, output_json, output_md)

    manifest_path = tmp_path / "docs/verification/incoming/examples/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "VERIFIED"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    failures = intake.verify_saved_report(paths["latest_json"], tmp_path)

    assert (
        "external evidence intake stable fields do not match current replacement preflight/incoming examples state"
        in failures
    )


def test_external_evidence_intake_rejects_stale_collection_task(tmp_path):
    intake = _load_script(
        "verify_ghost_pulse_external_evidence_intake_stale_task",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    )
    audit_path = _write_gap_audit(tmp_path)
    _, preflight_path = _write_replacement_preflight(tmp_path, audit_path)
    manifest_path = tmp_path / "docs/verification/incoming/examples/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["collection_tasks"][0]["candidate"] = "docs/verification/incoming/wrong.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    report = intake.build_report(tmp_path, preflight_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == intake.DECISION_PREFLIGHT_INVALID
    assert (
        "incoming examples: dpi_lab: collection task candidate path must be "
        "docs/verification/incoming/dpi_lab.json"
    ) in report["failures"]
