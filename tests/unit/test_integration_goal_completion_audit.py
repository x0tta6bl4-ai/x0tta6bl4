import json
from pathlib import Path

from src.integration import goal_completion_audit


def test_goal_completion_audit_wraps_objective_coverage_report(monkeypatch, tmp_path):
    def fake_build_report(root: Path) -> dict:
        assert root == tmp_path
        return {
            "schema_version": "x0tta6bl4-integration-spine-objective-coverage-audit-v4-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "next_actions": [{"id": "submit_external_settlement_receipt", "status": "OPERATOR_INPUT_REQUIRED"}],
            "summary": {"coverage_rows_blocking": 1},
        }

    monkeypatch.setattr(goal_completion_audit, "build_coverage_report", fake_build_report)

    report = goal_completion_audit.build_report(tmp_path)

    assert report["schema_version"] == "x0tta6bl4-integration-spine-goal-completion-audit-v2-repo-generated"
    assert report["source_schema_version"] == "x0tta6bl4-integration-spine-objective-coverage-audit-v4-repo-generated"
    assert report["compatibility_alias_for"] == "integration-spine-objective-coverage-audit-current"
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["next_actions"][0]["status"] == "OPERATOR_INPUT_REQUIRED"


def test_goal_completion_audit_cli_returns_two_when_not_complete(monkeypatch, tmp_path):
    def fake_build_report(root: Path) -> dict:
        return {
            "schema_version": "x0tta6bl4-integration-spine-objective-coverage-audit-v4-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "next_actions": [],
            "summary": {},
        }

    output = tmp_path / "goal-completion.json"
    monkeypatch.setattr(goal_completion_audit, "build_coverage_report", fake_build_report)

    exit_code = goal_completion_audit.main(
        ["--root", str(tmp_path), "--output-json", str(output), "--require-complete"]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["schema_version"] == "x0tta6bl4-integration-spine-goal-completion-audit-v2-repo-generated"
    assert payload["completion_decision"] == "NOT_COMPLETE"
