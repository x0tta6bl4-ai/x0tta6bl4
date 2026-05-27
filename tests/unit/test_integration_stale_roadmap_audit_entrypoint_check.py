import json
from pathlib import Path

from src.integration.stale_roadmap_audit_entrypoint_check import build_report, classify_entrypoint, main


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# placeholder\n", encoding="utf-8")


def test_stale_roadmap_audit_entrypoint_check_passes_when_references_exist(tmp_path):
    _touch(tmp_path, "scripts/ops/existing.py")
    _touch(tmp_path, "tests/unit/scripts/test_existing.py")
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {
            "steps": [
                "python3 scripts/ops/existing.py --output json",
                "python3 -m pytest tests/unit/scripts/test_existing.py",
            ]
        },
    )

    report = build_report(tmp_path, [".tmp/validation-shards/audit.json"])

    assert report["decision"] == "ENTRYPOINTS_CLEAR"
    assert report["ready"] is True
    assert report["triage_ready"] is True
    assert report["summary"]["entrypoints_seen_total"] == 2
    assert report["summary"]["entrypoints_missing_total"] == 0
    assert report["mutates_files"] is False
    assert report["contacts_live_systems"] is False


def test_stale_roadmap_audit_entrypoint_check_reports_missing_scripts_and_tests(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {
            "command": "python3 scripts/ops/missing.py && python3 scripts/ops/missing.py",
            "tests": ["python3 -m pytest tests/unit/scripts/test_missing.py"],
        },
    )

    report = build_report(tmp_path, [".tmp/validation-shards/audit.json"])

    assert report["decision"] == "STALE_AUDIT_ENTRYPOINTS_MISSING"
    assert report["ready"] is False
    assert report["triage_ready"] is False
    assert report["entrypoints_missing"] == [
        "scripts/ops/missing.py",
        "tests/unit/scripts/test_missing.py",
    ]
    assert report["summary"]["entrypoints_missing_total"] == 2
    assert report["summary"]["missing_entrypoint_triage_counts"] == {
        "legacy_unit_test_for_missing_surface": 1,
        "unclassified_missing_entrypoint": 1,
    }
    artifact = report["artifacts"][0]
    assert artifact["references"]["scripts/ops/missing.py"] == ["$.command", "$.command"]


def test_stale_roadmap_audit_entrypoint_check_classifies_current_replacements_and_legacy_surfaces(tmp_path):
    for path in (
        "scripts/ops/generate_production_raw_evidence_template_pack.py",
        "scripts/ops/run_integration_spine_completion_gate.py",
        "scripts/ops/run_production_raw_evidence_pipeline.py",
        "scripts/ops/run_integration_spine_production_input_pipeline.py",
        "src/integration/production_raw_evidence_pipeline.py",
        "src/integration/production_input_pipeline.py",
        "src/integration/completion_gate_runner.py",
        "src/integration/production_gap_index.py",
        "docs/verification/x0tta6bl4-active-goal-gap-audit-2026-05-20.md",
    ):
        _touch(tmp_path, path)
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {
            "commands": [
                "python3 scripts/ops/audit_goal_completion.py --output json",
                "python3 scripts/ops/collect_live005_client_matrix_evidence.py --output json",
                "python3 scripts/ops/render_spb_operator_next_steps.py --output json",
                "bash scripts/ops/restore_critical_payloads.sh host",
                "python3 scripts/ops/audit_horizon2_rag_rfc_gate.py --output json",
            ]
        },
    )

    report = build_report(tmp_path, [".tmp/validation-shards/audit.json"])

    assert report["decision"] == "STALE_AUDIT_ENTRYPOINTS_TRIAGED"
    assert report["ready"] is False
    assert report["triage_ready"] is True
    assert report["summary"]["missing_entrypoint_triage_counts"] == {
        "external_live_prereq": 1,
        "horizon2_guard_blocked_by_current_v1_1_gaps": 1,
        "legacy_live_validation_surface": 1,
        "legacy_spb_validation_surface": 1,
        "mapped_to_current_surface": 1,
    }
    assert report["summary"]["missing_entrypoints_mapped_to_current_surface"] == 1
    assert report["summary"]["missing_entrypoints_legacy_live_or_spb"] == 2
    assert report["summary"]["missing_entrypoints_external_live_prereq"] == 1
    assert report["summary"]["missing_entrypoints_unclassified"] == 0
    assert report["summary"]["current_entrypoint_targets_missing_total"] == 0


def test_stale_roadmap_audit_entrypoint_check_blocks_triage_when_replacement_targets_are_missing(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {"command": "python3 scripts/ops/audit_goal_completion.py --output json"},
    )

    report = build_report(tmp_path, [".tmp/validation-shards/audit.json"])

    assert report["decision"] == "STALE_AUDIT_ENTRYPOINTS_MISSING"
    assert report["ready"] is False
    assert report["triage_ready"] is False
    assert report["summary"]["missing_entrypoints_unclassified"] == 0
    assert report["summary"]["current_entrypoint_targets_missing_total"] == 3
    assert report["current_entrypoint_targets_missing"] == [
        "scripts/ops/run_integration_spine_completion_gate.py",
        "src/integration/completion_gate_runner.py",
        "src/integration/production_gap_index.py",
    ]


def test_classify_entrypoint_returns_current_surface_for_roadmap_completion_audit():
    result = classify_entrypoint("scripts/ops/audit_roadmap_execution_completion.py")

    assert result["triage_status"] == "mapped_to_current_surface"
    assert "src/integration/completion_gate_runner.py" in result["current_entrypoints"]


def test_stale_roadmap_audit_entrypoint_check_cli_require_clear_returns_two_when_blocked(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {"command": "python3 scripts/ops/missing.py"},
    )
    output_json = tmp_path / "entrypoints.json"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--artifact",
            ".tmp/validation-shards/audit.json",
            "--output-json",
            str(output_json),
            "--require-clear",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["decision"] == "STALE_AUDIT_ENTRYPOINTS_MISSING"
    assert payload["summary"]["entrypoints_missing_total"] == 1


def test_stale_roadmap_audit_entrypoint_check_cli_require_triaged_allows_classified_stale_refs(tmp_path):
    _touch(tmp_path, "src/integration/completion_gate_runner.py")
    _touch(tmp_path, "src/integration/production_gap_index.py")
    _touch(tmp_path, "scripts/ops/run_integration_spine_completion_gate.py")
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {"command": "python3 scripts/ops/audit_goal_completion.py --output json"},
    )
    output_json = tmp_path / "entrypoints.json"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--artifact",
            ".tmp/validation-shards/audit.json",
            "--output-json",
            str(output_json),
            "--require-triaged",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["decision"] == "STALE_AUDIT_ENTRYPOINTS_TRIAGED"
    assert payload["ready"] is False
    assert payload["triage_ready"] is True


def test_stale_roadmap_audit_entrypoint_check_cli_require_triaged_fails_unclassified_refs(tmp_path):
    _write_json(
        tmp_path,
        ".tmp/validation-shards/audit.json",
        {"command": "python3 scripts/ops/missing.py"},
    )

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--artifact",
            ".tmp/validation-shards/audit.json",
            "--require-triaged",
        ]
    )

    assert exit_code == 2
