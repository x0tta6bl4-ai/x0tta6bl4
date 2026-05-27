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


def test_external_gap_scaffold_writes_all_missing_claim_files(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )

    result = scaffold.scaffold(tmp_path, list(scaffold.CLAIM_GAPS))

    assert result["status"] == scaffold.STATUS_INCOMPLETE
    assert sorted(result["claims"]) == sorted(scaffold.CLAIM_GAPS)
    for claim_id, spec in scaffold.CLAIM_GAPS.items():
        latest = tmp_path / "docs" / "verification" / spec["latest_json"]
        latest_md = tmp_path / "docs" / "verification" / spec["latest_md"]
        assert latest.exists()
        assert latest_md.exists()
        payload = json.loads(latest.read_text(encoding="utf-8"))
        assert payload["schema"] == scaffold.SCHEMA
        assert payload["claim_id"] == claim_id
        assert payload["status"] == scaffold.STATUS_INCOMPLETE
        assert payload["simulated"] is False
        assert payload["dry_run"] is False
        assert payload["template"] is False
        assert payload["commands"][0]["exit_code"] == 0
        assert payload["claim_boundary"]["claim_verified"] is False
        if claim_id == "production_readiness":
            assert payload["references"] == []
        assert payload["required_artifact_roles"] == spec["required_artifact_roles"]
        assert payload["gap_artifact_role"] == scaffold.GAP_ARTIFACT_ROLE
        for artifact in payload["artifacts"]:
            artifact_path = tmp_path / artifact["path"]
            assert artifact_path.exists()
            assert artifact["role"] == scaffold.GAP_ARTIFACT_ROLE
            assert artifact["sha256"] == scaffold.sha256_file(artifact_path)


def test_external_gap_scaffold_makes_missing_rows_invalid_not_missing(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_invalid",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    proof = _load_script(
        "run_ghost_pulse_proof_gate_for_external_gap_scaffold",
        "scripts/ops/run_ghost_pulse_proof_gate.py",
    )

    scaffold.scaffold(tmp_path, ["dpi_lab", "whitelist_lab", "security_review", "production_readiness"])

    rows = {
        requirement["claim_id"]: proof.validate_external_evidence(tmp_path, requirement)
        for requirement in proof.EXTERNAL_REQUIREMENTS
        if requirement["claim_id"] in scaffold.CLAIM_GAPS
    }

    assert all(row["status"] == "INVALID" for row in rows.values())
    assert "status must be VERIFIED" in rows["dpi_lab"]["errors"]
    assert "measurements.authorized_lab must be True" in rows["dpi_lab"]["errors"]
    assert "artifacts[0].role is required" not in rows["dpi_lab"]["errors"]
    assert "required artifact role missing: lab_scope" in rows["dpi_lab"]["errors"]
    assert "measurements.provider_profile must be nonempty" in rows["whitelist_lab"]["errors"]
    assert "measurements.reviewer must be nonempty" in rows["security_review"]["errors"]
    assert "measurements.production_ready must be bool_true" in rows["production_readiness"]["errors"]
    assert "references must be a non-empty list" in rows["production_readiness"]["errors"]


def test_external_gap_scaffold_writes_fail_closed_incoming_examples(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_examples",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_gap_examples",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )

    manifest = scaffold.write_incoming_examples(tmp_path, ["kernel_attach", "dpi_lab", "production_readiness"])

    assert manifest["schema"] == scaffold.INCOMING_EXAMPLE_MANIFEST_SCHEMA
    assert manifest["status"] == scaffold.INCOMING_EXAMPLE_STATUS
    assert manifest["claim_boundary"]["production_ready"] is False
    assert manifest["intake_gate"]["write_report_command"] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--write-report",
        "--json",
    ]
    assert manifest["intake_gate"]["require_all_ready_command"] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--require-all-ready",
        "--json",
    ]
    assert len(manifest["intake_gate"]["post_import_refresh_commands"]) == 9
    assert manifest["intake_gate"]["post_import_refresh_commands"][-1] == [
        "python3",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
        "--write-report",
        "--json",
    ]
    assert manifest["intake_gate"]["expected_current_decision_with_examples_only"] == (
        "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED"
    )
    assert (tmp_path / manifest["manifest"]).exists()
    assert (tmp_path / manifest["readme"]).exists()
    assert [row["claim_id"] for row in manifest["examples"]] == [
        "kernel_attach",
        "dpi_lab",
        "production_readiness",
    ]
    assert [row["claim_id"] for row in manifest["collection_tasks"]] == [
        "kernel_attach",
        "dpi_lab",
        "production_readiness",
    ]
    kernel_task = manifest["collection_tasks"][0]
    assert kernel_task["status"] == scaffold.COLLECTION_TASK_STATUS
    assert kernel_task["candidate"] == "docs/verification/incoming/kernel_attach.json"
    assert kernel_task["example"] == "docs/verification/incoming/examples/kernel_attach.example.json"
    assert kernel_task["artifact_root"] == "docs/verification/incoming/artifacts/kernel_attach"
    assert kernel_task["required_artifact_roles"] == [
        "kernel_commands",
        "kernel_measurements",
        "kernel_interface_scan",
        "kernel_candidate_audit",
    ]
    assert kernel_task["required_measurements"]["xdp_attached"] is True
    assert ["bpftool", "prog", "show"] in kernel_task["required_commands"]
    assert kernel_task["read_only_import_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "kernel_attach",
        "--candidate",
        "docs/verification/incoming/kernel_attach.json",
        "--require-ready",
        "--json",
    ]
    assert kernel_task["write_import_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "kernel_attach",
        "--candidate",
        "docs/verification/incoming/kernel_attach.json",
        "--write",
        "--json",
    ]

    dpi_example = tmp_path / "docs/verification/incoming/examples/dpi_lab.example.json"
    payload = json.loads(dpi_example.read_text(encoding="utf-8"))
    assert payload["schema"] == scaffold.SCHEMA
    assert payload["claim_id"] == "dpi_lab"
    assert payload["status"] == scaffold.STATUS_INCOMPLETE
    assert payload["template"] is True
    assert payload["mode"] == scaffold.INCOMING_EXAMPLE_MODE
    assert payload["candidate_destination"] == "docs/verification/incoming/dpi_lab.json"
    assert payload["artifacts"][0]["role"] == "lab_scope"
    assert payload["artifacts"][3]["role"] == "lab_conclusion"
    assert payload["artifacts"][3]["path"].endswith("lab_conclusion.REPLACE_WITH_REAL_JSON_FILE")
    assert payload["measurements"]["authorized_lab"] == "REPLACE_WITH_TRUE"
    assert payload["failures"] == [
        "incoming example is not evidence and must be rejected by proof gate"
    ]
    assert payload["requirement_contract"]["json_artifact_object_field_links"] == {
        "lab_conclusion": ["measurements", "failures", "claim_boundary"]
    }

    report = importer.build_report(tmp_path, "dpi_lab", dpi_example)
    assert report["decision"] == importer.DECISION_REJECTED
    assert report["failures"] == [
        "candidate evidence must be staged at docs/verification/incoming/dpi_lab.json"
    ]

    dpi_candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    dpi_candidate.write_bytes(dpi_example.read_bytes())
    report = importer.build_report(tmp_path, "dpi_lab", dpi_candidate)
    assert report["decision"] == importer.DECISION_REJECTED
    assert "dpi_lab: status must be VERIFIED" in report["failures"]
    assert "dpi_lab: template must be false" in report["failures"]
    assert "dpi_lab: failures must be absent or empty for VERIFIED evidence" in report["failures"]
    readme = (tmp_path / manifest["readme"]).read_text(encoding="utf-8")
    assert "## Intake Gate" in readme
    assert "## Collection Tasks" in readme
    assert "verify_ghost_pulse_external_evidence_intake.py --require-all-ready --json" in readme

    production_example = json.loads(
        (tmp_path / "docs/verification/incoming/examples/production_readiness.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert [row["claim_id"] for row in production_example["references"]] == [
        "kernel_attach",
        "packet_capture",
        "baseline_timing_comparison",
        "dpi_lab",
        "whitelist_lab",
        "security_review",
    ]


def test_external_gap_scaffold_writes_fail_closed_incoming_gap_candidates(tmp_path):
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_candidates",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    importer = _load_script(
        "import_ghost_pulse_external_evidence_for_gap_candidates",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
    )

    index = scaffold.write_incoming_gap_candidates(tmp_path, ["dpi_lab"])
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    payload = json.loads(candidate.read_text(encoding="utf-8"))

    assert index["schema"] == scaffold.INCOMING_GAP_CANDIDATE_SCHEMA
    assert index["status"] == scaffold.STATUS_INCOMPLETE
    assert index["candidates"]["dpi_lab"]["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert index["candidates"]["dpi_lab"]["expected_import_decision"] == "REJECTED"
    assert payload["schema"] == scaffold.SCHEMA
    assert payload["claim_id"] == "dpi_lab"
    assert payload["status"] == scaffold.STATUS_INCOMPLETE
    assert payload["template"] is False
    assert payload["mode"] == "EXTERNAL_EVIDENCE_GAP_RECORD"
    assert payload["claim_boundary"]["claim_verified"] is False

    report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["decision"] == importer.DECISION_REJECTED
    assert "dpi_lab: status must be VERIFIED" in report["failures"]
    assert "dpi_lab: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD" in report["failures"]
    assert "dpi_lab: measurements.authorized_lab must be True" in report["failures"]
