import json
from pathlib import Path

from src.integration.production_closeout_review import (
    build_closure_preflight_report,
    build_final_review_report,
    build_report,
    main,
)


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_current_evidence_context(
    root: Path,
    *,
    current_gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    _write_json(
        root,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        {
            "status": "working_map_not_production_completion_proof",
            "planes": {
                "data_plane": {},
                "control_plane": {},
                "trust_plane": {},
                "evidence_plane": {},
                "economy_plane": {},
            },
            "current_gaps": current_gaps or [],
            "next_actions": next_actions or [],
        },
    )
    audit = root / "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text("# active goal audit\n", encoding="utf-8")


def _write_cross_plane_proof_gate(root: Path, *, allowed: bool) -> None:
    claim_ids = (
        "production_readiness",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "settlement_finality",
        "dpi_bypass",
    )
    claim_results = [
        {
            "claim_id": claim_id,
            "allowed": allowed,
            "blockers": [] if allowed else [f"{claim_id}_proof_missing"],
        }
        for claim_id in claim_ids
    ]
    _write_json(
        root,
        ".tmp/validation-shards/cross-plane-proof-gate-current.json",
        {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_ALLOWED" if allowed else "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": allowed,
            "context": {
                "source_artifact_hashes_present": True,
                "map_sha256": "0" * 64,
                "audit_sha256": "1" * 64,
            },
            "claim_results": claim_results,
            "summary": {
                "claims_total": len(claim_results),
                "claims_allowed": len(claim_results) if allowed else 0,
                "claims_blocked": 0 if allowed else len(claim_results),
            },
        },
    )


def _governance_handoff(*, ready: bool) -> dict:
    return {
        "available": True,
        "decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
        if ready
        else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
        "actionable": True,
        "ready_for_operator_execute": ready,
        "approval_value_required": "execute-proposal-1-base-sepolia",
        "missing_inputs": []
        if ready
        else [
            {
                "id": "ready_execute_state",
                "status": "WAIT_FOR_CHAIN_STATE",
            }
        ],
        "operator_next_actions": [
            {"id": "refresh_readiness", "status": "DONE" if ready else "BLOCKING"},
            {"id": "dry_run_execute_boundary", "status": "READY" if ready else "AFTER_READY_STATE"},
            {
                "id": "execute_with_operator_approval",
                "status": "OPERATOR_APPROVAL_REQUIRED" if ready else "AFTER_READY_STATE",
                "requires_operator_approval": True,
            },
            {"id": "retain_execution_receipt", "status": "AFTER_EXECUTE"},
            {"id": "rerun_completion_and_gap", "status": "AFTER_EXECUTE"},
        ],
        "operator_command_checks": [
            {
                "action_id": "refresh_readiness",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "dry_run_execute_boundary",
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
            {
                "action_id": "rerun_completion_and_gap",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
    }


def _external_handoff(*, ready: bool) -> dict:
    return {
        "available": True,
        "decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY_FOR_COMPLETION_RERUN"
        if ready
        else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
        "ready_for_completion_rerun": ready,
        "capture_preflight_decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
        "capture_inputs_ready": ready,
        "missing_inputs": []
        if ready
        else [
            {"id": "capture_input_preflight", "status": "OPERATOR_REQUIRED"},
            {"id": "retained_settlement_receipt", "status": "OPERATOR_REQUIRED"},
            {"id": "live_rpc_receipt_verification", "status": "OPERATOR_REQUIRED"},
            {"id": "production_evidence_import", "status": "OPERATOR_REQUIRED"},
            {"id": "completion_gate_external_settlement", "status": "OPERATOR_REQUIRED"},
        ],
        "operator_next_actions": [
            {"id": "preflight_capture_inputs", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
            {"id": "capture_real_settlement_receipt", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
            {"id": "verify_retained_settlement_json", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
            {"id": "verify_live_base_rpc", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
            {"id": "rerun_production_input_pipeline", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
            {"id": "rerun_completion_gate", "status": "DONE" if ready else "OPERATOR_INPUT_REQUIRED"},
        ],
        "operator_command_checks": [
            {
                "action_id": "preflight_capture_inputs",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "verify_retained_settlement_json",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "verify_live_base_rpc",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_production_input_pipeline",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_completion_gate",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
    }


def _x0t_contract_handoff(*, ready: bool) -> dict:
    return {
        "available": True,
        "decision": "X0T_CONTRACT_DEPLOYMENT_CONFIG_READY"
        if ready
        else "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR",
        "deployment_ready": ready,
        "approval_value_required": "apply-bridge-address-base-sepolia",
        "missing_inputs": []
        if ready
        else [
            {
                "id": "operator_contract_addresses",
                "status": "OPERATOR_INPUT_REQUIRED",
            }
        ],
        "operator_next_actions": []
        if ready
        else [
            {"id": "provide_bridge_address", "status": "OPERATOR_INPUT_REQUIRED"},
            {"id": "validate_bridge_address", "status": "OPERATOR_INPUT_REQUIRED"},
            {"id": "apply_bridge_address_with_operator_approval", "status": "OPERATOR_APPROVAL_REQUIRED"},
            {"id": "rerun_contract_readiness", "status": "AFTER_APPLY"},
            {"id": "rerun_completion_audit", "status": "AFTER_APPLY"},
            {"id": "rerun_production_gap_index", "status": "AFTER_APPLY"},
        ],
        "operator_command_checks": []
        if ready
        else [
            {
                "action_id": "validate_bridge_address",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "apply_bridge_address_with_operator_approval",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_contract_readiness",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_completion_audit",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_production_gap_index",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
    }


def _live_rollout_handoff(*, ready: bool) -> dict:
    return {
        "available": True,
        "decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
        if ready
        else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
        "ready_for_completion_rerun": ready,
        "can_close_image_digests_blocker": ready,
        "missing_inputs": []
        if ready
        else [
            {
                "id": "live_rollout_image_digest_provenance",
                "status": "OPERATOR_INPUT_REQUIRED",
            }
        ],
        "operator_next_actions": []
        if ready
        else [
            {"id": "render_template_pack", "status": "OPERATOR_INPUT_REQUIRED"},
            {"id": "return_digest_pinned_evidence", "status": "OPERATOR_INPUT_REQUIRED"},
            {"id": "verify_live_rollout_evidence_gate", "status": "AFTER_OPERATOR_EVIDENCE"},
            {"id": "rerun_rollout_provenance", "status": "AFTER_OPERATOR_EVIDENCE"},
            {"id": "rerun_current_evidence_rollup", "status": "AFTER_ROLLOUT_READY"},
        ],
        "operator_command_checks": []
        if ready
        else [
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
            {
                "action_id": "rerun_rollout_provenance",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
            {
                "action_id": "rerun_current_evidence_rollup",
                "entrypoint_exists": True,
                "shell_redirection_placeholder_detected": False,
            },
        ],
    }


def _write_sources(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json",
        {
            "schema_version": "test-input-manifest",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "OPERATOR_INPUT_BUNDLE_REQUIRED",
            "ready_for_production_closeout_review": ready,
            "goal_can_be_marked_complete": False,
            "summary": {
                "ready_for_production_closeout_review": ready,
                "external_artifacts_ready": 1 if ready else 0,
                "external_artifacts_required": 1,
                "external_artifacts_missing": 0 if ready else 1,
                "raw_files_ready_for_integration": 1 if ready else 0,
                "raw_files_required_for_integration": 1,
                "raw_files_blocking_for_integration": 0 if ready else 1,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        {
            "schema_version": "test-return-acceptance",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED",
            "ready_for_pipeline_install": ready,
            "ready_to_stage": ready,
            "summary": {
                "ready_for_pipeline_install": ready,
                "ready_to_stage": ready,
                "external_artifacts_operator_required": 0 if ready else 1,
                "external_settlement_live_rpc_ready": ready,
                "raw_ready_to_stage": ready,
                "raw_files_expected": 1,
                "raw_files_staged": 1 if ready else 0,
                "raw_files_ready_to_stage": 1 if ready else 0,
                "raw_files_destination_existing": 1,
                "raw_files_local_observation": 0 if ready else 1,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
        {
            "schema_version": "test-input-pipeline",
            "status": "VERIFIED HERE",
            "ok": True,
            "pipeline_decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW"
            if ready
            else "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE",
            "blocking_inputs": []
            if ready
            else [
                {
                    "evidence_key": "external_settlement",
                    "kind": "external_settlement",
                    "status": "OPERATOR_REQUIRED",
                }
            ],
            "summary": {
                "blocking_inputs_total": 0 if ready else 1,
                "blocking_external_inputs": 0 if ready else 1,
                "blocking_raw_inputs": 0,
                "collector_evidence_blockers": 0 if ready else 4,
                "raw_files_expected": 1,
                "raw_files_installed": 1,
                "external_settlement_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json",
        {
            "schema_version": "test-rollup",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ROLLUP_APPROVAL_READY" if ready else "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE",
            "ready": ready,
            "summary": {
                "source_errors_total": 0,
                "evidence_files_total": 1,
                "evidence_files_valid": 1 if ready else 0,
                "evidence_files_missing": 0,
                "evidence_files_invalid": 0 if ready else 1,
                "evidence_files_operator_input_required": 0 if ready else 1,
                "ready_for_closeout_review": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json",
        {
            "schema_version": "test-consistency",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR"
            if ready
            else "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR",
            "valid": True,
            "production_ready": ready,
            "summary": {
                "errors_total": 0,
                "required_evidence_files_total": 1,
                "required_evidence_files_ready": 1 if ready else 0,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {
            "schema_version": "test-current-rollup",
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "goal_can_be_marked_complete": ready,
            "operator_handoffs": {
                "source_artifact": "current_evidence_rollup",
                "source_available": True,
                "x0t_governance_execute": _governance_handoff(ready=ready),
                "external_settlement": _external_handoff(ready=ready),
                "live_rollout_image_digests": _live_rollout_handoff(ready=ready),
            },
            "summary": {
                "top_blockers_total": 0 if ready else 5,
                "top_blockers_blocking": 0 if ready else 1,
                "top_blockers_operator_input_required": 0 if ready else 4,
                "top_blockers_operator_approval_required": 0,
                "external_settlement_handoff_clear": True,
                "external_settlement_handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
                if ready
                else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
                "x0t_governance_execute_readiness_available": True,
                "x0t_governance_execute_readiness_clear": True,
                "x0t_governance_execute_decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
                "x0t_governance_execute_ready_now": False,
                "x0t_governance_proposal_executed": ready,
                "x0t_governance_state_label": "Executed" if ready else "Queued",
                "x0t_governance_next_executable_after_utc": "" if ready else "2026-05-21T04:45:22Z",
                "x0t_governance_seconds_until_earliest_execution_by_block_time": 0 if ready else 120,
                "x0t_governance_execute_handoff_available": True,
                "x0t_governance_execute_handoff_clear": True,
                "x0t_governance_execute_handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
                if ready
                else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
                "x0t_governance_execute_handoff_actionable": True,
                "x0t_governance_ready_for_operator_execute": ready,
                "x0t_contract_readiness_available": True,
                "x0t_contract_surface_clear": True,
                "x0t_contract_readiness_decision": "CONTRACT_READINESS_CLEAR"
                if ready
                else "BLOCKED_ON_DEPLOYMENT_CONFIG",
                "x0t_contract_readiness_clear": ready,
                "x0t_contract_build_env_ready": True,
                "x0t_contract_build_verification_ready": True,
                "x0t_contract_bridge_source_ready": True,
                "x0t_contract_deployment_config_ready": ready,
                "x0t_contract_operator_configs_ready": ready,
                "x0t_contract_missing_inputs_total": 0 if ready else 1,
                "x0t_bridge_config_available": True,
                "x0t_bridge_config_decision": "X0T_BRIDGE_CONFIG_READY"
                if ready
                else "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
                "x0t_bridge_config_ready": ready,
                "x0t_bridge_address_input_ready": ready,
                "x0t_bridge_configured_bridge_ready": ready,
                "x0t_bridge_missing_inputs_total": 0 if ready else 1,
                "x0t_contract_deployment_ready": ready,
                "image_digests_operator_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
                if ready
                else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
                "image_digests_ready_for_completion_rerun": ready,
                "image_digests_missing_inputs_total": 0 if ready else 1,
                "image_digests_operator_actions_total": 0 if ready else 5,
                "image_digests_operator_commands_total": 0 if ready else 4,
                "image_digests_operator_command_entrypoints_missing": 0,
                "image_digests_operator_command_surface_ready": True,
                "image_digests_operator_commands_with_shell_redirection_placeholders": 0,
                "image_digests_operator_command_shell_surface_ready": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
        {
            "schema_version": "test-production-gap-index",
            "status": "VERIFIED HERE",
            "ok": True,
            "x0t_governance_operator_handoff": _governance_handoff(ready=ready),
            "external_settlement_operator_handoff": _external_handoff(ready=ready),
            "x0t_contract_operator_handoff": _x0t_contract_handoff(ready=ready),
            "live_rollout_operator_handoff": _live_rollout_handoff(ready=ready),
        },
    )
    _write_cross_plane_proof_gate(root, allowed=ready)


def test_production_closeout_review_accepts_valid_blocked_state(tmp_path):
    _write_sources(tmp_path, ready=False)

    report = build_report(tmp_path)

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["decision"] == "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_total"] == 6
    assert report["summary"]["sources_ready"] == 0
    assert report["summary"]["blocking_inputs_total"] == 1
    assert report["summary"]["raw_files_installed"] == 0
    assert report["summary"]["raw_files_pipeline_reported_installed"] == 1
    assert report["summary"]["raw_files_install_claim_source"] == "return_acceptance"
    assert report["summary"]["raw_files_existing_or_retained"] == 1
    assert report["summary"]["raw_files_local_observation"] == 1
    assert report["summary"]["rollup_evidence_files_invalid"] == 1
    assert report["summary"]["rollup_evidence_files_operator_input_required"] == 1
    assert report["summary"]["operator_handoff_source_available"] is True
    assert report["summary"]["operator_handoff_source_errors_total"] == 0
    assert report["summary"]["top_blockers_total"] == 5
    assert report["summary"]["top_blockers_blocking"] == 1
    assert report["summary"]["top_blockers_operator_input_required"] == 4
    assert report["summary"]["top_blockers_operator_approval_required"] == 0
    assert report["summary"]["x0t_contract_surface_clear"] is True
    assert report["summary"]["x0t_contract_bridge_source_ready"] is True
    assert report["summary"]["x0t_contract_deployment_ready"] is False
    assert report["summary"]["x0t_bridge_config_decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    assert report["summary"]["external_settlement_handoff_clear"] is True
    assert report["summary"]["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["summary"]["x0t_governance_execute_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert report["summary"]["x0t_governance_proposal_executed"] is False
    assert report["summary"]["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    )
    assert report["summary"]["x0t_governance_handoff_available"] is True
    assert report["summary"]["x0t_governance_handoff_actionable"] is True
    assert report["summary"]["x0t_governance_handoff_approval_value_required"] == "execute-proposal-1-base-sepolia"
    assert report["summary"]["x0t_governance_handoff_missing_inputs_total"] == 1
    assert report["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_approval_required_actions_total"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_commands_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert report["summary"]["external_settlement_handoff_available"] is True
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert report["summary"]["external_settlement_capture_preflight_decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert report["summary"]["external_settlement_capture_inputs_ready"] is False
    assert report["summary"]["external_settlement_handoff_missing_inputs_total"] == 5
    assert report["summary"]["external_settlement_handoff_operator_actions_total"] == 6
    assert report["summary"]["external_settlement_handoff_operator_input_required_actions_total"] == 6
    assert report["summary"]["external_settlement_handoff_operator_commands_total"] == 5
    assert report["summary"]["external_settlement_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["external_settlement_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["external_settlement_handoff_operator_sequence_ready"] is True
    assert report["summary"]["x0t_contract_handoff_available"] is True
    assert report["summary"]["x0t_contract_handoff_decision"] == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    assert report["summary"]["x0t_contract_handoff_deployment_ready"] is False
    assert report["summary"]["x0t_contract_handoff_approval_value_required"] == "apply-bridge-address-base-sepolia"
    assert report["summary"]["x0t_contract_handoff_missing_inputs_total"] == 1
    assert report["summary"]["x0t_contract_handoff_operator_actions_total"] == 6
    assert report["summary"]["x0t_contract_handoff_operator_approval_required_actions_total"] == 1
    assert report["summary"]["x0t_contract_handoff_operator_commands_total"] == 5
    assert report["summary"]["x0t_contract_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_contract_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["x0t_contract_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert report["summary"]["live_rollout_handoff_available"] is True
    assert report["summary"]["live_rollout_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert report["summary"]["live_rollout_handoff_ready_for_completion_rerun"] is False
    assert report["summary"]["live_rollout_handoff_can_close_image_digests_blocker"] is False
    assert report["summary"]["live_rollout_handoff_missing_inputs_total"] == 1
    assert report["summary"]["live_rollout_handoff_operator_actions_total"] == 5
    assert report["summary"]["live_rollout_handoff_operator_input_required_actions_total"] == 2
    assert report["summary"]["live_rollout_handoff_operator_commands_total"] == 4
    assert report["summary"]["live_rollout_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["live_rollout_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["live_rollout_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
    assert report["operator_handoffs"]["x0t_governance_execute"]["approval_value_required"] == (
        "execute-proposal-1-base-sepolia"
    )
    assert report["operator_handoffs"]["x0t_governance_execute"]["source_artifact"] == (
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
    )
    assert report["operator_handoffs"]["external_settlement"]["missing_inputs"][0]["id"] == "capture_input_preflight"
    assert report["operator_handoffs"]["external_settlement"]["operator_next_actions"][0]["status"] == (
        "OPERATOR_INPUT_REQUIRED"
    )
    assert report["operator_handoffs"]["x0t_contract_deployment"]["source_artifact"] == (
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
    )
    assert report["operator_handoffs"]["x0t_contract_deployment"]["approval_value_required"] == (
        "apply-bridge-address-base-sepolia"
    )
    assert report["operator_handoffs"]["x0t_contract_deployment"]["operator_command_checks"]
    assert report["operator_handoffs"]["live_rollout_image_digests"]["source_artifact"] == (
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
    )
    assert report["operator_handoffs"]["live_rollout_image_digests"]["missing_inputs"][0]["id"] == (
        "live_rollout_image_digest_provenance"
    )
    assert report["operator_handoffs"]["live_rollout_image_digests"]["operator_command_checks"]
    assert report["blocking_inputs"][0]["evidence_key"] == "external_settlement"
    preflight = build_closure_preflight_report(report)
    final_review = build_final_review_report(report)
    assert preflight["decision"] == "PREFLIGHT_BLOCKED_ON_OPERATOR_EVIDENCE"
    assert final_review["decision"] == "FINAL_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"
    for derived in (preflight, final_review):
        assert derived["status"] == "VERIFIED HERE"
        assert derived["ok"] is True
        assert derived["goal_can_be_marked_complete"] is False
        assert derived["summary"]["raw_files_installed"] == 0
        assert derived["summary"]["raw_files_install_claim_source"] == "return_acceptance"
        assert derived["summary"]["raw_files_pipeline_reported_installed"] == 1
        assert derived["summary"]["raw_files_local_observation"] == 1
        assert derived["summary"]["rollup_evidence_files_operator_input_required"] == 1
        assert derived["summary"]["operator_handoff_source_available"] is True
        assert derived["summary"]["top_blockers_operator_input_required"] == 4
        assert derived["summary"]["x0t_contract_deployment_ready"] is False
        assert derived["summary"]["external_settlement_handoff_decision"] == (
            "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
        )
        assert derived["summary"]["x0t_governance_execute_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
        assert derived["summary"]["x0t_governance_proposal_executed"] is False
        assert derived["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
        assert derived["summary"]["x0t_governance_handoff_operator_approval_required_actions_total"] == 0
        assert derived["summary"]["external_settlement_handoff_operator_input_required_actions_total"] == 6
        assert derived["summary"]["external_settlement_handoff_operator_commands_total"] == 5
        assert derived["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
        assert derived["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
        assert derived["operator_handoffs"]["external_settlement"]["operator_next_actions"][0]["status"] == (
            "OPERATOR_INPUT_REQUIRED"
        )
        assert derived["operator_handoffs"]["external_settlement"]["operator_command_checks"]
        assert derived["operator_handoffs"]["x0t_contract_deployment"]["operator_command_checks"]
        assert derived["operator_handoffs"]["live_rollout_image_digests"]["operator_command_checks"]


def test_production_closeout_review_can_be_ready_when_sources_are_ready(tmp_path):
    _write_sources(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)

    report = build_report(tmp_path)

    assert report["local_closeout_ready"] is True
    assert report["ready"] is True
    assert report["decision"] == "CLOSEOUT_REVIEW_READY"
    assert report["summary"]["local_closeout_ready"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_claim_gate"]["closeout_ready_claim_allowed"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["summary"]["source_errors_total"] == 0
    assert report["summary"]["sources_ready"] == report["summary"]["sources_total"]
    assert report["summary"]["raw_files_installed"] == 1
    assert report["summary"]["raw_files_install_claim_source"] == "return_acceptance"
    assert report["summary"]["operator_handoff_source_available"] is True
    assert report["summary"]["rollup_evidence_files_operator_input_required"] == 0
    assert report["summary"]["top_blockers_total"] == 0
    assert report["summary"]["top_blockers_blocking"] == 0
    assert report["summary"]["top_blockers_operator_input_required"] == 0
    assert report["summary"]["top_blockers_operator_approval_required"] == 0
    assert report["summary"]["x0t_contract_deployment_ready"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is True
    assert report["summary"]["x0t_governance_handoff_ready_for_operator_execute"] is True
    assert report["summary"]["x0t_governance_handoff_operator_approval_required_actions_total"] == 1
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["external_settlement_handoff_operator_input_required_actions_total"] == 0
    assert report["summary"]["x0t_contract_handoff_deployment_ready"] is True
    assert report["summary"]["x0t_contract_handoff_operator_actions_total"] == 0
    assert report["summary"]["live_rollout_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["live_rollout_handoff_operator_actions_total"] == 0
    assert report["not_verified_yet"] == []


def test_production_closeout_review_blocks_ready_without_current_evidence_context(tmp_path):
    _write_sources(tmp_path, ready=True)

    report = build_report(tmp_path)
    preflight = build_closure_preflight_report(report)
    final_review = build_final_review_report(report)

    assert report["local_closeout_ready"] is True
    assert report["ready"] is False
    assert report["decision"] == "CLOSEOUT_REVIEW_BLOCKED_BY_CURRENT_EVIDENCE"
    assert report["summary"]["closeout_ready_blocked_by_current_evidence"] is True
    assert report["summary"]["closeout_ready_blocked_by_cross_plane_proof_gate"] is False
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["closeout_ready_claim_allowed"] is False
    assert preflight["ready"] is False
    assert final_review["ready"] is False
    assert preflight["summary"]["local_closeout_ready"] is True
    assert preflight["summary"]["closeout_ready_blocked_by_current_evidence"] is True
    assert preflight["summary"]["closeout_ready_blocked_by_cross_plane_proof_gate"] is False


def test_production_closeout_review_blocks_ready_on_current_evidence_open_gap(tmp_path):
    _write_sources(tmp_path, ready=True)
    _write_current_evidence_context(
        tmp_path,
        current_gaps=[{"id": "external-dpi-proof-missing", "blocks_real_readiness": True}],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    report = build_report(tmp_path)

    assert report["local_closeout_ready"] is True
    assert report["ready"] is False
    assert report["decision"] == "CLOSEOUT_REVIEW_BLOCKED_BY_CURRENT_EVIDENCE"
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_production_closeout_review_blocks_ready_when_cross_plane_proof_gate_blocks(tmp_path):
    _write_sources(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = build_report(tmp_path)
    preflight = build_closure_preflight_report(report)
    final_review = build_final_review_report(report)

    assert report["local_closeout_ready"] is True
    assert report["ready"] is False
    assert report["decision"] == "CLOSEOUT_REVIEW_BLOCKED_BY_CROSS_PLANE_PROOF_GATE"
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["closeout_ready_blocked_by_cross_plane_proof_gate"] is True
    assert report["cross_plane_claim_gate"]["closeout_ready_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "reusable cross-plane proof gate must allow production closeout claims" in report["not_verified_yet"]
    assert preflight["ready"] is False
    assert final_review["ready"] is False
    assert preflight["summary"]["cross_plane_proof_gate_allowed"] is False
    assert final_review["cross_plane_proof_gate"]["allowed"] is False


def test_production_closeout_review_reports_missing_source_errors(tmp_path):
    report = build_report(tmp_path)

    assert report["ready"] is False
    assert report["decision"] == "CLOSEOUT_REVIEW_INVALID_SOURCE_ARTIFACTS"
    assert report["summary"]["source_errors_total"] == 6
    assert report["source_errors"]


def test_production_closeout_review_cli_require_ready_returns_two_when_blocked(tmp_path):
    _write_sources(tmp_path, ready=False)
    output_json = tmp_path / "closeout.json"
    preflight_json = tmp_path / "preflight.json"
    final_review_json = tmp_path / "final-review.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--output-json",
        str(output_json),
        "--output-closure-preflight-json",
        str(preflight_json),
        "--output-final-review-json",
        str(final_review_json),
        "--require-ready",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_json.read_text(encoding="utf-8"))
    final_review = json.loads(final_review_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["summary"]["source_errors_total"] == 0
    assert payload["operator_handoffs"]["x0t_governance_execute"]["operator_next_actions"]
    assert payload["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert payload["summary"]["external_settlement_handoff_operator_input_required_actions_total"] == 6
    assert payload["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert payload["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
    assert payload["operator_handoffs"]["x0t_contract_deployment"]["operator_command_checks"]
    assert payload["operator_handoffs"]["live_rollout_image_digests"]["operator_command_checks"]
    assert preflight["schema_version"].endswith("v4-repo-generated")
    assert final_review["schema_version"].endswith("v4-repo-generated")
    assert preflight["summary"]["raw_files_installed"] == 0
    assert final_review["summary"]["raw_files_installed"] == 0
    assert preflight["operator_handoffs"]["external_settlement"]["operator_command_checks"]
    assert preflight["summary"]["external_settlement_handoff_operator_input_required_actions_total"] == 6
    assert preflight["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert preflight["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
    assert final_review["summary"]["external_settlement_handoff_operator_sequence_ready"] is True
    assert final_review["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert final_review["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
