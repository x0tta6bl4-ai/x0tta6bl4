import json
from pathlib import Path

from src.integration.current_evidence_rollup import RollupInputs, build_rollup, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _external(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "READY" if ready else "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
        "goal_can_be_marked_complete": False,
        "summary": {
            "x0t_external_settlement_ready": ready,
            "live_rpc_ready": ready,
            "expected_evidence_file_exists": ready,
            "fake_external_settlement_prevention_enforced": True,
        },
    }


def _external_handoff(*, ready: bool) -> dict:
    return {
        "schema_version": "x0tta6bl4-x0t-external-settlement-operator-handoff-v6-repo-generated",
        "status": "VERIFIED HERE",
        "ok": True,
        "handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
        if ready
        else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
        "ready_for_completion_rerun": ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "missing_inputs": [] if ready else [{"id": "capture_input_preflight"}],
        "operator_next_actions": [
            {"id": "preflight_capture_inputs"},
            {"id": "verify_live_base_rpc"},
        ],
        "operator_command_checks": [
            {
                "action_id": "preflight_capture_inputs",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "verify_live_base_rpc",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
        "summary": {
            "source_errors_total": 0,
            "capture_preflight_available": True,
            "capture_preflight_decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
            "capture_inputs_ready": ready,
            "missing_inputs_total": 0 if ready else 5,
            "operator_actions_total": 6,
            "operator_commands_total": 5,
            "operator_command_entrypoints_missing": 0,
            "operator_command_surface_ready": True,
            "operator_commands_with_shell_redirection_placeholders": 0,
            "operator_command_shell_surface_ready": True,
            "operator_sequence_ready": True,
        },
    }


def _governance_readiness(*, ready: bool, decision: str | None = None, execute_ready_now: bool | None = None) -> dict:
    readiness_decision = decision or ("ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE")
    proposal_executed = ready or readiness_decision == "ALREADY_EXECUTED"
    execute_ready = execute_ready_now if execute_ready_now is not None else readiness_decision == "READY_TO_EXECUTE"
    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-readiness-v2",
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": readiness_decision,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": True,
        "submits_transaction": False,
        "proposal_state": {"state_label": "Executed" if proposal_executed else "Ready" if execute_ready else "Queued"},
        "summary": {
            "execute_ready_now": execute_ready,
            "proposal_executed": proposal_executed,
            "next_executable_after_utc": "" if proposal_executed or execute_ready else "2026-05-21T04:45:22Z",
        },
    }


def _governance_handoff(
    *,
    ready: bool,
    handoff_decision: str | None = None,
    ready_for_operator_execute: bool | None = None,
) -> dict:
    decision = handoff_decision or (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
        if ready
        else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    )
    operator_execute_ready = (
        ready_for_operator_execute
        if ready_for_operator_execute is not None
        else decision == "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
    )
    return {
        "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
        "status": "VERIFIED HERE",
        "ok": True,
        "handoff_decision": decision,
        "handoff_actionable": True,
        "ready_for_operator_execute": operator_execute_ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "missing_inputs": [] if ready or operator_execute_ready else [{"id": "ready_execute_state"}],
        "operator_next_actions": [
            {"id": "refresh_readiness"},
            {"id": "execute_with_operator_approval"},
            {"id": "rerun_completion_and_gap"},
        ],
        "operator_command_checks": [
            {
                "action_id": "refresh_readiness",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "execute_with_operator_approval",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_completion_and_gap",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
        "summary": {
            "source_errors_total": 0,
            "missing_inputs_total": 0 if ready or operator_execute_ready else 1,
            "operator_actions_total": 5,
            "operator_commands_total": 5,
            "operator_command_entrypoints_missing": 0,
            "operator_command_surface_ready": True,
            "operator_commands_with_shell_redirection_placeholders": 0,
            "operator_command_shell_surface_ready": True,
            "operator_sequence_ready": True,
            "seconds_until_earliest_execution_by_block_time": 0 if ready or operator_execute_ready else 120,
            "next_executable_after_utc": "" if ready or operator_execute_ready else "2026-05-21T04:45:22Z",
        },
    }


def _x0t_bridge_config(*, ready: bool) -> dict:
    return {
        "schema_version": "x0tta6bl4-x0t-bridge-config-v1",
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "X0T_BRIDGE_CONFIG_READY" if ready else "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
        "bridge_config_ready": ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "missing_inputs": [] if ready else [{"id": "bridge_contract_address"}],
        "write": {
            "approval_env": "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL",
            "approval_value_required": "apply-bridge-address-base-sepolia",
        },
        "summary": {
            "bridge_address_input_ready": ready,
            "configured_bridge_ready": ready,
            "bridge_config_ready": ready,
            "missing_inputs_total": 0 if ready else 1,
        },
    }


def _x0t_contract_readiness(*, ready: bool) -> dict:
    return {
        "schema_version": "x0tta6bl4-x0t-contract-readiness-v1",
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "CONTRACT_READINESS_CLEAR" if ready else "BLOCKED_ON_DEPLOYMENT_CONFIG",
        "contract_readiness_clear": ready,
        "goal_can_be_marked_complete": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "missing_inputs": [] if ready else [{"id": "operator_contract_addresses"}],
        "summary": {
            "build_env_ready": True,
            "contract_build_verification_ready": True,
            "base_sepolia_manifest_ready": True,
            "legacy_contract_surface_ready": True,
            "bridge_contract_source_ready": True,
            "deployment_config_ready": ready,
            "operator_configs_ready": ready,
            "missing_inputs_total": 0 if ready else 1,
        },
    }


def _image(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "READY" if ready else "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
        "operator_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
        if ready
        else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
        "ready_for_completion_rerun": ready,
        "goal_can_be_marked_complete": False,
        "missing_inputs": [] if ready else [{"id": "live_rollout_image_digest_provenance"}],
        "operator_next_actions": [] if ready else [
            {"id": "render_template_pack"},
            {"id": "return_digest_pinned_evidence"},
            {"id": "verify_live_rollout_evidence_gate"},
            {"id": "rerun_rollout_provenance"},
            {"id": "rerun_current_evidence_rollup"},
        ],
        "operator_command_checks": [] if ready else [
            {
                "action_id": "render_template_pack",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "verify_live_rollout_evidence_gate",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
        "summary": {
            "can_close_image_digests_blocker": ready,
            "raw_deploy_images_total": 2,
            "raw_deploy_images_digest_pinned": 2 if ready else 0,
            "runtime_image_provenance_artifacts_retained_here": ready,
            "missing_inputs_total": 0 if ready else 1,
            "operator_actions_total": 0 if ready else 5,
            "operator_commands_total": 0 if ready else 2,
            "operator_command_entrypoints_missing": 0,
            "operator_command_surface_ready": True,
            "operator_commands_with_shell_redirection_placeholders": 0,
            "operator_command_shell_surface_ready": True,
        },
    }


def _semantic(*, ready: bool) -> dict:
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "goal_can_be_marked_complete": ready,
        "summary": {
            "blocking_items_total": 0 if ready else 3,
            "semantic_preflight_errors_total": 0 if ready else 2,
        },
    }


def _write_rollup_inputs(tmp_path: Path, *, ready: bool) -> RollupInputs:
    external = tmp_path / "external.json"
    external_handoff = tmp_path / "external-handoff.json"
    governance_readiness = tmp_path / "governance-readiness.json"
    governance_handoff = tmp_path / "governance-handoff.json"
    contract_readiness = tmp_path / "contract-readiness.json"
    bridge_config = tmp_path / "bridge-config.json"
    image = tmp_path / "image.json"
    semantic = tmp_path / "semantic.json"
    _write_json(external, _external(ready=ready))
    _write_json(external_handoff, _external_handoff(ready=ready))
    _write_json(governance_readiness, _governance_readiness(ready=ready))
    _write_json(governance_handoff, _governance_handoff(ready=ready))
    _write_json(contract_readiness, _x0t_contract_readiness(ready=ready))
    _write_json(bridge_config, _x0t_bridge_config(ready=ready))
    _write_json(image, _image(ready=ready))
    _write_json(semantic, _semantic(ready=ready))
    return RollupInputs(
        tmp_path,
        external,
        image,
        semantic,
        "external.json",
        "image.json",
        "semantic.json",
        external_settlement_handoff_path=external_handoff,
        governance_execute_readiness_path=governance_readiness,
        governance_execute_handoff_path=governance_handoff,
        x0t_contract_readiness_path=contract_readiness,
        x0t_bridge_config_path=bridge_config,
        external_settlement_handoff_display="external-handoff.json",
        governance_execute_readiness_display="governance-readiness.json",
        governance_execute_handoff_display="governance-handoff.json",
        x0t_contract_readiness_display="contract-readiness.json",
        x0t_bridge_config_display="bridge-config.json",
    )


def test_current_evidence_rollup_blocks_when_upstream_artifacts_are_blocked(tmp_path):
    report = build_rollup(_write_rollup_inputs(tmp_path, ready=False))

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["top_blockers_total"] == 5
    assert report["summary"]["top_blockers_blocking"] == 1
    assert report["summary"]["top_blockers_operator_input_required"] == 4
    assert report["summary"]["top_blockers_operator_approval_required"] == 0
    assert {item["id"] for item in report["top_blockers"]} == {
        "external_settlement:001",
        "x0t-governance:proposal-execution",
        "x0t-contract:deployment-config",
        "live-rollout:image-digests",
        "integration-spine:semantic-production-readiness",
    }
    blocker_statuses = {item["id"]: item["status"] for item in report["top_blockers"]}
    assert blocker_statuses["external_settlement:001"] == "OPERATOR_INPUT_REQUIRED"
    assert blocker_statuses["x0t-governance:proposal-execution"] == "BLOCKING"
    assert blocker_statuses["x0t-contract:deployment-config"] == "OPERATOR_INPUT_REQUIRED"
    assert blocker_statuses["live-rollout:image-digests"] == "OPERATOR_INPUT_REQUIRED"
    assert blocker_statuses["integration-spine:semantic-production-readiness"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["external_settlement_handoff_clear"] is True
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert report["summary"]["external_settlement_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["external_settlement_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["external_settlement_handoff_operator_sequence_ready"] is True
    assert report["summary"]["x0t_governance_execute_handoff_clear"] is True
    assert report["summary"]["x0t_governance_execute_handoff_actionable"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is False
    assert report["summary"]["x0t_governance_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_contract_surface_clear"] is True
    assert report["summary"]["x0t_contract_bridge_source_ready"] is True
    assert report["summary"]["x0t_contract_deployment_ready"] is False
    assert report["summary"]["x0t_bridge_config_decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    assert report["summary"]["image_digests_operator_handoff_decision"] == (
        "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["image_digests_missing_inputs_total"] == 1
    assert report["summary"]["image_digests_operator_actions_total"] == 5
    assert report["summary"]["image_digests_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["image_digests_operator_command_surface_ready"] is True
    assert report["operator_handoffs"]["source_available"] is True
    assert report["operator_handoffs"]["external_settlement"]["missing_inputs"][0]["id"] == "capture_input_preflight"
    assert report["operator_handoffs"]["x0t_governance_execute"]["operator_command_checks"]
    assert report["operator_handoffs"]["live_rollout_image_digests"]["missing_inputs"][0]["id"] == (
        "live_rollout_image_digest_provenance"
    )
    assert report["operator_handoffs"]["live_rollout_image_digests"]["operator_command_checks"]
    governance_blocker = next(
        item for item in report["top_blockers"] if item["id"] == "x0t-governance:proposal-execution"
    )
    assert "next executable after UTC: 2026-05-21T04:45:22Z" in governance_blocker["required_evidence"]


def test_current_evidence_rollup_accepts_ready_to_execute_readiness_without_closing(tmp_path):
    inputs = _write_rollup_inputs(tmp_path, ready=False)
    _write_json(
        inputs.governance_execute_readiness_path,
        _governance_readiness(ready=False, decision="READY_TO_EXECUTE", execute_ready_now=True),
    )
    _write_json(
        inputs.governance_execute_handoff_path,
        _governance_handoff(
            ready=False,
            handoff_decision="X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
            ready_for_operator_execute=True,
        ),
    )

    report = build_rollup(inputs)
    blocker_ids = {item["id"] for item in report["top_blockers"]}

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["x0t_governance_execute_readiness_clear"] is True
    assert report["summary"]["x0t_governance_execute_decision"] == "READY_TO_EXECUTE"
    assert report["summary"]["x0t_governance_execute_ready_now"] is True
    assert report["summary"]["x0t_governance_execute_handoff_clear"] is True
    assert report["summary"]["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
    )
    assert report["summary"]["x0t_governance_ready_for_operator_execute"] is True
    assert "x0t-governance:operator-handoff" not in blocker_ids
    assert "x0t-governance:proposal-execution" in blocker_ids
    proposal_blocker = next(
        item for item in report["top_blockers"] if item["id"] == "x0t-governance:proposal-execution"
    )
    assert proposal_blocker["status"] == "OPERATOR_APPROVAL_REQUIRED"
    assert report["summary"]["top_blockers_operator_approval_required"] == 1


def test_current_evidence_rollup_can_mark_complete_when_all_inputs_are_ready(tmp_path):
    report = build_rollup(_write_rollup_inputs(tmp_path, ready=True))

    assert report["completion_decision"] == "COMPLETE"
    assert report["goal_can_be_marked_complete"] is True
    assert report["top_blockers"] == []
    assert report["not_verified_yet"] == []
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["external_settlement_handoff_operator_sequence_ready"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is True
    assert report["summary"]["x0t_contract_deployment_ready"] is True
    assert report["summary"]["image_digests_operator_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
    assert report["operator_handoffs"]["live_rollout_image_digests"]["ready_for_completion_rerun"] is True
    assert report["summary"]["top_blockers_blocking"] == 0
    assert report["summary"]["top_blockers_operator_input_required"] == 0
    assert report["summary"]["top_blockers_operator_approval_required"] == 0
    assert report["operator_handoffs"]["external_settlement"]["ready_for_completion_rerun"] is True


def test_current_evidence_rollup_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-complete"])

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["summary"]["source_errors_total"] == 8
    assert report["goal_can_be_marked_complete"] is False
