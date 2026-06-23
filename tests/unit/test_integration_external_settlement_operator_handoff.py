import json
from pathlib import Path

from src.integration.external_settlement_operator_handoff import build_report, main


OPERATOR_ENTRYPOINTS = [
    "src/integration/external_settlement.py",
    "scripts/ops/verify_x0t_external_settlement_evidence.py",
    "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
    "scripts/ops/run_integration_spine_production_input_pipeline.py",
    "scripts/ops/run_integration_spine_completion_gate.py",
]


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_operator_entrypoints(root: Path) -> None:
    for rel in OPERATOR_ENTRYPOINTS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test entrypoint\n", encoding="utf-8")


def _base_sources(root: Path, *, ready: bool) -> None:
    _write_operator_entrypoints(root)
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-capture-preflight-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
            "summary": {
                "capture_inputs_ready": ready,
                "errors_total": 0 if ready else 3,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-evidence-gate-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "x0t_external_settlement_decision": "READY" if ready else "BLOCKED_ON_EVIDENCE",
            "summary": {
                "evidence_file_found": ready,
                "evidence_file_valid": ready,
                "x0t_external_settlement_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-live-rpc-gate-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "x0t_external_settlement_live_rpc_decision": "READY" if ready else "BLOCKED_ON_EVIDENCE",
            "summary": {
                "evidence_file_found": ready,
                "retained_evidence_ready": ready,
                "live_rpc_checked": ready,
                "x0t_external_settlement_live_rpc_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-current-blocker-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_PROMOTE" if ready else "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
            "summary": {
                "expected_evidence_file_exists": ready,
                "live_rpc_ready": ready,
                "x0t_external_settlement_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-import-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-evidence-import-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {"production_evidence_complete": ready},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-completion-gate-runner-v4-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "summary": {
                "external_settlement_ready": ready,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )


def test_operator_handoff_is_verified_but_blocked_without_settlement_evidence(tmp_path):
    _base_sources(tmp_path, ready=False)

    report = build_report(tmp_path)

    assert report["schema_version"].endswith("v6-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["ready_for_completion_rerun"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["capture_preflight_available"] is True
    assert report["summary"]["capture_preflight_decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert report["summary"]["capture_inputs_ready"] is False
    assert report["summary"]["evidence_file_ready"] is False
    assert report["summary"]["live_rpc_ready"] is False
    assert report["summary"]["production_import_external_settlement_ready"] is False
    assert report["summary"]["completion_gate_external_settlement_ready"] is False
    assert report["summary"]["missing_inputs_total"] == 5
    assert report["summary"]["operator_actions_total"] == 6
    assert report["summary"]["operator_commands_total"] == 5
    assert report["summary"]["operator_command_entrypoints_missing"] == 0
    assert report["summary"]["operator_command_surface_ready"] is True
    assert report["summary"]["operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["operator_command_shell_surface_ready"] is True
    assert report["summary"]["operator_sequence_ready"] is True
    assert report["summary"]["missing_inputs_operator_input_required"] == 5
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0
    assert {
        item["status"]
        for item in report["missing_inputs"]
    } == {"OPERATOR_INPUT_REQUIRED"}
    assert report["missing_inputs"][0]["id"] == "capture_input_preflight"
    assert report["operator_next_actions"][0]["id"] == "preflight_capture_inputs"
    assert report["operator_next_actions"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["operator_next_actions"][0]["runs_live_rpc"] is False
    assert report["operator_next_actions"][0]["writes_evidence"] is False
    assert report["operator_command_checks"][0]["expected_entrypoint"] == "src/integration/external_settlement.py"
    assert report["operator_command_checks"][0]["entrypoint_exists"] is True
    assert all(
        check["shell_redirection_placeholder_detected"] is False
        for check in report["operator_command_checks"]
    )
    live_rpc_action = next(
        action for action in report["operator_next_actions"] if action["id"] == "verify_live_base_rpc"
    )
    assert live_rpc_action["status"] == "OPERATOR_INPUT_REQUIRED"
    assert '"$X0T_BASE_RPC_URL"' in live_rpc_action["command"]
    assert "<base-rpc-url>" not in live_rpc_action["command"]
    assert ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json" in report["source_artifacts"]
    assert report["source_errors"] == []


def test_operator_handoff_can_be_ready_when_all_sources_are_ready(tmp_path):
    _base_sources(tmp_path, ready=True)

    report = build_report(tmp_path)

    assert report["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
    assert report["ready_for_completion_rerun"] is True
    assert report["summary"]["capture_preflight_decision"] == "CAPTURE_INPUTS_READY"
    assert report["summary"]["capture_inputs_ready"] is True
    assert report["summary"]["missing_inputs_total"] == 0
    assert report["summary"]["missing_inputs_operator_input_required"] == 0
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0
    assert report["summary"]["operator_command_surface_ready"] is True
    assert report["summary"]["operator_command_shell_surface_ready"] is True
    assert report["operator_next_actions"][0]["status"] == "DONE"


def test_operator_handoff_blocks_when_operator_command_entrypoint_is_missing(tmp_path):
    _base_sources(tmp_path, ready=True)
    (tmp_path / "scripts/ops/run_integration_spine_completion_gate.py").unlink()

    report = build_report(tmp_path)

    assert report["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["ready_for_completion_rerun"] is False
    assert report["summary"]["operator_command_surface_ready"] is False
    assert report["summary"]["operator_command_entrypoints_missing"] == 1
    assert report["missing_inputs"][0]["id"] == "operator_command_entrypoints"
    assert report["missing_inputs"][0]["status"] == "REPO_REQUIRED"
    assert "scripts/ops/run_integration_spine_completion_gate.py" in report["missing_inputs"][0]["missing_entrypoints"]
    missing_check = next(
        check
        for check in report["operator_command_checks"]
        if check["expected_entrypoint"] == "scripts/ops/run_integration_spine_completion_gate.py"
    )
    assert missing_check["status"] == "MISSING_LOCAL_ENTRYPOINT"


def test_operator_handoff_blocks_shell_redirection_style_operator_placeholders(tmp_path, monkeypatch):
    _base_sources(tmp_path, ready=True)
    monkeypatch.setattr(
        "src.integration.external_settlement_operator_handoff.VERIFY_LIVE_RPC_COMMAND",
        "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready --rpc-url <base-rpc-url>",
    )

    report = build_report(tmp_path)

    assert report["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["ready_for_completion_rerun"] is False
    assert report["summary"]["operator_commands_with_shell_redirection_placeholders"] == 1
    assert report["summary"]["operator_command_shell_surface_ready"] is False
    assert report["summary"]["operator_sequence_ready"] is False
    assert report["missing_inputs"][0]["id"] == "operator_command_shell_placeholders"
    assert "<base-rpc-url>" in report["missing_inputs"][0]["shell_redirection_placeholders"]
    unsafe_check = next(
        check
        for check in report["operator_command_checks"]
        if check["action_id"] == "verify_live_base_rpc"
    )
    assert unsafe_check["status"] == "SHELL_REDIRECTION_PLACEHOLDER"


def test_operator_handoff_requires_capture_preflight_source_even_when_other_sources_are_ready(tmp_path):
    _base_sources(tmp_path, ready=True)
    (tmp_path / ".tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json").unlink()

    report = build_report(tmp_path)

    assert report["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["ready_for_completion_rerun"] is False
    assert report["summary"]["capture_preflight_available"] is False
    assert report["summary"]["capture_inputs_ready"] is False
    assert report["summary"]["source_errors_total"] == 1
    assert report["missing_inputs"][0]["id"] == "capture_input_preflight"
    assert any(item["label"] == "capture_preflight" and item["status"] == "MISSING" for item in report["source_reports"])


def test_operator_handoff_cli_require_ready_returns_two_when_blocked(tmp_path):
    _base_sources(tmp_path, ready=False)
    output_json = tmp_path / "handoff.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output_json), "--require-ready"])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["ready_for_completion_rerun"] is False
    assert payload["summary"]["capture_inputs_ready"] is False
    assert payload["summary"]["missing_inputs_total"] == 5
