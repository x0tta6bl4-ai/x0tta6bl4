import json
from pathlib import Path

from src.integration.completion_gate_runner import build_report, main


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


def _write_governance_execute_readiness(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
            "proposal_state": {
                "state_label": "Executed" if ready else "Queued",
                "executed": ready,
                "vetoed": False,
            },
            "timelock": {
                "seconds_until_earliest_execution_by_block_time": 0 if ready else 23210,
            },
            "summary": {
                "execute_ready_now": False,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
            },
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
        },
    )


def _base_sources(root: Path, *, ready: bool) -> None:
    raw_expected = 2
    raw_staged = raw_expected if ready else 0
    _write_governance_execute_readiness(root, ready=ready)
    _write_cross_plane_proof_gate(root, allowed=ready)
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
                "blocking_inputs_total": 0 if ready else 3,
                "blocking_external_inputs": 0 if ready else 1,
                "blocking_raw_inputs": 0,
                "collector_evidence_blockers": 0 if ready else 2,
                "raw_files_expected": raw_expected,
                "raw_files_installed": raw_staged,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-packet-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-input-return-packet-v2-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RETURN_PACKET_READY" if ready else "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "blocking_inputs_total": 0 if ready else raw_expected + 1,
                "blocking_raw_inputs": 0 if ready else raw_expected,
                "blocking_external_inputs": 0 if ready else 1,
                "blocking_inputs_operator_input_required": 0 if ready else raw_expected + 1,
                "blocking_inputs_generic_operator_required": 0,
                "operator_next_actions_total": 0 if ready else 2,
                "operator_next_actions_operator_input_required": 0 if ready else 2,
                "operator_next_actions_generic_blocking": 0,
                "raw_files_expected": raw_expected,
                "raw_files_missing": 0,
                "raw_files_local_observation": 0 if ready else raw_expected,
                "external_artifacts_operator_required": 0 if ready else 1,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "summary": {
                "raw_files_expected": raw_expected,
                "raw_files_staged": raw_staged,
                "raw_files_local_observation": 0 if ready else raw_expected,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR" if ready else "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR",
            "production_ready": ready,
            "summary": {
                "required_evidence_files_total": 3,
                "required_evidence_files_ready": 3 if ready else 0,
                "external_required_evidence_files_total": 1,
                "external_required_evidence_files_ready": 1 if ready else 0,
                "raw_operator_packet_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS"
                if ready
                else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_operator_packet_readiness_ready_for_collectors": ready,
                "raw_operator_packet_readiness_collectors_ready": 1 if ready else 0,
                "raw_operator_packet_readiness_collectors_blocked": 0 if ready else 1,
                "raw_operator_packet_readiness_collectors_total": 1,
                "raw_operator_packet_readiness_raw_files_ready": raw_expected if ready else 0,
                "raw_operator_packet_readiness_raw_files_local_observation": 0 if ready else raw_expected,
                "raw_operator_packet_readiness_raw_files_total": raw_expected,
                "raw_operator_packet_production_ready_blocked_by_raw_readiness": False,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json",
        {"status": "VERIFIED HERE", "ok": True, "decision": "ROLLUP_APPROVAL_READY" if ready else "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE", "ready": ready, "summary": {}},
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-closeout-review-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "CLOSEOUT_REVIEW_READY" if ready else "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
            "ready": ready,
            "summary": {
                "x0t_contract_handoff_available": True,
                "x0t_contract_handoff_decision": "X0T_CONTRACT_DEPLOYMENT_CONFIG_READY"
                if ready
                else "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR",
                "x0t_contract_handoff_deployment_ready": ready,
                "x0t_contract_handoff_approval_value_required": "apply-bridge-address-base-sepolia",
                "x0t_contract_handoff_missing_inputs_total": 0 if ready else 1,
                "x0t_contract_handoff_operator_actions_total": 0 if ready else 6,
                "x0t_contract_handoff_operator_approval_required_actions_total": 0 if ready else 1,
                "x0t_contract_handoff_operator_commands_total": 0 if ready else 5,
                "x0t_contract_handoff_operator_command_entrypoints_missing": 0,
                "x0t_contract_handoff_operator_command_surface_ready": False if ready else True,
                "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "x0t_contract_handoff_operator_command_shell_surface_ready": True,
                "x0t_contract_handoff_operator_sequence_ready": not ready,
                "live_rollout_handoff_available": True,
                "live_rollout_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
                if ready
                else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
                "live_rollout_handoff_ready_for_completion_rerun": ready,
                "live_rollout_handoff_can_close_image_digests_blocker": ready,
                "live_rollout_handoff_missing_inputs_total": 0 if ready else 1,
                "live_rollout_handoff_operator_actions_total": 0 if ready else 5,
                "live_rollout_handoff_operator_input_required_actions_total": 0 if ready else 2,
                "live_rollout_handoff_operator_commands_total": 0 if ready else 4,
                "live_rollout_handoff_operator_command_entrypoints_missing": 0,
                "live_rollout_handoff_operator_command_surface_ready": False if ready else True,
                "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "live_rollout_handoff_operator_command_shell_surface_ready": True,
                "live_rollout_handoff_operator_sequence_ready": not ready,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-closure-preflight-current.json",
        {"status": "VERIFIED HERE", "ok": True, "decision": "PREFLIGHT_READY_FOR_FINAL_REVIEW" if ready else "PREFLIGHT_BLOCKED_ON_OPERATOR_EVIDENCE", "ready": ready, "summary": {}},
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-final-review-current.json",
        {"status": "VERIFIED HERE", "ok": True, "decision": "FINAL_REVIEW_READY" if ready else "FINAL_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE", "ready": ready, "summary": {}},
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "goal_can_be_marked_complete": ready,
            "summary": {
                "current_raw_files_installed": raw_staged,
                "semantic_blocking_items_total": 0 if ready else 121,
                "semantic_preflight_errors_total": 0 if ready else 120,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-completion-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
            "goal_can_be_marked_complete": ready,
            "summary": {
                "checklist_total": 48,
                "checklist_passed": 48 if ready else 40,
                "checklist_blocking": 0 if ready else 8,
                "local_wiring_passed": True,
                "production_readiness_passed": ready,
                "external_settlement_handoff_clear": True,
                "external_settlement_handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
                if ready
                else "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
                "external_settlement_handoff_ready_for_completion_rerun": ready,
                "external_settlement_capture_preflight_decision": "CAPTURE_INPUTS_READY"
                if ready
                else "CAPTURE_INPUTS_BLOCKED",
                "external_settlement_handoff_operator_command_entrypoints_missing": 0,
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "external_settlement_handoff_operator_command_shell_surface_ready": True,
                "x0t_governance_execute_decision": "ALREADY_EXECUTED" if ready else "NOT_READY_TIMELOCK_ACTIVE",
                "x0t_governance_execute_ready_now": False,
                "x0t_governance_handoff_operator_actions_total": 5,
                "x0t_governance_handoff_operator_commands_total": 5,
                "x0t_governance_handoff_operator_command_entrypoints_missing": 0,
                "x0t_governance_handoff_operator_command_surface_ready": True,
                "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "x0t_governance_handoff_operator_command_shell_surface_ready": True,
                "x0t_governance_handoff_operator_sequence_ready": True,
                "x0t_governance_proposal_executed": ready,
                "x0t_governance_state_label": "Executed" if ready else "Queued",
                "x0t_governance_next_executable_after_utc": "2026-05-21T04:45:22Z",
                "x0t_governance_seconds_until_earliest_execution_by_block_time": 0 if ready else 23210,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {"status": "VERIFIED HERE", "ok": True, "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE", "goal_can_be_marked_complete": ready, "summary": {}},
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
        {"status": "VERIFIED HERE", "ok": True, "decision": "NO_PRODUCTION_EVIDENCE_GAPS" if ready else "BLOCKED_ON_OPERATOR_EVIDENCE", "goal_can_be_marked_complete": ready, "summary": {}},
    )


def test_completion_gate_runner_fails_closed_on_current_blockers(tmp_path):
    _base_sources(tmp_path, ready=False)

    report = build_report(tmp_path)

    assert report["schema_version"].endswith("v6-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["local_completion_ready"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["local_completion_ready"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert report["summary"]["current_raw_files_installed"] == 0
    assert report["summary"]["pipeline_raw_files_reported_installed"] == 0
    assert report["summary"]["coverage_raw_files_reported_installed"] == 0
    assert report["summary"]["production_input_return_packet_available"] is True
    assert report["summary"]["production_input_return_packet_decision"] == (
        "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    )
    assert report["summary"]["production_input_return_packet_blocking_inputs_total"] == 3
    assert report["summary"]["production_input_return_packet_blocking_raw_inputs"] == 2
    assert report["summary"]["production_input_return_packet_blocking_external_inputs"] == 1
    assert report["summary"]["production_input_return_packet_blocking_inputs_operator_input_required"] == 3
    assert report["summary"]["production_input_return_packet_blocking_inputs_generic_operator_required"] == 0
    assert report["summary"]["production_input_return_packet_operator_next_actions_total"] == 2
    assert report["summary"]["production_input_return_packet_operator_next_actions_operator_input_required"] == 2
    assert report["summary"]["production_input_return_packet_operator_next_actions_generic_blocking"] == 0
    assert report["summary"]["production_input_return_packet_raw_files_expected"] == 2
    assert report["summary"]["production_input_return_packet_raw_files_missing"] == 0
    assert report["summary"]["production_input_return_packet_raw_files_local_observation"] == 2
    assert report["summary"]["production_input_return_packet_external_artifacts_operator_required"] == 1
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 2
    assert report["summary"]["required_evidence_files_ready"] == 0
    assert report["summary"]["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 0
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 1
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 2
    assert report["summary"]["raw_operator_packet_readiness_raw_files_total"] == 2
    assert report["summary"]["semantic_blocking_items_total"] == 121
    assert report["summary"]["semantic_preflight_errors_total"] == 120
    assert report["summary"]["x0t_governance_execute_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert report["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_commands_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is False
    assert report["summary"]["external_settlement_handoff_clear"] is True
    assert report["summary"]["external_settlement_handoff_decision"] == (
        "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert report["summary"]["external_settlement_capture_preflight_decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert report["summary"]["external_settlement_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["external_settlement_handoff_operator_command_shell_surface_ready"] is True
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
    assert report["summary"]["steps_ready"] == 0
    assert report["source_errors"] == []


def test_completion_gate_runner_can_complete_when_sources_complete(tmp_path):
    _base_sources(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)

    report = build_report(tmp_path)

    assert report["completion_decision"] == "COMPLETE"
    assert report["local_completion_ready"] is True
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["local_completion_ready"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_proof_gate"]["source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["summary"]["steps_ready"] == report["summary"]["steps_total"]
    assert report["summary"]["current_raw_files_installed"] == 2
    assert report["summary"]["production_input_return_packet_available"] is True
    assert report["summary"]["production_input_return_packet_decision"] == "RETURN_PACKET_READY"
    assert report["summary"]["production_input_return_packet_blocking_inputs_total"] == 0
    assert report["summary"]["production_input_return_packet_blocking_raw_inputs"] == 0
    assert report["summary"]["production_input_return_packet_operator_next_actions_total"] == 0
    assert report["summary"]["required_evidence_files_ready"] == 3
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is True
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 2
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 0
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 0
    assert report["summary"]["x0t_governance_execute_decision"] == "ALREADY_EXECUTED"
    assert report["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_commands_total"] == 5
    assert report["summary"]["x0t_governance_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_command_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert report["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is True
    assert report["summary"]["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["x0t_contract_handoff_deployment_ready"] is True
    assert report["summary"]["x0t_contract_handoff_operator_actions_total"] == 0
    assert report["summary"]["x0t_contract_handoff_operator_commands_total"] == 0
    assert report["summary"]["live_rollout_handoff_ready_for_completion_rerun"] is True
    assert report["summary"]["live_rollout_handoff_operator_actions_total"] == 0
    assert report["summary"]["live_rollout_handoff_operator_commands_total"] == 0


def test_completion_gate_runner_blocks_complete_without_current_evidence_context(tmp_path):
    _base_sources(tmp_path, ready=True)

    report = build_report(tmp_path)

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["local_completion_ready"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["completion_blocked_by_current_evidence"] is True
    assert report["summary"]["completion_blocked_by_cross_plane_proof_gate"] is False
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False


def test_completion_gate_runner_blocks_complete_when_cross_plane_proof_gate_blocks(tmp_path):
    _base_sources(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = build_report(tmp_path)

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["local_completion_ready"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["completion_blocked_by_cross_plane_proof_gate"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_completion_gate_runner_blocks_complete_on_current_evidence_open_gap(tmp_path):
    _base_sources(tmp_path, ready=True)
    _write_current_evidence_context(
        tmp_path,
        current_gaps=[{"id": "external-dpi-proof-missing", "blocks_real_readiness": True}],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    report = build_report(tmp_path)

    assert report["completion_decision"] == "NOT_COMPLETE"
    assert report["local_completion_ready"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_completion_gate_runner_cli_require_complete_returns_two_when_blocked(tmp_path):
    _base_sources(tmp_path, ready=False)
    output_json = tmp_path / "gate.json"

    exit_code = main(["--root", str(tmp_path), "--output-json", str(output_json), "--require-complete"])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["completion_decision"] == "NOT_COMPLETE"
    assert payload["summary"]["current_raw_files_installed"] == 0
    assert payload["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert payload["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
