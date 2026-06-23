import json
from pathlib import Path

from scripts.ops.audit_production_grade_goal import Requirement, build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_production_grade_audit_accepts_fail_closed_blocked_evidence(tmp_path):
    _write_json(
        tmp_path / ".tmp/demo-gate.json",
        {"status": "VERIFIED HERE", "ok": True, "goal_can_be_marked_complete": False},
    )
    _write_json(
        tmp_path / ".tmp/demo-evidence-gate.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "entrypoint_decision": "RAW_EVIDENCE_GATE_BLOCKED",
            "ready_for_entrypoint_execution": False,
            "goal_can_be_marked_complete": False,
        },
    )
    requirements = [
        Requirement(
            "demo",
            "Demo requirement",
            [".tmp/demo-gate.json", ".tmp/demo-evidence-gate.json"],
            "production evidence missing",
        )
    ]

    report = build_report(tmp_path, requirements)

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["requirements_with_failed_artifact_checks"] == 0
    assert report["summary"]["requirements_with_production_gaps"] == 1
    assert report["summary"]["next_actions_operator_input_required"] == 1
    assert report["summary"]["next_actions_generic_blocking"] == 0
    assert report["prompt_to_artifact_checklist"][0]["status"] == "VERIFIED_LOCAL_PRODUCTION_GAP"
    assert report["next_actions"][0]["status"] == "OPERATOR_INPUT_REQUIRED"


def test_production_grade_audit_reports_missing_artifacts(tmp_path):
    requirements = [
        Requirement("demo", "Demo requirement", [".tmp/missing.json"], "production evidence missing")
    ]

    report = build_report(tmp_path, requirements)

    assert report["summary"]["requirements_missing_artifacts"] == 1
    assert report["summary"]["missing_artifact_requirement_ids"] == ["demo"]
    assert report["prompt_to_artifact_checklist"][0]["status"] == "MISSING_ARTIFACTS"


def test_production_grade_audit_promotes_completion_gate_handoff_actions(tmp_path):
    _write_json(
        tmp_path / ".tmp/demo-gate.json",
        {"status": "VERIFIED HERE", "ok": True, "goal_can_be_marked_complete": False},
    )
    _write_json(
        tmp_path / ".tmp/demo-evidence-gate.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "entrypoint_decision": "RAW_EVIDENCE_GATE_BLOCKED",
            "ready_for_entrypoint_execution": False,
            "goal_can_be_marked_complete": False,
        },
    )
    _write_json(
        tmp_path / ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "x0t_contract_handoff_available": True,
                "x0t_contract_handoff_decision": "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR",
                "x0t_contract_handoff_deployment_ready": False,
                "x0t_contract_handoff_approval_value_required": "apply-bridge-address-base-sepolia",
                "x0t_contract_handoff_missing_inputs_total": 1,
                "x0t_contract_handoff_operator_actions_total": 6,
                "x0t_contract_handoff_operator_approval_required_actions_total": 1,
                "x0t_contract_handoff_operator_commands_total": 5,
                "x0t_contract_handoff_operator_command_shell_surface_ready": True,
                "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "x0t_contract_handoff_operator_sequence_ready": True,
                "live_rollout_handoff_available": True,
                "live_rollout_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
                "live_rollout_handoff_can_close_image_digests_blocker": False,
                "live_rollout_handoff_missing_inputs_total": 1,
                "live_rollout_handoff_operator_actions_total": 5,
                "live_rollout_handoff_operator_input_required_actions_total": 2,
                "live_rollout_handoff_operator_commands_total": 4,
                "live_rollout_handoff_operator_command_shell_surface_ready": True,
                "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "live_rollout_handoff_operator_sequence_ready": True,
                "production_input_return_packet_available": True,
                "production_input_return_packet_decision": "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE",
                "production_input_return_packet_blocking_inputs_total": 31,
                "production_input_return_packet_blocking_raw_inputs": 30,
                "production_input_return_packet_blocking_external_inputs": 1,
                "production_input_return_packet_blocking_inputs_operator_input_required": 31,
                "production_input_return_packet_blocking_inputs_generic_operator_required": 0,
                "production_input_return_packet_operator_next_actions_total": 2,
                "production_input_return_packet_operator_next_actions_operator_input_required": 2,
                "production_input_return_packet_operator_next_actions_generic_blocking": 0,
                "production_input_return_packet_raw_files_expected": 63,
                "production_input_return_packet_raw_files_missing": 33,
                "production_input_return_packet_raw_files_local_observation": 30,
            },
        },
    )
    requirements = [
        Requirement(
            "demo",
            "Demo requirement",
            [".tmp/demo-gate.json", ".tmp/demo-evidence-gate.json"],
            "production evidence missing",
        )
    ]

    report = build_report(tmp_path, requirements)
    actions = {item["id"]: item["status"] for item in report["next_actions"]}

    assert report["summary"]["completion_gate_runner_available"] is True
    assert report["summary"]["completion_gate_production_input_return_packet_available"] is True
    assert report["summary"]["completion_gate_production_input_return_packet_decision"] == (
        "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    )
    assert report["summary"]["completion_gate_production_input_return_packet_blocking_inputs_total"] == 31
    assert report["summary"]["completion_gate_production_input_return_packet_blocking_raw_inputs"] == 30
    assert report["summary"]["completion_gate_production_input_return_packet_blocking_external_inputs"] == 1
    assert report["summary"][
        "completion_gate_production_input_return_packet_blocking_inputs_operator_input_required"
    ] == 31
    assert report["summary"][
        "completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required"
    ] == 0
    assert report["summary"]["completion_gate_production_input_return_packet_operator_next_actions_total"] == 2
    assert report["summary"][
        "completion_gate_production_input_return_packet_operator_next_actions_operator_input_required"
    ] == 2
    assert report["summary"]["completion_gate_production_input_return_packet_operator_next_actions_generic_blocking"] == 0
    assert report["summary"]["completion_gate_production_input_return_packet_raw_files_expected"] == 63
    assert report["summary"]["completion_gate_production_input_return_packet_raw_files_missing"] == 33
    assert report["summary"]["completion_gate_production_input_return_packet_raw_files_local_observation"] == 30
    assert report["summary"]["completion_gate_x0t_contract_handoff_decision"] == (
        "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["completion_gate_live_rollout_handoff_decision"] == (
        "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["completion_gate_live_rollout_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["next_actions_operator_input_required"] == 3
    assert report["summary"]["next_actions_operator_approval_required"] == 1
    assert report["summary"]["next_actions_after_blockers"] == 1
    assert report["summary"]["next_actions_generic_blocking"] == 0
    assert actions["replace_operator_evidence"] == "OPERATOR_INPUT_REQUIRED"
    assert actions["provide_x0t_bridge_contract_address"] == "OPERATOR_INPUT_REQUIRED"
    assert actions["apply_x0t_bridge_contract_address_with_approval"] == "OPERATOR_APPROVAL_REQUIRED"
    assert actions["return_live_rollout_image_digest_provenance"] == "OPERATOR_INPUT_REQUIRED"
    assert actions["rerun_production_closeout"] == "AFTER_BLOCKERS"


def test_production_grade_audit_cli_writes_fail_closed_report(tmp_path):
    output = tmp_path / "audit.json"
    output_md = tmp_path / "audit.md"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--output-json",
        str(output),
        "--output-md",
        str(output_md),
        "--require-complete",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert output_md.exists()
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["next_actions_operator_input_required"] == 1
    assert report["summary"]["next_actions_generic_blocking"] == 0
