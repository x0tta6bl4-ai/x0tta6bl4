import json
from pathlib import Path

from src.integration.x0t_governance_execute_handoff import build_report, main, render_markdown


OPERATOR_ENTRYPOINTS = [
    "scripts/ops/check_x0t_governance_execute_readiness.py",
    "execute_dao_proposal.py",
    "src/integration/completion_audit.py",
    "src/integration/production_gap_index.py",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_operator_entrypoints(root: Path) -> None:
    for rel in OPERATOR_ENTRYPOINTS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test entrypoint\n", encoding="utf-8")


def _readiness(path: Path, *, decision: str = "NOT_READY_TIMELOCK_ACTIVE", executed: bool = False) -> Path:
    _write_operator_entrypoints(path.parent)
    ready = decision == "READY_TO_EXECUTE"
    vetoed = decision == "VETOED_NOT_EXECUTABLE"
    not_executable = decision == "NOT_READY_STATE_NOT_EXECUTABLE"
    state_label = (
        "Executed"
        if executed
        else "Vetoed"
        if vetoed
        else "Defeated"
        if not_executable
        else "Ready"
        if ready
        else "Queued"
    )
    state_code = 6 if executed else 7 if vetoed else 2 if not_executable else 5 if ready else 4
    queued = state_label == "Queued"
    seconds_until_ready = 0 if ready or executed or vetoed or decision == "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED" else 1200
    _write_json(
        path,
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-readiness-v2",
            "generated_at": "2026-05-21T01:00:00Z",
            "status": "VERIFIED HERE",
            "ok": True,
            "chain": {"name": "base-sepolia", "chain_id": 84532},
            "governance_contract": "0xf1B0086962e41710968D81F099c8ced23b97D2d2",
            "proposal_id": 1,
            "proposal_state": {
                "state_code": state_code,
                "state_label": state_label,
                "queued": queued,
                "executed": executed,
                "vetoed": vetoed,
            },
            "timelock": {
                "earliest_execution_time_utc": "2026-05-21T04:45:22Z",
                "seconds_until_earliest_execution_by_block_time": seconds_until_ready,
            },
            "decision": "ALREADY_EXECUTED" if executed else decision,
            "summary": {
                "execute_ready_now": ready,
                "proposal_queued": queued,
                "proposal_executed": executed,
                "proposal_vetoed": vetoed,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
                "safe_to_retry_readiness_check": not executed,
            },
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
        },
    )
    return path


def test_handoff_blocks_until_readiness_is_ready(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json")

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")
    rerun = next(action for action in report["operator_next_actions"] if action["id"] == "rerun_completion_and_gap")

    assert report["schema_version"].endswith("v2-repo-generated")
    assert report["status"] == "VERIFIED HERE"
    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    assert report["handoff_actionable"] is True
    assert report["ready_for_operator_execute"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_chain"] is False
    assert report["submits_transaction"] is False
    assert report["runs_live_rpc"] is False
    assert report["summary"]["readiness_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert report["summary"]["approval_value_required"] == "execute-proposal-1-base-sepolia"
    assert report["summary"]["operator_actions_total"] == 5
    assert report["summary"]["operator_commands_total"] == 5
    assert report["summary"]["operator_command_entrypoints_missing"] == 0
    assert report["summary"]["operator_command_surface_ready"] is True
    assert report["summary"]["operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["operator_command_shell_surface_ready"] is True
    assert report["summary"]["operator_sequence_ready"] is True
    assert report["missing_inputs"][0]["id"] == "ready_execute_state"
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0
    assert report["operator_next_actions"][2]["submits_transaction"] is True
    assert 'PRIVATE_KEY="$PRIVATE_KEY"' in report["operator_next_actions"][2]["command"]
    assert "PRIVATE_KEY=..." not in report["operator_next_actions"][2]["command"]
    assert all(
        check["shell_redirection_placeholder_detected"] is False
        for check in report["operator_command_checks"]
    )
    assert any("completion_audit" in command and "--output-md" in command for command in rerun["commands"])
    assert any("production_gap_index" in command and "--output-md" in command for command in rerun["commands"])


def test_handoff_is_ready_only_with_ready_readiness_and_preserves_approval_boundary(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", decision="READY_TO_EXECUTE")

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")
    markdown = render_markdown(report)

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
    assert report["decision"] == "READY_FOR_OPERATOR_EXECUTE"
    assert report["ready_for_operator_execute"] is True
    assert report["approval_boundary"]["approval_env"] == "X0T_EXECUTE_PROPOSAL_APPROVAL"
    assert report["approval_boundary"]["expected_value"] == "execute-proposal-1-base-sepolia"
    assert report["approval_boundary"]["can_submit_without_operator_approval"] is False
    assert {item["id"] for item in report["missing_inputs"]} == {
        "explicit_operator_approval",
        "operator_private_key",
    }
    missing_statuses = {item["id"]: item["status"] for item in report["missing_inputs"]}
    assert missing_statuses["explicit_operator_approval"] == "OPERATOR_APPROVAL_REQUIRED"
    assert missing_statuses["operator_private_key"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["missing_inputs_operator_approval_required"] == 1
    assert report["summary"]["missing_inputs_operator_input_required"] == 1
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0
    assert "X0T_EXECUTE_PROPOSAL_APPROVAL" in markdown
    assert "python3 execute_dao_proposal.py --dry-run" in markdown
    assert 'PRIVATE_KEY="$PRIVATE_KEY"' in markdown
    assert "Operator Command Surface" in markdown
    assert "shell redirection placeholders: `0`" in markdown


def test_handoff_blocks_when_operator_command_entrypoint_is_missing(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", decision="READY_TO_EXECUTE")
    (tmp_path / "src/integration/production_gap_index.py").unlink()

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_OPERATOR_COMMANDS"
    assert report["handoff_actionable"] is False
    assert report["ready_for_operator_execute"] is False
    assert report["summary"]["operator_command_surface_ready"] is False
    assert report["summary"]["operator_command_entrypoints_missing"] == 1
    assert report["missing_inputs"][0]["id"] == "operator_command_entrypoints"
    assert "src/integration/production_gap_index.py" in report["missing_inputs"][0]["missing_entrypoints"]


def test_handoff_blocks_shell_redirection_style_operator_placeholders(tmp_path, monkeypatch):
    readiness = _readiness(tmp_path / "readiness.json", decision="READY_TO_EXECUTE")
    monkeypatch.setattr(
        "src.integration.x0t_governance_execute_handoff.PRIVATE_KEY_ENV_ASSIGNMENT",
        "PRIVATE_KEY=<operator-key>",
    )

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_OPERATOR_COMMANDS"
    assert report["handoff_actionable"] is False
    assert report["ready_for_operator_execute"] is False
    assert report["summary"]["operator_commands_with_shell_redirection_placeholders"] == 1
    assert report["summary"]["operator_command_shell_surface_ready"] is False
    assert report["summary"]["operator_sequence_ready"] is False
    assert report["missing_inputs"][0]["id"] == "operator_command_shell_placeholders"
    assert "PRIVATE_KEY=<operator-key>" in report["missing_inputs"][0]["shell_redirection_placeholders"]


def test_handoff_handles_already_executed_readiness_without_execute_prompt(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", executed=True)

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
    assert report["already_executed"] is True
    assert report["ready_for_operator_execute"] is False
    assert report["missing_inputs"] == []
    assert report["summary"]["proposal_executed"] is True


def test_handoff_reports_terminal_vetoed_state_without_wait_prompt(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", decision="VETOED_NOT_EXECUTABLE")

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    assert report["ready_for_operator_execute"] is False
    assert report["summary"]["proposal_vetoed"] is True
    assert report["summary"]["readiness_decision"] == "VETOED_NOT_EXECUTABLE"
    assert [item["id"] for item in report["missing_inputs"]] == ["terminal_vetoed_state"]
    assert report["missing_inputs"][0]["status"] == "TERMINAL_CHAIN_STATE"


def test_handoff_reports_after_timelock_refresh_requirement(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", decision="QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED")

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    assert report["ready_for_operator_execute"] is False
    assert report["summary"]["readiness_decision"] == "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED"
    assert report["summary"]["seconds_until_earliest_execution_by_block_time"] == 0
    assert [item["id"] for item in report["missing_inputs"]] == ["refresh_after_timelock_state"]
    assert report["missing_inputs"][0]["status"] == "READINESS_REFRESH_REQUIRED"


def test_handoff_reports_non_executable_chain_state_without_wait_prompt(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json", decision="NOT_READY_STATE_NOT_EXECUTABLE")

    report = build_report(tmp_path, readiness, readiness_display="readiness.json")

    assert report["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    assert report["ready_for_operator_execute"] is False
    assert report["summary"]["readiness_decision"] == "NOT_READY_STATE_NOT_EXECUTABLE"
    assert [item["id"] for item in report["missing_inputs"]] == ["not_executable_chain_state"]
    assert report["missing_inputs"][0]["status"] == "CHAIN_STATE_NOT_EXECUTABLE"


def test_handoff_cli_require_ready_fails_closed_when_not_ready(tmp_path):
    readiness = _readiness(tmp_path / "readiness.json")
    output_json = tmp_path / "handoff.json"
    output_md = tmp_path / "handoff.md"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--readiness-json",
            str(readiness),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--require-ready",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["handoff_actionable"] is True
    assert payload["ready_for_operator_execute"] is False
    assert output_md.exists()


def test_handoff_cli_require_actionable_rejects_missing_readiness(tmp_path):
    _write_operator_entrypoints(tmp_path)
    output_json = tmp_path / "handoff.json"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--readiness-json",
            "missing.json",
            "--output-json",
            str(output_json),
            "--require-actionable",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["handoff_decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_INVALID_READINESS"
    assert payload["handoff_actionable"] is False
    assert payload["source_errors"]
