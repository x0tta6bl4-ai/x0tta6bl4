import json
from pathlib import Path

from src.integration.objective_coverage_audit import (
    DEFAULT_CROSS_PLANE_PROOF_GATE,
    DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT,
    OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS,
    build_report,
    main,
)
from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS


def _write_json(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_cross_plane_proof_gate(root: Path, *, allowed: bool) -> None:
    claim_results = [
        {
            "claim_id": claim_id,
            "allowed": allowed,
            "blockers": [] if allowed else [f"{claim_id}_proof_missing"],
        }
        for claim_id in OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS
    ]
    _write_json(
        root,
        DEFAULT_CROSS_PLANE_PROOF_GATE,
        {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_ALLOWED" if allowed else "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": allowed,
            "context": {
                "required_planes_present": True,
                "open_gap_ids": [] if allowed else ["external-dpi-proof-missing"],
                "next_action_ids": [] if allowed else ["external-dpi-real-artifact-intake"],
                "current_gap_count": 0 if allowed else 1,
                "next_action_count": 0 if allowed else 1,
            },
            "claim_results": claim_results,
            "summary": {
                "claims_total": len(claim_results),
                "claims_allowed": len(claim_results) if allowed else 0,
                "claims_blocked": 0 if allowed else len(claim_results),
            },
        },
    )


def _base_artifacts(root: Path, *, ready: bool = False) -> None:
    raw_expected = 2
    raw_staged = raw_expected if ready else 0
    raw_local = 0 if ready else raw_expected
    _write_cross_plane_proof_gate(root, allowed=ready)
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-code-wiring-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "wiring_covered": {
                "identity": "identity wired",
                "event_bus": "event bus wired",
                "policy_engine": "policy wired",
                "safe_actuator": "safe actuator wired",
                "settlement_reward_loop": "settlement wired",
            },
            "verification": [],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-input-pipeline-v4-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "pipeline_decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE",
            "ready": ready,
            "summary": {
                "raw_files_expected": raw_expected,
                "raw_files_installed": raw_staged,
                "raw_files_install_claim_source": "return_acceptance",
                "collector_evidence_blockers": 0 if ready else 2,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "ready_for_pipeline_install": ready,
            "ready_to_stage": ready,
            "summary": {
                "raw_files_expected": raw_expected,
                "raw_files_staged": raw_staged,
                "raw_files_local_observation": raw_local,
                "raw_ready_to_stage": ready,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_FOR_PRODUCTION_EVIDENCE_INSTALL" if ready else "BLOCKED_OPERATOR_EVIDENCE_REQUIRED",
            "pending_evidence_keys": [] if ready else sorted(REQUIRED_EVIDENCE_KEYS),
            "summary": {
                "ready_for_install": ready,
                "required_evidence_keys_ready": len(REQUIRED_EVIDENCE_KEYS) if ready else 0,
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_INSTALL" if ready else "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED",
            "summary": {"ready_source_candidates_total": len(REQUIRED_EVIDENCE_KEYS) if ready else 0},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "goal_can_be_marked_complete": ready,
            "summary": {
                "files_total": raw_expected,
                "usable_for_goal_completion_files": raw_expected if ready else 0,
                "classification_counts": {"PRODUCTION_GRADE": raw_expected} if ready else {"RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE": raw_expected},
                "collector_classification_counts": {
                    "paid-client-serviceability": {"PRODUCTION_GRADE": 8 if ready else 0},
                    "live-rollout": {"PRODUCTION_GRADE": 6 if ready else 0},
                },
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "goal_can_be_marked_complete": ready,
            "summary": {
                "blocking_items_total": 0 if ready else 3,
                "semantic_preflight_errors_total": 0 if ready else 2,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "production_ready": ready,
            "decision": "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR" if ready else "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR",
            "summary": {"required_evidence_files_ready": 31 if ready else 0, "required_evidence_files_total": 31},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "ready": ready,
            "decision": "ROLLUP_APPROVAL_READY" if ready else "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE",
            "summary": {"evidence_files_valid": 31 if ready else 0, "evidence_files_total": 31},
        },
    )
    closeout_handoff_summary = {
        "operator_handoff_source_available": True,
        "operator_handoff_source_errors_total": 0,
        "x0t_governance_handoff_operator_actions_total": 5,
        "x0t_governance_handoff_operator_commands_total": 5,
        "x0t_governance_handoff_operator_sequence_ready": True,
        "external_settlement_handoff_operator_actions_total": 6,
        "external_settlement_handoff_operator_commands_total": 5,
        "external_settlement_handoff_operator_sequence_ready": True,
        "x0t_contract_handoff_available": True,
        "x0t_contract_handoff_decision": "X0T_CONTRACT_DEPLOYMENT_CONFIG_READY"
        if ready
        else "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR",
        "x0t_contract_handoff_deployment_ready": ready,
        "x0t_contract_handoff_operator_actions_total": 0 if ready else 6,
        "x0t_contract_handoff_operator_commands_total": 0 if ready else 5,
        "x0t_contract_handoff_operator_sequence_ready": not ready,
        "live_rollout_handoff_available": True,
        "live_rollout_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
        if ready
        else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
        "live_rollout_handoff_ready_for_completion_rerun": ready,
        "live_rollout_handoff_operator_actions_total": 0 if ready else 5,
        "live_rollout_handoff_operator_commands_total": 0 if ready else 4,
        "live_rollout_handoff_operator_command_entrypoints_missing": 0,
        "live_rollout_handoff_operator_sequence_ready": not ready,
    }
    for rel, decision in [
        (".tmp/validation-shards/integration-spine-production-closeout-review-current.json", "CLOSEOUT_REVIEW_READY" if ready else "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"),
        (".tmp/validation-shards/integration-spine-production-closure-preflight-current.json", "PREFLIGHT_READY_FOR_FINAL_REVIEW" if ready else "PREFLIGHT_BLOCKED_ON_OPERATOR_EVIDENCE"),
        (".tmp/validation-shards/integration-spine-production-final-review-current.json", "FINAL_REVIEW_READY" if ready else "FINAL_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"),
    ]:
        _write_json(
            root,
            rel,
            {
                "status": "VERIFIED HERE",
                "ok": True,
                "ready": ready,
                "decision": decision,
                "operator_handoffs": {
                    "source_artifact": ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
                    "source_available": True,
                },
                "summary": {"raw_files_installed": raw_staged, **closeout_handoff_summary},
            },
        )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-completion-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "goal_can_be_marked_complete": ready,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "summary": {"local_wiring_passed": True, "production_readiness_passed": ready},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "NO_PRODUCTION_EVIDENCE_GAPS" if ready else "BLOCKED_ON_OPERATOR_EVIDENCE",
            "operator_priority_order": ["external_settlement"],
            "summary": {
                "pending_evidence_keys": 0 if ready else len(REQUIRED_EVIDENCE_KEYS),
                "external_settlement_handoff_available": True,
                "external_settlement_handoff_clear": True,
                "external_settlement_handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
                if ready
                else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
                "external_settlement_handoff_ready_for_completion_rerun": ready,
                "external_settlement_capture_inputs_ready": ready,
                "external_settlement_capture_preflight_decision": "CAPTURE_INPUTS_READY"
                if ready
                else "CAPTURE_INPUTS_BLOCKED",
                "external_settlement_handoff_missing_inputs_total": 0 if ready else 5,
                "external_settlement_handoff_operator_actions_total": 6,
                "external_settlement_handoff_operator_commands_total": 5,
                "external_settlement_handoff_operator_command_entrypoints_missing": 0,
                "external_settlement_handoff_operator_command_surface_ready": True,
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "external_settlement_handoff_operator_command_shell_surface_ready": True,
                "external_settlement_handoff_source_errors_total": 0,
                "x0t_governance_execute_readiness_available": True,
                "x0t_governance_execute_decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
                "x0t_governance_execute_ready_now": False,
                "x0t_governance_execute_handoff_available": True,
                "x0t_governance_execute_handoff_clear": True,
                "x0t_governance_execute_handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
                if ready
                else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
                "x0t_governance_execute_handoff_actionable": True,
                "x0t_governance_ready_for_operator_execute": False,
                "x0t_governance_execute_handoff_missing_inputs_total": 0 if ready else 1,
                "x0t_governance_execute_handoff_source_errors_total": 0,
                "x0t_governance_execute_handoff_operator_actions_total": 5,
                "x0t_governance_execute_handoff_operator_commands_total": 5,
                "x0t_governance_execute_handoff_operator_command_entrypoints_missing": 0,
                "x0t_governance_execute_handoff_operator_command_surface_ready": True,
                "x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "x0t_governance_execute_handoff_operator_command_shell_surface_ready": True,
                "x0t_governance_execute_handoff_operator_sequence_ready": True,
                "x0t_governance_proposal_executed": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
            "proposal_state": {
                "state_code": 6 if ready else 4,
                "state_label": "Executed" if ready else "Queued",
                "queued": not ready,
                "executed": ready,
                "vetoed": False,
            },
            "summary": {
                "execute_ready_now": False,
                "proposal_executed": ready,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
            },
            "timelock": {
                "seconds_until_earliest_execution_by_block_time": 0 if ready else 23210,
            },
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
            if ready
            else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
            "handoff_actionable": True,
            "ready_for_operator_execute": False,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "approval_boundary": {
                "approval_env": "X0T_EXECUTE_PROPOSAL_APPROVAL",
                "expected_value": "execute-proposal-1-base-sepolia",
                "can_submit_without_operator_approval": False,
            },
            "summary": {
                "readiness_decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
                "source_errors_total": 0,
                "missing_inputs_total": 0 if ready else 1,
                "operator_actions_total": 5,
                "operator_commands_total": 5,
                "operator_command_entrypoints_missing": 0,
                "operator_command_surface_ready": True,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
                "operator_sequence_ready": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "goal_can_be_marked_complete": ready,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "summary": {},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_CLOSE" if ready else "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
            "summary": {
                "x0t_external_settlement_ready": ready,
                "live_rpc_ready": ready,
                "expected_evidence_file_exists": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-external-settlement-operator-handoff-v6-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
            if ready
            else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
            "decision": "READY_FOR_COMPLETION_RERUN" if ready else "BLOCKED_ON_OPERATOR_EVIDENCE",
            "ready_for_completion_rerun": ready,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "summary": {
                "source_errors_total": 0,
                "capture_preflight_available": True,
                "capture_preflight_decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
                "capture_inputs_ready": ready,
                "missing_inputs_total": 0 if ready else 5,
                "evidence_file_ready": ready,
                "live_rpc_ready": ready,
                "production_import_external_settlement_ready": ready,
                "completion_gate_external_settlement_ready": ready,
                "operator_actions_total": 6,
                "operator_commands_total": 5,
                "operator_command_entrypoints_missing": 0,
                "operator_command_surface_ready": True,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
                "operator_sequence_ready": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_CLOSE" if ready else "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
            "summary": {
                "can_close_image_digests_blocker": ready,
                "raw_deploy_images_total": 7,
                "raw_deploy_images_digest_pinned": 7 if ready else 0,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-collection-checklist-progress-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY" if ready else "OPERATOR_INPUT_REQUIRED",
            "summary": {"items_total": 31, "items_ready": 31 if ready else 0},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "all_packets_actionable": True,
            "operator_priority_order": ["external_settlement"],
            "summary": {"packets_total": 5},
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/production-raw-evidence-operator-packet-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE",
            "local_handoff_complete": True,
            "production_ready": ready,
            "goal_can_be_marked_complete": False,
            "summary": {
                "packets_total": 1,
                "actionable_packets": 1,
                "local_entrypoints_missing": 0,
                "raw_files_total": raw_expected,
                "operator_bundle_files_existing": raw_expected,
                "operator_bundle_files_production_ready": raw_expected if ready else 0,
                "operator_bundle_files_replacement_required": 0 if ready else raw_expected,
                "raw_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS"
                if ready
                else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_readiness_ready_for_collectors": ready,
                "raw_readiness_collectors_ready": 1 if ready else 0,
                "raw_readiness_collectors_blocked": 0 if ready else 1,
                "raw_readiness_collectors_total": 1,
                "raw_readiness_raw_files_ready": raw_expected if ready else 0,
                "raw_readiness_raw_files_local_observation": 0 if ready else raw_expected,
                "raw_readiness_raw_files_total": raw_expected,
                "production_ready_blocked_by_raw_readiness": False,
            },
        },
    )


def _write_production_grade_goal_audit(root: Path) -> None:
    _write_json(
        root,
        DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "next_actions_total": 5,
                "next_actions_operator_input_required": 3,
                "next_actions_operator_approval_required": 1,
                "next_actions_after_blockers": 1,
                "next_actions_generic_blocking": 0,
                "completion_gate_runner_available": True,
                "completion_gate_runner_decision": "NOT_COMPLETE",
                "completion_gate_production_input_return_packet_available": True,
                "completion_gate_production_input_return_packet_decision": (
                    "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
                ),
                "completion_gate_production_input_return_packet_blocking_inputs_total": 31,
                "completion_gate_production_input_return_packet_blocking_raw_inputs": 30,
                "completion_gate_production_input_return_packet_blocking_external_inputs": 1,
                "completion_gate_production_input_return_packet_blocking_inputs_operator_input_required": 31,
                "completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required": 0,
                "completion_gate_production_input_return_packet_operator_next_actions_total": 2,
                "completion_gate_production_input_return_packet_operator_next_actions_operator_input_required": 2,
                "completion_gate_production_input_return_packet_operator_next_actions_generic_blocking": 0,
                "completion_gate_production_input_return_packet_raw_files_expected": 63,
                "completion_gate_production_input_return_packet_raw_files_missing": 33,
                "completion_gate_production_input_return_packet_raw_files_local_observation": 30,
                "completion_gate_x0t_contract_handoff_decision": (
                    "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
                ),
                "completion_gate_x0t_contract_handoff_approval_value_required": (
                    "apply-bridge-address-base-sepolia"
                ),
                "completion_gate_x0t_contract_handoff_missing_inputs_total": 1,
                "completion_gate_x0t_contract_handoff_operator_actions_total": 6,
                "completion_gate_x0t_contract_handoff_operator_approval_required_actions_total": 1,
                "completion_gate_x0t_contract_handoff_operator_commands_total": 5,
                "completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready": True,
                "completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "completion_gate_x0t_contract_handoff_operator_sequence_ready": True,
                "completion_gate_live_rollout_handoff_decision": (
                    "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
                ),
                "completion_gate_live_rollout_handoff_missing_inputs_total": 1,
                "completion_gate_live_rollout_handoff_operator_actions_total": 5,
                "completion_gate_live_rollout_handoff_operator_input_required_actions_total": 2,
                "completion_gate_live_rollout_handoff_operator_commands_total": 4,
                "completion_gate_live_rollout_handoff_operator_command_shell_surface_ready": True,
                "completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "completion_gate_live_rollout_handoff_operator_sequence_ready": True,
            },
            "next_actions": [
                {
                    "id": "replace_operator_evidence",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "action": "Replace operator evidence.",
                },
                {
                    "id": "provide_x0t_bridge_contract_address",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "action": "Provide bridge address.",
                    "source_artifact": ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json",
                },
                {
                    "id": "apply_x0t_bridge_contract_address_with_approval",
                    "status": "OPERATOR_APPROVAL_REQUIRED",
                    "action": "Apply bridge address.",
                    "approval_value_required": "apply-bridge-address-base-sepolia",
                },
                {
                    "id": "return_live_rollout_image_digest_provenance",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "action": "Return image digest provenance.",
                },
                {
                    "id": "rerun_production_closeout",
                    "status": "AFTER_BLOCKERS",
                    "action": "Rerun production closeout.",
                },
            ],
        },
    )


def _mark_governance_ready_for_operator(root: Path) -> None:
    gap_path = root / ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
    gap = json.loads(gap_path.read_text(encoding="utf-8"))
    gap_summary = gap.setdefault("summary", {})
    gap_summary.update(
        {
            "x0t_governance_execute_decision": "READY_TO_EXECUTE",
            "x0t_governance_execute_ready_now": True,
            "x0t_governance_execute_handoff_decision": (
                "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
            ),
            "x0t_governance_ready_for_operator_execute": True,
            "x0t_governance_execute_handoff_missing_inputs_total": 2,
            "x0t_governance_proposal_executed": False,
        }
    )
    gap_path.write_text(json.dumps(gap), encoding="utf-8")

    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_EXECUTE",
            "proposal_state": {
                "state_code": 5,
                "state_label": "Ready",
                "queued": True,
                "executed": False,
                "vetoed": False,
            },
            "summary": {
                "execute_ready_now": True,
                "proposal_executed": False,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
            },
            "timelock": {"seconds_until_earliest_execution_by_block_time": 0},
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
            "handoff_actionable": True,
            "ready_for_operator_execute": True,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "approval_boundary": {
                "approval_env": "X0T_EXECUTE_PROPOSAL_APPROVAL",
                "expected_value": "execute-proposal-1-base-sepolia",
                "can_submit_without_operator_approval": False,
            },
            "summary": {
                "readiness_decision": "READY_TO_EXECUTE",
                "source_errors_total": 0,
                "missing_inputs_total": 2,
                "operator_actions_total": 5,
                "operator_commands_total": 5,
                "operator_command_entrypoints_missing": 0,
                "operator_command_surface_ready": True,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
                "operator_sequence_ready": True,
            },
        },
    )


def test_objective_coverage_audit_reports_blocked_raw_counts_from_return_acceptance(tmp_path):
    _base_artifacts(tmp_path, ready=False)

    report = build_report(tmp_path)

    assert report["schema_version"].endswith("v4-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["local_integration_ready"] is True
    assert report["production_ready"] is False
    summary = report["summary"]
    assert summary["current_raw_files_installed"] == 0
    assert summary["return_acceptance_raw_files_staged"] == 0
    assert summary["return_acceptance_raw_files_local_observation"] == 2
    assert summary["pipeline_raw_files_reported_installed"] == 0
    pipeline_row = next(row for row in report["prompt_to_artifact_checklist"] if row["id"] == "goal_audit:production_input_pipeline")
    assert pipeline_row["status"] == "VERIFIED_LOCAL_PRODUCTION_GAP"
    assert pipeline_row["evidence"]["raw_files_installed"] == 0
    assert "goal_audit:production_input_pipeline" in report["blocking_row_ids"]
    cross_plane_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "goal_audit:cross_plane_proof_gate"
    )
    assert cross_plane_row["local_ready"] is True
    assert cross_plane_row["production_ready"] is False
    assert cross_plane_row["evidence"]["claims_blocked"] == len(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS)
    assert "goal_audit:cross_plane_proof_gate" in report["blocking_row_ids"]
    assert summary["cross_plane_proof_gate_available"] is True
    assert summary["cross_plane_proof_gate_allowed"] is False
    assert summary["cross_plane_proof_gate_claims_blocked"] == len(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS)
    assert "external-dpi-proof-missing" in summary["cross_plane_proof_gate_open_gap_ids"]
    raw_packet_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "goal_audit:production_raw_evidence_operator_packet"
    )
    assert raw_packet_row["local_ready"] is True
    assert raw_packet_row["production_ready"] is False
    assert summary["raw_operator_packet_files_replacement_required"] == 2
    assert summary["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert summary["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert summary["raw_operator_packet_readiness_collectors_ready"] == 0
    assert summary["raw_operator_packet_readiness_collectors_blocked"] == 1
    assert summary["raw_operator_packet_readiness_collectors_total"] == 1
    assert summary["raw_operator_packet_readiness_raw_files_ready"] == 0
    assert summary["raw_operator_packet_readiness_raw_files_local_observation"] == 2
    assert summary["raw_operator_packet_readiness_raw_files_total"] == 2
    assert summary["external_settlement_handoff_available"] is True
    assert summary["external_settlement_handoff_clear"] is True
    assert summary["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert summary["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert summary["external_settlement_handoff_operator_command_entrypoints_missing"] == 0
    assert summary["external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert summary["external_settlement_handoff_operator_command_shell_surface_ready"] is True
    assert summary["x0t_governance_execute_readiness_available"] is True
    assert summary["x0t_governance_execute_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert summary["x0t_governance_execute_handoff_available"] is True
    assert summary["x0t_governance_execute_handoff_clear"] is True
    assert summary["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    )
    assert summary["x0t_governance_execute_handoff_actionable"] is True
    assert summary["x0t_governance_proposal_executed"] is False
    assert summary["x0t_governance_execute_handoff_operator_commands_total"] == 5
    assert summary["x0t_governance_execute_handoff_operator_command_entrypoints_missing"] == 0
    assert summary["x0t_governance_execute_handoff_operator_command_surface_ready"] is True
    assert summary["x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert summary["x0t_governance_execute_handoff_operator_command_shell_surface_ready"] is True
    assert summary["x0t_governance_execute_handoff_operator_sequence_ready"] is True
    assert summary["closeout_operator_handoff_source_artifact"] == (
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
    )
    assert summary["closeout_operator_handoff_source_available"] is True
    assert summary["closeout_operator_handoff_source_errors_total"] == 0
    assert summary["closeout_x0t_governance_handoff_operator_actions_total"] == 5
    assert summary["closeout_x0t_governance_handoff_operator_commands_total"] == 5
    assert summary["closeout_x0t_governance_handoff_operator_sequence_ready"] is True
    assert summary["closeout_external_settlement_handoff_operator_actions_total"] == 6
    assert summary["closeout_external_settlement_handoff_operator_commands_total"] == 5
    assert summary["closeout_external_settlement_handoff_operator_sequence_ready"] is True
    assert summary["closeout_x0t_contract_handoff_available"] is True
    assert summary["closeout_x0t_contract_handoff_decision"] == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    assert summary["closeout_x0t_contract_handoff_deployment_ready"] is False
    assert summary["closeout_x0t_contract_handoff_operator_actions_total"] == 6
    assert summary["closeout_x0t_contract_handoff_operator_commands_total"] == 5
    assert summary["closeout_x0t_contract_handoff_operator_sequence_ready"] is True
    assert summary["closeout_live_rollout_handoff_available"] is True
    assert summary["closeout_live_rollout_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert summary["closeout_live_rollout_handoff_ready_for_completion_rerun"] is False
    assert summary["closeout_live_rollout_handoff_operator_actions_total"] == 5
    assert summary["closeout_live_rollout_handoff_operator_commands_total"] == 4
    assert summary["closeout_live_rollout_handoff_operator_command_entrypoints_missing"] == 0
    assert summary["closeout_live_rollout_handoff_operator_sequence_ready"] is True
    handoff_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "external_settlement_operator_handoff"
    )
    assert handoff_row["local_ready"] is True
    assert handoff_row["production_ready"] is False
    assert ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json" in handoff_row["artifact_paths"]
    assert handoff_row["evidence"]["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert handoff_row["evidence"]["operator_commands_total"] == 5
    governance_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "x0t_governance_execute_handoff"
    )
    assert governance_row["local_ready"] is True
    assert governance_row["production_ready"] is False
    assert ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json" in governance_row[
        "artifact_paths"
    ]
    assert governance_row["evidence"]["handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    )
    assert governance_row["evidence"]["operator_commands_total"] == 5
    assert governance_row["evidence"]["operator_sequence_ready"] is True
    next_actions = {item["id"]: item for item in report["next_actions"]}
    external_action = next_actions["submit_external_settlement_receipt"]
    assert external_action["status"] == "OPERATOR_INPUT_REQUIRED"
    assert external_action["handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert external_action["ready_for_completion_rerun"] is False
    assert external_action["capture_inputs_ready"] is False
    raw_action = next_actions["replace_semantically_blocked_raw_evidence"]
    assert raw_action["status"] == "OPERATOR_INPUT_REQUIRED"
    assert raw_action["raw_operator_packet_decision"] == "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE"
    assert raw_action["raw_operator_packet_local_handoff_complete"] is True
    assert raw_action["raw_operator_packet_files_replacement_required"] == 2
    assert raw_action["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert raw_action["raw_operator_packet_readiness_raw_files_local_observation"] == 2
    assert raw_action["raw_inventory_files_total"] == 2
    assert raw_action["raw_inventory_usable_for_goal_completion"] == 0
    governance_action = next_actions["execute_x0t_governance_proposal_after_timelock"]
    assert governance_action["status"] == "BLOCKING"
    assert governance_action["readiness_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert governance_action["requires_operator_approval"] is True
    assert governance_action["submits_transaction"] is True
    assert governance_action["approval_value_required"] == "execute-proposal-1-base-sepolia"
    assert governance_action["commands"][0].endswith("--require-ready")
    assert governance_action["commands"][1] == "python3 execute_dao_proposal.py --dry-run"
    assert governance_action["commands"][2] == (
        "X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia "
        "PRIVATE_KEY=\"$PRIVATE_KEY\" python3 execute_dao_proposal.py"
    )
    assert governance_action["required_artifact"] == (
        ".tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json"
    )
    proof_gate_action = next_actions["clear_cross_plane_proof_gate"]
    assert proof_gate_action["status"] == "BLOCKING"
    assert proof_gate_action["source_artifact"] == DEFAULT_CROSS_PLANE_PROOF_GATE
    assert proof_gate_action["requested_claim_ids"] == list(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS)
    assert "claim_blocked:dpi_bypass" in proof_gate_action["blocker_ids"]


def test_objective_coverage_promotes_production_grade_next_actions(tmp_path):
    _base_artifacts(tmp_path, ready=False)
    _write_production_grade_goal_audit(tmp_path)

    report = build_report(tmp_path)
    summary = report["summary"]
    next_actions = {item["id"]: item for item in report["next_actions"]}
    production_grade_actions = {item["id"]: item for item in report["production_grade_next_actions"]}

    assert summary["production_grade_goal_audit_available"] is True
    assert summary["production_grade_goal_decision"] == "NOT_COMPLETE"
    assert summary["production_grade_goal_can_be_marked_complete"] is False
    assert summary["production_grade_next_actions_total"] == 5
    assert summary["production_grade_next_actions_operator_input_required"] == 3
    assert summary["production_grade_next_actions_operator_approval_required"] == 1
    assert summary["production_grade_next_actions_after_blockers"] == 1
    assert summary["production_grade_next_actions_generic_blocking"] == 0
    assert summary["production_grade_completion_gate_runner_available"] is True
    assert summary["production_grade_completion_gate_runner_decision"] == "NOT_COMPLETE"
    assert summary["production_grade_completion_gate_production_input_return_packet_available"] is True
    assert summary["production_grade_completion_gate_production_input_return_packet_decision"] == (
        "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    )
    assert summary["production_grade_completion_gate_production_input_return_packet_blocking_inputs_total"] == 31
    assert summary["production_grade_completion_gate_production_input_return_packet_blocking_raw_inputs"] == 30
    assert summary["production_grade_completion_gate_production_input_return_packet_blocking_external_inputs"] == 1
    assert summary[
        "production_grade_completion_gate_production_input_return_packet_blocking_inputs_operator_input_required"
    ] == 31
    assert summary[
        "production_grade_completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required"
    ] == 0
    assert summary["production_grade_completion_gate_production_input_return_packet_operator_next_actions_total"] == 2
    assert summary[
        "production_grade_completion_gate_production_input_return_packet_operator_next_actions_operator_input_required"
    ] == 2
    assert summary[
        "production_grade_completion_gate_production_input_return_packet_operator_next_actions_generic_blocking"
    ] == 0
    assert summary["production_grade_completion_gate_production_input_return_packet_raw_files_expected"] == 63
    assert summary["production_grade_completion_gate_production_input_return_packet_raw_files_missing"] == 33
    assert summary["production_grade_completion_gate_production_input_return_packet_raw_files_local_observation"] == 30
    assert summary["production_grade_completion_gate_x0t_contract_handoff_decision"] == (
        "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    )
    assert summary["production_grade_completion_gate_x0t_contract_handoff_approval_value_required"] == (
        "apply-bridge-address-base-sepolia"
    )
    assert summary["production_grade_completion_gate_x0t_contract_handoff_missing_inputs_total"] == 1
    assert summary["production_grade_completion_gate_x0t_contract_handoff_operator_actions_total"] == 6
    assert summary[
        "production_grade_completion_gate_x0t_contract_handoff_operator_approval_required_actions_total"
    ] == 1
    assert summary["production_grade_completion_gate_x0t_contract_handoff_operator_commands_total"] == 5
    assert summary[
        "production_grade_completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready"
    ] is True
    assert summary[
        "production_grade_completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"
    ] == 0
    assert summary["production_grade_completion_gate_x0t_contract_handoff_operator_sequence_ready"] is True
    assert summary["production_grade_completion_gate_live_rollout_handoff_decision"] == (
        "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    )
    assert summary["production_grade_completion_gate_live_rollout_handoff_missing_inputs_total"] == 1
    assert summary["production_grade_completion_gate_live_rollout_handoff_operator_actions_total"] == 5
    assert summary[
        "production_grade_completion_gate_live_rollout_handoff_operator_input_required_actions_total"
    ] == 2
    assert summary["production_grade_completion_gate_live_rollout_handoff_operator_commands_total"] == 4
    assert summary[
        "production_grade_completion_gate_live_rollout_handoff_operator_command_shell_surface_ready"
    ] is True
    assert summary[
        "production_grade_completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"
    ] == 0
    assert summary["production_grade_completion_gate_live_rollout_handoff_operator_sequence_ready"] is True
    assert production_grade_actions["replace_operator_evidence"]["source"] == "production_grade_goal_audit"
    assert production_grade_actions["replace_operator_evidence"]["source_artifact"] == DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT
    assert next_actions["provide_x0t_bridge_contract_address"]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert next_actions["apply_x0t_bridge_contract_address_with_approval"]["status"] == (
        "OPERATOR_APPROVAL_REQUIRED"
    )
    assert next_actions["apply_x0t_bridge_contract_address_with_approval"]["approval_value_required"] == (
        "apply-bridge-address-base-sepolia"
    )
    assert next_actions["return_live_rollout_image_digest_provenance"]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert next_actions["rerun_production_closeout"]["status"] == "AFTER_BLOCKERS"


def test_objective_coverage_marks_ready_governance_action_as_operator_approval_required(tmp_path):
    _base_artifacts(tmp_path, ready=False)
    _mark_governance_ready_for_operator(tmp_path)

    report = build_report(tmp_path)
    next_actions = {item["id"]: item for item in report["next_actions"]}
    governance_action = next_actions["execute_x0t_governance_proposal_after_timelock"]

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["x0t_governance_execute_decision"] == "READY_TO_EXECUTE"
    assert report["summary"]["x0t_governance_execute_ready_now"] is True
    assert report["summary"]["x0t_governance_ready_for_operator_execute"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is False
    assert governance_action["status"] == "OPERATOR_APPROVAL_REQUIRED"
    assert governance_action["readiness_decision"] == "READY_TO_EXECUTE"
    assert governance_action["ready_for_operator_execute"] is True
    assert governance_action["requires_operator_approval"] is True
    assert governance_action["submits_transaction"] is True


def test_objective_coverage_requires_cross_plane_proof_gate_artifact(tmp_path):
    _base_artifacts(tmp_path, ready=True)
    (tmp_path / DEFAULT_CROSS_PLANE_PROOF_GATE).unlink()

    report = build_report(tmp_path)

    cross_plane_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "goal_audit:cross_plane_proof_gate"
    )
    next_actions = {item["id"]: item for item in report["next_actions"]}

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert any(DEFAULT_CROSS_PLANE_PROOF_GATE in error for error in report["source_errors"])
    assert cross_plane_row["local_ready"] is False
    assert cross_plane_row["production_ready"] is False
    assert "cross_plane_proof_gate_missing" in cross_plane_row["evidence"]["blocker_ids"]
    assert report["summary"]["cross_plane_proof_gate_available"] is False
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert next_actions["clear_cross_plane_proof_gate"]["status"] == "BLOCKING"
    command = next_actions["clear_cross_plane_proof_gate"]["command"]
    assert f"--output-json {DEFAULT_CROSS_PLANE_PROOF_GATE}" in command
    assert " > " not in command


def test_objective_coverage_audit_can_complete_when_all_sources_are_ready(tmp_path):
    _base_artifacts(tmp_path, ready=True)

    report = build_report(tmp_path)

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["current_raw_files_installed"] == 2
    assert report["summary"]["raw_operator_packet_files_production_ready"] == 2
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is True
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 2
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 0
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 0
    assert report["summary"]["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["x0t_governance_execute_decision"] == "ALREADY_EXECUTED"
    assert report["summary"]["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
    )
    assert report["summary"]["x0t_governance_proposal_executed"] is True
    assert report["summary"]["closeout_operator_handoff_source_available"] is True
    assert report["summary"]["closeout_x0t_governance_handoff_operator_sequence_ready"] is True
    assert report["summary"]["closeout_external_settlement_handoff_operator_sequence_ready"] is True
    assert report["summary"]["closeout_x0t_contract_handoff_deployment_ready"] is True
    assert report["summary"]["closeout_live_rollout_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["cross_plane_proof_gate_available"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_claims_blocked"] == 0
    handoff_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "external_settlement_operator_handoff"
    )
    assert handoff_row["local_ready"] is True
    assert handoff_row["production_ready"] is True
    governance_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "x0t_governance_execute_handoff"
    )
    assert governance_row["local_ready"] is True
    assert governance_row["production_ready"] is True
    cross_plane_row = next(
        row for row in report["prompt_to_artifact_checklist"] if row["id"] == "goal_audit:cross_plane_proof_gate"
    )
    assert cross_plane_row["local_ready"] is True
    assert cross_plane_row["production_ready"] is True
    next_actions = {item["id"]: item for item in report["next_actions"]}
    assert next_actions["submit_external_settlement_receipt"]["status"] == "DONE"
    assert next_actions["replace_semantically_blocked_raw_evidence"]["status"] == "DONE"
    assert next_actions["execute_x0t_governance_proposal_after_timelock"]["status"] == "DONE"
    assert next_actions["clear_cross_plane_proof_gate"]["status"] == "DONE"
    assert report["summary"]["coverage_rows_blocking"] > 0
    assert "goal_audit:broad_production_hardening" in report["blocking_row_ids"]
    assert "goal_audit:cross_plane_proof_gate" not in report["blocking_row_ids"]


def test_objective_coverage_audit_cli_require_complete_returns_two_when_blocked(tmp_path):
    _base_artifacts(tmp_path, ready=False)
    output_json = tmp_path / "coverage.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output_json), "--require-complete"])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["completion_decision"] == "NOT_COMPLETE"
    assert payload["summary"]["current_raw_files_installed"] == 0
    assert payload["summary"]["closeout_operator_handoff_source_available"] is True
    assert payload["summary"]["closeout_external_settlement_handoff_operator_sequence_ready"] is True
    assert payload["summary"]["closeout_x0t_contract_handoff_operator_sequence_ready"] is True
    assert payload["summary"]["closeout_live_rollout_handoff_operator_sequence_ready"] is True
