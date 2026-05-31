import json
from pathlib import Path

import pytest

from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS
from src.integration.production_gap_index import ProductionGapIndexGate, main, render_markdown


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_current_evidence_context(
    root: Path,
    *,
    current_gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
) -> None:
    _write_json(
        root / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
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
        root / ".tmp/validation-shards/cross-plane-proof-gate-current.json",
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


def _governance_execute_readiness(path: Path, *, executed: bool) -> Path:
    _write_json(
        path,
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALREADY_EXECUTED" if executed else "READY_TO_EXECUTE",
            "proposal_state": {
                "state_label": "Executed" if executed else "Ready",
                "executed": executed,
                "vetoed": False,
            },
            "summary": {
                "execute_ready_now": not executed,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
            },
            "timelock": {
                "seconds_until_earliest_execution_by_block_time": 0,
            },
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
        },
    )
    return path


def _governance_execute_handoff(
    path: Path,
    *,
    readiness_decision: str = "READY_TO_EXECUTE",
    executed: bool = False,
) -> Path:
    missing_inputs = [] if executed or readiness_decision == "READY_TO_EXECUTE" else [
        {
            "id": "ready_execute_state",
            "reason": f"readiness decision is {readiness_decision}, not READY_TO_EXECUTE",
            "command": "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md --require-ready",
            "status": "WAIT_FOR_CHAIN_STATE",
        }
    ]
    operator_next_actions = [
        {
            "id": "refresh_readiness",
            "status": "DONE",
            "command": "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md",
            "submits_transaction": False,
        },
        {
            "id": "dry_run_execute_boundary",
            "status": "AFTER_READY_STATE",
            "command": "python3 execute_dao_proposal.py --dry-run",
            "submits_transaction": False,
        },
        {
            "id": "execute_with_operator_approval",
            "status": "AFTER_READY_STATE",
            "command": (
                "X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia "
                "PRIVATE_KEY=\"$PRIVATE_KEY\" python3 execute_dao_proposal.py"
            ),
            "requires_operator_approval": True,
            "submits_transaction": True,
        },
        {
            "id": "retain_execution_receipt",
            "status": "AFTER_EXECUTE",
            "required_artifact": ".tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json",
            "acceptance_rule": "receipt ok=true only when tx receipt status is 1 and final proposal state is Executed",
        },
        {
            "id": "rerun_completion_and_gap",
            "status": "AFTER_EXECUTE",
            "commands": [
                (
                    "python3 -m src.integration.completion_audit --root . "
                    "--output-json .tmp/validation-shards/integration-spine-completion-audit-current.json "
                    "--output-md docs/verification/integration-spine-completion-audit-2026-05-20.md"
                ),
                (
                    "python3 -m src.integration.production_gap_index --root . "
                    "--output-json .tmp/validation-shards/integration-spine-production-gap-index-current.json "
                    "--output-md docs/verification/integration-spine-production-gap-index-2026-05-20.md"
                ),
            ],
            "submits_transaction": False,
        },
    ]
    operator_command_checks = [
        {
            "action_id": "refresh_readiness",
            "command": operator_next_actions[0]["command"],
            "entrypoint_exists": True,
            "expected_entrypoint": "scripts/ops/check_x0t_governance_execute_readiness.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY",
        },
        {
            "action_id": "dry_run_execute_boundary",
            "command": operator_next_actions[1]["command"],
            "entrypoint_exists": True,
            "expected_entrypoint": "execute_dao_proposal.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY",
        },
        {
            "action_id": "execute_with_operator_approval",
            "command": operator_next_actions[2]["command"],
            "entrypoint_exists": True,
            "expected_entrypoint": "execute_dao_proposal.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY",
        },
        {
            "action_id": "rerun_completion_and_gap",
            "command": operator_next_actions[4]["commands"][0],
            "entrypoint_exists": True,
            "expected_entrypoint": "src/integration/completion_audit.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY",
        },
        {
            "action_id": "rerun_completion_and_gap",
            "command": operator_next_actions[4]["commands"][1],
            "entrypoint_exists": True,
            "expected_entrypoint": "src/integration/production_gap_index.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY",
        },
    ]
    _write_json(
        path,
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
            if executed
            else "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
            "handoff_actionable": True,
            "ready_for_operator_execute": not executed,
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
                "readiness_decision": "ALREADY_EXECUTED" if executed else readiness_decision,
                "source_errors_total": 0,
                "missing_inputs_total": len(missing_inputs),
                "operator_actions_total": 5,
                "operator_commands_total": 5,
                "operator_command_entrypoints_missing": 0,
                "operator_command_surface_ready": True,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
                "operator_sequence_ready": True,
            },
            "missing_inputs": missing_inputs,
            "operator_next_actions": operator_next_actions,
            "operator_command_checks": operator_command_checks,
        },
    )
    return path


def _external_settlement_handoff(
    path: Path,
    *,
    ready: bool,
    command_surface_ready: bool = True,
) -> Path:
    missing_inputs = [] if ready else [
        {
            "id": "capture_input_preflight",
            "reason": "operator capture inputs have not passed read-only preflight",
            "required_command": (
                "python3 -m src.integration.external_settlement --root . "
                "--preflight-capture-inputs --transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" "
                "--destination-chain \"$X0T_DESTINATION_CHAIN\" --settlement-id \"$X0T_SETTLEMENT_ID\" "
                "--rpc-url \"$X0T_BASE_RPC_URL\" --require-preflight-ready"
            ),
            "status": "OPERATOR_REQUIRED",
        },
        {
            "id": "retained_settlement_receipt",
            "reason": "retained settlement receipt is missing or invalid",
            "required_artifact": ".tmp/external-settlement-evidence/settlement-submit.json",
            "status": "OPERATOR_REQUIRED",
        },
    ]
    operator_next_actions = [
        {
            "id": "preflight_capture_inputs",
            "status": "OPERATOR_INPUT_REQUIRED" if not ready else "DONE",
            "command": (
                "python3 -m src.integration.external_settlement --root . "
                "--preflight-capture-inputs --transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" "
                "--destination-chain \"$X0T_DESTINATION_CHAIN\" --settlement-id \"$X0T_SETTLEMENT_ID\" "
                "--rpc-url \"$X0T_BASE_RPC_URL\" --require-preflight-ready"
            ),
            "runs_live_rpc": False,
            "writes_evidence": False,
        },
        {
            "id": "capture_real_settlement_receipt",
            "status": "OPERATOR_INPUT_REQUIRED" if not ready else "DONE",
            "description": "Place a real submitted X0T transaction receipt at .tmp/external-settlement-evidence/settlement-submit.json.",
        },
        {
            "id": "verify_live_base_rpc",
            "status": "OPERATOR_INPUT_REQUIRED" if not ready else "DONE",
            "command": (
                "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py "
                "--require-ready --rpc-url \"$X0T_BASE_RPC_URL\""
            ),
        },
    ]
    operator_command_checks = [
        {
            "action_id": "preflight_capture_inputs",
            "command": operator_next_actions[0]["command"],
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "src/integration/external_settlement.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
        {
            "action_id": "verify_live_base_rpc",
            "command": operator_next_actions[2]["command"],
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
    ]
    _write_json(
        path,
        {
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
            "summary": {
                "source_errors_total": 0,
                "capture_preflight_available": True,
                "capture_preflight_decision": "CAPTURE_INPUTS_READY" if ready else "CAPTURE_INPUTS_BLOCKED",
                "capture_inputs_ready": ready,
                "missing_inputs_total": 0 if ready else 5,
                "operator_actions_total": 6,
                "operator_commands_total": 5,
                "operator_command_entrypoints_missing": 0 if command_surface_ready else 1,
                "operator_command_surface_ready": command_surface_ready,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
            },
            "missing_inputs": missing_inputs,
            "operator_next_actions": operator_next_actions,
            "operator_command_checks": operator_command_checks,
        },
    )
    return path


def _rollout_provenance_handoff(path: Path, *, ready: bool, command_surface_ready: bool = True) -> Path:
    operator_next_actions = [] if ready else [
        {
            "id": "render_template_pack",
            "status": "OPERATOR_INPUT_REQUIRED",
            "command": "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force",
        },
        {
            "id": "return_digest_pinned_evidence",
            "status": "OPERATOR_INPUT_REQUIRED",
            "required_path": ".tmp/production-raw-evidence-operator-bundle/live-rollout/image-digests.json",
        },
        {
            "id": "verify_live_rollout_evidence_gate",
            "status": "AFTER_OPERATOR_EVIDENCE",
            "command": "python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready",
        },
        {
            "id": "rerun_rollout_provenance",
            "status": "AFTER_OPERATOR_EVIDENCE",
            "command": (
                "python3 -m src.integration.rollout_provenance --root . "
                "--raw-image-digests .tmp/live-rollout-raw-evidence/image-digests.json "
                "--provenance-gate .tmp/validation-shards/deploy-image-provenance-gate-current.json --require-ready"
            ),
        },
        {
            "id": "rerun_current_evidence_rollup",
            "status": "AFTER_ROLLOUT_READY",
            "command": "python3 -m src.integration.current_evidence_rollup --root . --require-complete",
        },
    ]
    operator_command_checks = [
        {
            "action_id": "render_template_pack",
            "command": operator_next_actions[0]["command"] if operator_next_actions else "",
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
        {
            "action_id": "verify_live_rollout_evidence_gate",
            "command": operator_next_actions[2]["command"] if operator_next_actions else "",
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "scripts/ops/verify_live_rollout_evidence_gate.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
        {
            "action_id": "rerun_rollout_provenance",
            "command": operator_next_actions[3]["command"] if operator_next_actions else "",
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "src/integration/rollout_provenance.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
        {
            "action_id": "rerun_current_evidence_rollup",
            "command": operator_next_actions[4]["command"] if operator_next_actions else "",
            "entrypoint_exists": command_surface_ready,
            "expected_entrypoint": "src/integration/current_evidence_rollup.py",
            "shell_redirection_placeholder": "",
            "shell_redirection_placeholder_detected": False,
            "status": "READY" if command_surface_ready else "MISSING_ENTRYPOINT",
        },
    ]
    _write_json(
        path,
        {
            "schema_version": "x0tta6bl4-live-rollout-image-digests-closure-attempt-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_CLOSE" if ready else "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
            "operator_handoff_decision": "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
            if ready
            else "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR",
            "ready_for_completion_rerun": ready,
            "goal_can_be_marked_complete": False,
            "summary": {
                "can_close_image_digests_blocker": ready,
                "missing_inputs_total": 0 if ready else 1,
                "operator_actions_total": 0 if ready else 5,
                "operator_commands_total": 0 if ready else 4,
                "operator_command_entrypoints_missing": 0 if command_surface_ready else 1,
                "operator_command_surface_ready": command_surface_ready,
                "operator_commands_with_shell_redirection_placeholders": 0,
                "operator_command_shell_surface_ready": True,
            },
            "missing_inputs": [] if ready else [
                {
                    "id": "live_rollout_image_digest_provenance",
                    "status": "OPERATOR_INPUT_REQUIRED",
                    "commands": [item["command"] for item in operator_next_actions if item.get("command")],
                }
            ],
            "operator_next_actions": operator_next_actions,
            "operator_command_checks": [] if ready else operator_command_checks,
        },
    )
    return path


def _next_input(key: str, *, ready: bool, exists: bool = True) -> dict:
    return {
        "evidence_key": key,
        "ready": ready,
        "source_artifact_exists": exists,
        "source_artifact_path": (
            f".tmp/validation-shards/{key}-evidence-gate-current.json"
            if exists
            else ".tmp/external-settlement-evidence/settlement-submit.json"
        ),
        "operator_action": f"provide production evidence for {key}",
        "verification_command": f"verify {key}",
        "collector_command": f"collect {key}",
        "errors": [] if ready else [f"{key} gate blocked"],
        "collector_semantic_blocker_raw_paths": [f".tmp/{key}/operator-manifest.json"] if not ready else [],
    }


def _import_result(key: str, *, ready: bool, exists: bool = True, path: str = "") -> dict:
    artifact_path = path or (
        f".tmp/validation-shards/{key}-evidence-gate-current.json"
        if exists
        else ".tmp/external-settlement-evidence/settlement-submit.json"
    )
    return {
        "evidence_key": key,
        "ready": ready,
        "artifact_exists": exists,
        "artifact_path": artifact_path,
        "supporting_artifact_exists": key == "external_settlement",
        "supporting_artifact_path": ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
        if key == "external_settlement"
        else "",
        "errors": [] if ready else [f"{key} import blocked"],
    }


def _intake_status(key: str, *, ready: bool, file_report_summary: dict | None = None) -> dict:
    return {
        "evidence_key": key,
        "ready": ready,
        "operator_bundle_file_report_summary": file_report_summary or {},
        "missing_or_blocking_reasons": [] if ready else [f"{key} intake blocked"],
    }


def _write_gate_inputs(
    tmp_path: Path,
    *,
    ready: bool,
    missing_external: bool = False,
    mismatch_key: str = "",
) -> tuple[Path, Path, Path]:
    next_path = tmp_path / "next.json"
    import_path = tmp_path / "import.json"
    audit_path = tmp_path / "audit.json"
    next_items = []
    import_items = []
    for key in sorted(REQUIRED_EVIDENCE_KEYS):
        exists = not (missing_external and key == "external_settlement")
        next_items.append(_next_input(key, ready=ready and exists, exists=exists))
        import_items.append(
            _import_result(
                key,
                ready=ready and exists,
                exists=exists,
                path=".tmp/different.json" if key == mismatch_key else "",
            )
        )
    complete = ready and not missing_external and not mismatch_key
    _write_json(next_path, {"status": "VERIFIED HERE", "ok": True, "required_inputs": next_items})
    _write_json(import_path, {"status": "VERIFIED HERE", "ok": True, "source_results": import_items})
    _write_json(
        audit_path,
        {
            "status": "VERIFIED HERE",
            "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
            "goal_can_be_marked_complete": complete,
            "checklist": [
                {
                    "id": "production_evidence_replacement_passport_clear",
                    "evidence": {
                        "raw_install_claim_source": "return_acceptance",
                        "current_raw_files_installed": 5 if complete else 0,
                        "coverage_raw_files_reported_installed": 5,
                        "return_acceptance_raw_files_staged": 5 if complete else 0,
                        "return_acceptance_raw_files_local_observation": 0 if complete else 5,
                    },
                }
            ],
            "summary": {
                "checklist_total": 13,
                "checklist_passed": 13 if complete else 7,
                "checklist_blocking": 0 if complete else 6,
                "local_wiring_passed": True,
                "production_readiness_passed": complete,
                "raw_operator_packet_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS"
                if complete
                else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_operator_packet_readiness_ready_for_collectors": complete,
                "raw_operator_packet_readiness_collectors_ready": 1 if complete else 0,
                "raw_operator_packet_readiness_collectors_blocked": 0 if complete else 1,
                "raw_operator_packet_readiness_collectors_total": 1,
                "raw_operator_packet_readiness_raw_files_ready": 5 if complete else 0,
                "raw_operator_packet_readiness_raw_files_local_observation": 0 if complete else 5,
                "raw_operator_packet_readiness_raw_files_total": 5,
                "x0t_bridge_config_decision": "X0T_BRIDGE_CONFIG_READY"
                if complete
                else "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
                "x0t_bridge_config_ready": complete,
                "x0t_bridge_address_input_ready": complete,
                "x0t_bridge_configured_bridge_ready": complete,
                "x0t_contract_readiness_decision": "CONTRACT_READINESS_CLEAR"
                if complete
                else "BLOCKED_ON_DEPLOYMENT_CONFIG",
                "x0t_contract_readiness_clear": complete,
                "x0t_contract_build_env_ready": True,
                "x0t_contract_build_verification_ready": True,
                "x0t_contract_bridge_source_ready": True,
                "x0t_contract_operator_configs_ready": complete,
                "x0t_contract_missing_inputs_total": 0 if complete else 1,
                "x0t_contract_deployment_ready": complete,
            },
        },
    )
    _write_cross_plane_proof_gate(tmp_path, allowed=complete)
    return next_path, import_path, audit_path


def test_gap_index_prioritizes_missing_external_settlement_artifact(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False, missing_external=True)
    rollout_path = _rollout_provenance_handoff(tmp_path / "rollout.json", ready=False)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        rollout_provenance_path=rollout_path,
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["missing_source_artifacts"] == 1
    assert report["summary"]["blocked_source_artifacts"] == len(REQUIRED_EVIDENCE_KEYS) - 1
    assert report["summary"]["completion_checklist_total"] == 13
    assert report["summary"]["completion_checklist_passed"] == 7
    assert report["summary"]["completion_checklist_blocking"] == 6
    assert report["summary"]["completion_checklist_remaining"] == 6
    assert report["summary"]["completion_local_wiring_passed"] is True
    assert report["summary"]["completion_production_readiness_passed"] is False
    assert report["summary"]["raw_install_claim_source"] == "return_acceptance"
    assert report["summary"]["current_raw_files_installed"] == 0
    assert report["summary"]["coverage_raw_files_reported_installed"] == 5
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 5
    assert report["summary"]["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 0
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 1
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 5
    assert report["summary"]["raw_operator_packet_readiness_raw_files_total"] == 5
    assert report["summary"]["x0t_contract_readiness_decision"] == "BLOCKED_ON_DEPLOYMENT_CONFIG"
    assert report["summary"]["x0t_contract_deployment_ready"] is False
    assert report["summary"]["x0t_contract_operator_handoff_available"] is True
    assert report["summary"]["x0t_contract_operator_handoff_decision"] == (
        "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["x0t_contract_operator_actions_total"] == 6
    assert report["summary"]["x0t_contract_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_contract_operator_command_surface_ready"] is True
    contract_handoff = report["x0t_contract_operator_handoff"]
    assert contract_handoff["approval_env"] == "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
    assert contract_handoff["approval_value_required"] == "apply-bridge-address-base-sepolia"
    assert contract_handoff["missing_inputs"][0]["id"] == "operator_contract_addresses"
    contract_action_ids = {item["id"] for item in contract_handoff["operator_next_actions"]}
    assert "validate_bridge_address" in contract_action_ids
    assert "apply_bridge_address_with_operator_approval" in contract_action_ids
    assert "rerun_contract_readiness" in contract_action_ids
    contract_command_ids = {item["action_id"] for item in contract_handoff["operator_command_checks"]}
    assert "validate_bridge_address" in contract_command_ids
    assert "apply_bridge_address_with_operator_approval" in contract_command_ids
    assert report["summary"]["live_rollout_handoff_available"] is True
    assert report["summary"]["live_rollout_handoff_clear"] is True
    assert report["summary"]["live_rollout_handoff_decision"] == (
        "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    )
    assert report["summary"]["live_rollout_handoff_missing_inputs_total"] == 1
    assert report["summary"]["live_rollout_handoff_operator_actions_total"] == 5
    assert report["summary"]["live_rollout_handoff_operator_commands_total"] == 4
    assert report["summary"]["live_rollout_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["live_rollout_handoff_operator_command_surface_ready"] is True
    rollout_handoff = report["live_rollout_operator_handoff"]
    assert rollout_handoff["available"] is True
    assert rollout_handoff["decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert rollout_handoff["missing_inputs"][0]["id"] == "live_rollout_image_digest_provenance"
    rollout_action_ids = {item["id"] for item in rollout_handoff["operator_next_actions"]}
    assert "render_template_pack" in rollout_action_ids
    assert "return_digest_pinned_evidence" in rollout_action_ids
    assert "rerun_rollout_provenance" in rollout_action_ids
    rollout_command_ids = {item["action_id"] for item in rollout_handoff["operator_command_checks"]}
    assert "verify_live_rollout_evidence_gate" in rollout_command_ids
    assert "rerun_current_evidence_rollup" in rollout_command_ids
    assert "X0T contract deployment config is not ready" in report["blocking_reasons"]
    assert "Live rollout image digest/provenance handoff is not ready for completion rerun" in report["blocking_reasons"]
    assert report["operator_priority_order"][0] == "external_settlement"
    external = report["evidence_gaps"][0]
    assert external["blocker_class"] == "MISSING_SOURCE_ARTIFACT"
    assert external["supporting_artifact_exists"] is True


def test_gap_index_detects_input_import_path_mismatch(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True, mismatch_key="paid_client_path")

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, root=tmp_path).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["import_mismatches"] == 1
    assert report["operator_priority_order"] == ["paid_client_path"]
    gap = report["evidence_gaps"][0]
    assert gap["blocker_class"] == "IMPORT_MISMATCH"
    assert gap["consistency_errors"]


def test_gap_index_preserves_intake_operator_bundle_identity_mismatch_counts(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False)
    intake_path = tmp_path / "intake.json"
    file_report_summary = {
        "files_total": 2,
        "files_available": 2,
        "manifest_identity_mismatches_total": 2,
        "collector_id_mismatches": 1,
        "raw_id_mismatches": 1,
        "file_name_mismatches": 0,
    }
    _write_json(
        intake_path,
        {
            "status": "VERIFIED HERE",
            "decision": "BLOCKED_OPERATOR_EVIDENCE_REQUIRED",
            "evidence_key_statuses": [
                _intake_status("live_spire_mtls", ready=False, file_report_summary=file_report_summary),
                *[
                    _intake_status(key, ready=False)
                    for key in sorted(REQUIRED_EVIDENCE_KEYS - {"live_spire_mtls"})
                ],
            ],
        },
    )

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, intake_path).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["production_intake_available"] is True
    assert report["summary"]["bundle_manifest_identity_mismatches_total"] == 2
    assert report["summary"]["bundle_collector_id_mismatches"] == 1
    assert report["summary"]["bundle_raw_id_mismatches"] == 1
    gap = next(item for item in report["evidence_gaps"] if item["evidence_key"] == "live_spire_mtls")
    assert gap["operator_bundle_file_report_summary"] == file_report_summary
    assert gap["intake_blocking_reasons"] == ["live_spire_mtls intake blocked"]


def test_gap_index_accepts_all_ready_sources_and_complete_audit(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, root=tmp_path).report()

    assert report["decision"] == "NO_PRODUCTION_EVIDENCE_GAPS"
    assert report["local_gap_index_clear"] is True
    assert report["goal_can_be_marked_complete"] is True
    assert report["summary"]["local_gap_index_clear"] is True
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is True
    assert report["summary"]["cross_plane_proof_gate_source_artifact_hashes_present"] is True
    assert report["current_evidence_context"]["included"] is True
    assert report["current_evidence_context"]["current_gap_count"] == 0
    assert report["current_evidence_context_hash"].startswith("0x")
    assert report["cross_plane_proof_gate"]["allowed"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_required"] is True
    assert report["cross_plane_claim_gate"]["cross_plane_proof_gate_allowed"] is True
    assert report["cross_plane_claim_gate"]["proof_claims"]["production_ready"] is False
    assert report["cross_plane_claim_gate"]["proof_claims"]["live_apply_authorized"] is False
    assert report["summary"]["ready_evidence_keys"] == len(REQUIRED_EVIDENCE_KEYS)
    assert report["summary"]["completion_checklist_passed"] == 13
    assert report["summary"]["completion_checklist_remaining"] == 0
    assert report["summary"]["completion_production_readiness_passed"] is True
    assert report["summary"]["current_raw_files_installed"] == 5
    assert report["summary"]["return_acceptance_raw_files_staged"] == 5
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is True
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 5
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 0
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 0
    assert report["summary"]["x0t_contract_readiness_decision"] == "CONTRACT_READINESS_CLEAR"
    assert report["summary"]["x0t_contract_deployment_ready"] is True
    assert report["operator_priority_order"] == []
    assert report["blocking_reasons"] == []


def test_gap_index_blocks_complete_without_current_evidence_context(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, root=tmp_path).report()

    assert report["decision"] == "PRODUCTION_GAP_INDEX_BLOCKED_BY_CURRENT_EVIDENCE"
    assert report["local_gap_index_clear"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["completion_blocked_by_current_evidence"] is True
    assert report["summary"]["completion_blocked_by_cross_plane_proof_gate"] is False
    assert report["summary"]["current_evidence_context_included"] is False
    assert report["summary"]["current_evidence_context_clear"] is False
    assert report["current_evidence_context"]["status"] == "missing_current_evidence_context"
    assert "current_evidence_context_missing" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert "current cross-plane evidence context is not clear" in report["blocking_reasons"]


def test_gap_index_blocks_complete_on_current_evidence_open_gap(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    _write_current_evidence_context(
        tmp_path,
        current_gaps=[{"id": "external-dpi-proof-missing", "blocks_real_readiness": True}],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, root=tmp_path).report()

    assert report["decision"] == "PRODUCTION_GAP_INDEX_BLOCKED_BY_CURRENT_EVIDENCE"
    assert report["local_gap_index_clear"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["current_evidence_open_gaps"] == 1
    assert report["summary"]["current_evidence_next_actions"] == 1
    assert report["current_evidence_context"]["open_gap_ids"] == ["external-dpi-proof-missing"]
    assert report["current_evidence_context"]["next_action_ids"] == ["external-dpi-real-artifact-intake"]
    assert "current_evidence_open_gaps" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "current_evidence_next_actions_open" in report["cross_plane_claim_gate"]["blocked_reason_ids"]


def test_gap_index_blocks_complete_when_cross_plane_proof_gate_blocks(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    _write_current_evidence_context(tmp_path)
    _write_cross_plane_proof_gate(tmp_path, allowed=False)

    report = ProductionGapIndexGate.load(next_path, import_path, audit_path, root=tmp_path).report()

    assert report["decision"] == "PRODUCTION_GAP_INDEX_BLOCKED_BY_CROSS_PLANE_PROOF_GATE"
    assert report["local_gap_index_clear"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["current_evidence_context_clear"] is True
    assert report["summary"]["cross_plane_proof_gate_allowed"] is False
    assert report["summary"]["completion_blocked_by_cross_plane_proof_gate"] is True
    assert report["cross_plane_claim_gate"]["goal_completion_claim_allowed"] is False
    assert "cross_plane_proof_gate_blocked" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "claim_blocked:dpi_bypass" in report["cross_plane_claim_gate"]["blocked_reason_ids"]
    assert "reusable cross-plane proof gate has not allowed production gap closure" in report["blocking_reasons"]
    assert "reusable cross-plane proof gate must allow production gap closure claims" in report["not_verified_yet"]


def test_gap_index_blocks_configured_governance_until_proposal_executed(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    governance_path = _governance_execute_readiness(tmp_path / "governance.json", executed=False)
    handoff_path = _governance_execute_handoff(tmp_path / "handoff.json")

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        governance_execute_readiness_path=governance_path,
        governance_execute_handoff_path=handoff_path,
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["ready_evidence_keys"] == len(REQUIRED_EVIDENCE_KEYS)
    assert report["summary"]["x0t_governance_execute_decision"] == "READY_TO_EXECUTE"
    assert report["summary"]["x0t_governance_execute_ready_now"] is True
    assert report["summary"]["x0t_governance_execute_handoff_available"] is True
    assert report["summary"]["x0t_governance_execute_handoff_clear"] is True
    assert report["summary"]["x0t_governance_execute_handoff_actionable"] is True
    assert report["summary"]["x0t_governance_execute_handoff_operator_commands_total"] == 5
    assert report["summary"]["x0t_governance_execute_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["x0t_governance_execute_handoff_operator_command_surface_ready"] is True
    assert (
        report["summary"]["x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders"]
        == 0
    )
    assert report["summary"]["x0t_governance_execute_handoff_operator_command_shell_surface_ready"] is True
    assert report["summary"]["x0t_governance_execute_handoff_operator_sequence_ready"] is True
    handoff = report["x0t_governance_operator_handoff"]
    assert handoff["available"] is True
    assert handoff["decision"] == "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL"
    assert handoff["actionable"] is True
    assert handoff["ready_for_operator_execute"] is True
    assert handoff["operator_next_actions"][2]["id"] == "execute_with_operator_approval"
    assert handoff["operator_command_checks"][2]["expected_entrypoint"] == "execute_dao_proposal.py"
    assert report["summary"]["x0t_governance_ready_for_operator_execute"] is True
    assert report["summary"]["x0t_governance_proposal_executed"] is False
    assert "X0T governance proposal is not executed" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("x0t_governance:")
    assert "handoff" in report["required_next_evidence"][0]


def test_gap_index_requires_configured_governance_handoff(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    governance_path = _governance_execute_readiness(tmp_path / "governance.json", executed=True)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        governance_execute_readiness_path=governance_path,
        governance_execute_handoff_path=tmp_path / "missing-handoff.json",
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["x0t_governance_execute_handoff_available"] is False
    assert report["summary"]["x0t_governance_execute_handoff_clear"] is False
    assert "X0T governance execute operator handoff artifact is missing or unreadable" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("x0t_governance_handoff:")


def test_gap_index_surfaces_configured_external_settlement_handoff(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False, missing_external=True)
    external_handoff_path = _external_settlement_handoff(tmp_path / "external-handoff.json", ready=False)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        external_settlement_handoff_path=external_handoff_path,
        external_settlement_handoff_display=str(external_handoff_path),
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["external_settlement_handoff_available"] is True
    assert report["summary"]["external_settlement_handoff_clear"] is True
    assert report["summary"]["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert report["summary"]["external_settlement_capture_preflight_decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert report["summary"]["external_settlement_capture_inputs_ready"] is False
    assert report["summary"]["external_settlement_handoff_missing_inputs_total"] == 5
    assert report["summary"]["external_settlement_handoff_operator_command_entrypoints_missing"] == 0
    assert (
        report["summary"]["external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    )
    assert report["summary"]["external_settlement_handoff_operator_command_shell_surface_ready"] is True
    handoff = report["external_settlement_operator_handoff"]
    assert handoff["available"] is True
    assert handoff["decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert handoff["missing_inputs"][0]["id"] == "capture_input_preflight"
    assert handoff["operator_next_actions"][0]["id"] == "preflight_capture_inputs"
    assert handoff["operator_command_checks"][0]["expected_entrypoint"] == "src/integration/external_settlement.py"
    assert str(external_handoff_path) in report["source_artifacts"]


def test_gap_index_requires_configured_external_settlement_handoff(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False, missing_external=True)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        external_settlement_handoff_path=tmp_path / "missing-external-handoff.json",
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["external_settlement_handoff_available"] is False
    assert report["summary"]["external_settlement_handoff_clear"] is False
    assert "External X0T settlement operator handoff artifact is missing or unreadable" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("external_settlement_handoff:")


def test_gap_index_surfaces_configured_live_rollout_handoff(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False)
    rollout_path = _rollout_provenance_handoff(tmp_path / "rollout.json", ready=False)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        rollout_provenance_path=rollout_path,
        rollout_provenance_display=str(rollout_path),
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["live_rollout_handoff_available"] is True
    assert report["summary"]["live_rollout_handoff_clear"] is True
    assert report["summary"]["live_rollout_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert report["summary"]["live_rollout_ready_for_completion_rerun"] is False
    assert report["summary"]["live_rollout_can_close_image_digests_blocker"] is False
    assert report["summary"]["live_rollout_handoff_missing_inputs_total"] == 1
    assert report["summary"]["live_rollout_handoff_operator_actions_total"] == 5
    assert report["summary"]["live_rollout_handoff_operator_commands_total"] == 4
    assert report["summary"]["live_rollout_handoff_operator_command_entrypoints_missing"] == 0
    assert report["summary"]["live_rollout_handoff_operator_command_surface_ready"] is True
    handoff = report["live_rollout_operator_handoff"]
    assert handoff["available"] is True
    assert handoff["decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    assert handoff["rollout_decision"] == "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"
    assert handoff["ready_for_completion_rerun"] is False
    assert handoff["missing_inputs"][0]["id"] == "live_rollout_image_digest_provenance"
    assert handoff["operator_next_actions"][0]["id"] == "render_template_pack"
    assert handoff["operator_command_checks"][0]["expected_entrypoint"] == (
        "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py"
    )
    assert str(rollout_path) in report["source_artifacts"]
    assert "Live rollout image digest/provenance handoff is not ready for completion rerun" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("live_rollout_handoff:")


def test_gap_index_requires_configured_live_rollout_handoff(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        rollout_provenance_path=tmp_path / "missing-rollout.json",
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["live_rollout_handoff_available"] is False
    assert report["summary"]["live_rollout_handoff_clear"] is False
    assert "Live rollout image digest/provenance handoff artifact is missing or unreadable" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("live_rollout_handoff:")


def test_gap_index_blocks_when_external_handoff_is_stale_after_sources_clear(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=True)
    external_handoff_path = _external_settlement_handoff(tmp_path / "external-handoff.json", ready=False)

    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        external_settlement_handoff_path=external_handoff_path,
    ).report()

    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["source_artifacts_clear"] is True
    assert report["summary"]["external_settlement_handoff_clear"] is True
    assert report["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert "External X0T settlement operator handoff is not ready for completion rerun" in report["blocking_reasons"]
    assert report["required_next_evidence"][0].startswith("external_settlement_handoff:")


def test_gap_index_markdown_renders_operator_handoff_fields(tmp_path):
    next_path, import_path, audit_path = _write_gate_inputs(tmp_path, ready=False, missing_external=True)
    governance_path = _governance_execute_readiness(tmp_path / "governance.json", executed=False)
    handoff_path = _governance_execute_handoff(tmp_path / "handoff.json")
    external_handoff_path = _external_settlement_handoff(tmp_path / "external-handoff.json", ready=False)
    rollout_path = _rollout_provenance_handoff(tmp_path / "rollout.json", ready=False)
    report = ProductionGapIndexGate.load(
        next_path,
        import_path,
        audit_path,
        governance_execute_readiness_path=governance_path,
        governance_execute_handoff_path=handoff_path,
        external_settlement_handoff_path=external_handoff_path,
        rollout_provenance_path=rollout_path,
    ).report()

    markdown = render_markdown(report)

    assert "# Integration Spine Production Gap Index" in markdown
    assert "pending evidence keys: `10`" in markdown
    assert "`external_settlement` - `MISSING_SOURCE_ARTIFACT`" in markdown
    assert "verify: `verify external_settlement`" in markdown
    assert "collector: `collect billing-provisioning`" in markdown
    assert "verify: `verify billing-provisioning`" in markdown
    assert "raw files to replace:" in markdown
    assert "`.tmp/billing-provisioning/operator-manifest.json`" in markdown
    assert "first blocker: billing-provisioning gate blocked" in markdown
    assert "raw readiness decision: `BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE`" in markdown
    assert "X0T contract operator handoff: `X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR`" in markdown
    assert "## X0T Contract Deployment Operator Handoff" in markdown
    assert "`operator_contract_addresses` - `OPERATOR_INPUT_REQUIRED`" in markdown
    assert "apply_x0t_bridge_contract_address.py --bridge-address" in markdown
    assert "`apply_bridge_address_with_operator_approval` - `OPERATOR_APPROVAL_REQUIRED`" in markdown
    assert "requires operator approval: `True`" in markdown
    assert "submits transaction: `False`" in markdown
    assert "entrypoint: `scripts/ops/apply_x0t_bridge_contract_address.py` exists=`True`" in markdown
    assert "governance execute decision: `READY_TO_EXECUTE`" in markdown
    assert "## X0T Governance Execute Operator Handoff" in markdown
    assert "`execute_with_operator_approval` - `AFTER_READY_STATE`" in markdown
    assert "requires operator approval: `True`" in markdown
    assert "submits transaction: `True`" in markdown
    assert "entrypoint: `execute_dao_proposal.py` exists=`True`" in markdown
    assert "`rerun_completion_and_gap` - `AFTER_EXECUTE`" in markdown
    assert "external settlement handoff: `X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR`" in markdown
    assert "external settlement capture preflight: `CAPTURE_INPUTS_BLOCKED`" in markdown
    assert "## External Settlement Operator Handoff" in markdown
    assert "`capture_input_preflight` - `OPERATOR_REQUIRED`" in markdown
    assert "python3 -m src.integration.external_settlement --root . --preflight-capture-inputs" in markdown
    assert "`retained_settlement_receipt` - `OPERATOR_REQUIRED`" in markdown
    assert "`preflight_capture_inputs` - `OPERATOR_INPUT_REQUIRED`" in markdown
    assert "`verify_live_base_rpc` - `OPERATOR_INPUT_REQUIRED`" in markdown
    assert "### Command Surface" in markdown
    assert "entrypoint: `src/integration/external_settlement.py` exists=`True`" in markdown
    assert "live rollout handoff: `LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR`" in markdown
    assert "## Live Rollout Image Digest Operator Handoff" in markdown
    assert "`live_rollout_image_digest_provenance` - `OPERATOR_INPUT_REQUIRED`" in markdown
    assert "scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force" in markdown
    assert "`render_template_pack` - `OPERATOR_INPUT_REQUIRED`" in markdown
    assert "`verify_live_rollout_evidence_gate` - `AFTER_OPERATOR_EVIDENCE`" in markdown
    assert "entrypoint: `scripts/ops/verify_live_rollout_evidence_gate.py` exists=`True`" in markdown
    assert "X0T governance proposal is not executed" in markdown


def test_gap_index_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--output-md",
            "docs/verification/integration-spine-production-gap-index.md",
            "--require-clear",
        ]
    )

    assert exit_code == 2
    report = json.loads(
        (tmp_path / ".tmp/validation-shards/integration-spine-production-gap-index-current.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["decision"] == "BLOCKED_ON_OPERATOR_EVIDENCE"
    assert report["summary"]["pending_evidence_keys"] == len(REQUIRED_EVIDENCE_KEYS)
    assert report["summary"]["completion_checklist_passed"] == 0
    assert report["summary"]["completion_checklist_remaining"] == 0
    markdown = tmp_path / "docs/verification/integration-spine-production-gap-index.md"
    assert markdown.exists()
    assert "Goal can be marked complete: `False`" in markdown.read_text(encoding="utf-8")


def test_gap_index_cli_refuses_to_overwrite_current_evidence_sources(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--root",
                str(tmp_path),
                "--output-json",
                "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
            ]
        )

    assert "must not overwrite current evidence source artifact" in str(exc.value)
