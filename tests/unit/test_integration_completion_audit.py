import json
from pathlib import Path

from src.integration.completion_audit import (
    RAW_PRODUCTION_EVIDENCE_KEYS,
    REQUIRED_EVIDENCE_KEYS,
    build_audit,
    main,
)


COLLECTOR_BY_EVIDENCE_KEY = {
    "billing-provisioning": "billing-provisioning",
    "ebpf-observability": "ebpf-observability",
    "live_spire_mtls": "zero-trust-pqc",
    "multi_host_mesh": "self-healing-pqc-mesh",
    "paid_client_path": "paid-client-serviceability",
    "safe_rollout_rollback": "live-rollout",
    "signed-release-provenance": "signed-release-provenance",
    "sla-telemetry": "sla-telemetry",
    "stable-deploy": "stable-deploy",
}


def _collector_script_name(evidence_key: str) -> str:
    return COLLECTOR_BY_EVIDENCE_KEY[evidence_key].replace("-", "_")


def _operator_bundle_path(evidence_key: str) -> str:
    collector_id = COLLECTOR_BY_EVIDENCE_KEY[evidence_key]
    return f".tmp/production-raw-evidence-operator-bundle/{collector_id}/operator-manifest.json"


def _raw_packet_identity_plan(evidence_key: str) -> list[dict]:
    collector_id = COLLECTOR_BY_EVIDENCE_KEY[evidence_key]
    path = _operator_bundle_path(evidence_key)
    return [
        {
            "path": path,
            "available": True,
            "suggested_fields": {
                "collector_id": collector_id,
                "raw_id": f"{collector_id}/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "current_fields": {
                "collector_id": None,
                "raw_id": f"{collector_id}/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "identity_mismatch_fields": ["collector_id"],
            "json_merge_patch": {
                "collector_id": collector_id,
                "raw_id": f"{collector_id}/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "json_patch_operations": [{"op": "add", "path": "/collector_id", "value": collector_id}],
        }
    ]


def _operator_packet_index_external_summary() -> dict:
    return {
        "evidence_key": "external_settlement",
        "packet_kind": "external_settlement",
        "commands_missing_entrypoints": 0,
        "required_operator_inputs": [
            "real submitted X0T transaction hash",
            "destination Base chain",
            "settlement_id tied to the integration-spine reward/settlement loop",
            "read-only RPC URL for the same Base chain",
            "retained source commands and explorer URL proving the receipt",
        ],
        "required_fields": [
            "transaction_hash is a 0x-prefixed 32-byte hash",
            "destination_chain is base-sepolia/base_sepolia or base-mainnet/base",
            "settlement_id is specific and non-placeholder",
            "source_commands contains exact retained commands",
            "explorer_url is HTTPS and matches destination_chain",
            "packet_hash is a 64-character lowercase hex digest",
        ],
        "commands": [
            {"command": "python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py --write-template-files --force", "existing_entrypoint": True},
            {"command": "export X0T_BASE_RPC_URL='<read-only Base RPC URL for the matching chain>'", "existing_entrypoint": True, "requires_operator_input": True},
            {"command": "export X0T_SETTLEMENT_TX_HASH='<0x-prefixed submitted settlement transaction hash>'", "existing_entrypoint": True, "requires_operator_input": True},
            {"command": "export X0T_DESTINATION_CHAIN='<base-sepolia|base|base-mainnet>'", "existing_entrypoint": True, "requires_operator_input": True},
            {"command": "export X0T_SETTLEMENT_ID='<non-placeholder settlement id>'", "existing_entrypoint": True, "requires_operator_input": True},
            {"command": "python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --require-preflight-ready", "existing_entrypoint": True},
            {"command": "python3 -m src.integration.external_settlement --root . --capture-from-rpc --write-evidence --require-ready", "existing_entrypoint": True},
            {"command": "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready", "existing_entrypoint": True},
            {"command": "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready", "existing_entrypoint": True},
            {"command": "python3 -m src.integration.production_evidence_replacement_passport --root . --require-valid --require-ready", "existing_entrypoint": True},
            {"command": "python3 -m src.integration.production_input_return_acceptance --root . --require-ready", "existing_entrypoint": True},
            {"command": "python3 -m src.integration.production_input_pipeline --root . --require-ready", "existing_entrypoint": True},
            {"command": "python3 -m src.integration.production_closeout_review --root . --require-ready", "existing_entrypoint": True},
        ],
        "fail_closed_rules": [
            "Do not treat external settlement scaffold templates as production evidence."
        ],
    }


def _operator_packet_index_raw_summary(evidence_key: str) -> dict:
    commands = [
        {"command": "python3 scripts/ops/generate_production_raw_evidence_template_pack.py --write-template-files --force", "existing_entrypoint": True},
        {"command": "write real production JSON files to the required operator bundle paths", "existing_entrypoint": True, "requires_operator_input": True},
        {"command": f"python3 -m src.integration.operator_bundle_identity --root . --evidence-key {evidence_key} --require-clean", "existing_entrypoint": True},
        {"command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json", "existing_entrypoint": True},
        {"command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json --apply", "existing_entrypoint": True},
        {"command": f"python3 scripts/ops/collect_{_collector_script_name(evidence_key)}_evidence_bundle.py --require-ready", "existing_entrypoint": True},
        {"command": f"python3 scripts/ops/verify_{_collector_script_name(evidence_key)}_evidence_gate.py --require-ready", "existing_entrypoint": True},
        {"command": "python3 -m src.integration.production_evidence_replacement_passport --root . --require-valid --require-ready", "existing_entrypoint": True},
        {"command": "python3 -m src.integration.production_input_return_acceptance --root . --require-ready", "existing_entrypoint": True},
        {"command": "python3 -m src.integration.production_input_pipeline --root . --require-ready", "existing_entrypoint": True},
        {"command": "python3 -m src.integration.production_closeout_review --root . --require-ready", "existing_entrypoint": True},
    ]
    if evidence_key == "safe_rollout_rollback":
        commands.insert(
            7,
            {"command": "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force", "existing_entrypoint": True},
        )
    required_operator_inputs = [
        "production environment identifier",
        "operator or CI identity that collected the evidence",
        "exact source_commands for every JSON file",
        "domain-specific production observations required by the collector",
    ]
    if evidence_key == "safe_rollout_rollback":
        required_operator_inputs.extend(
            [
                "digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image",
                "retained per-image cosign/SLSA provenance artifacts for current deployed image digests",
            ]
        )
    fail_closed_rules = [
        "Do not treat production raw evidence template pack files as production evidence."
    ]
    if evidence_key == "safe_rollout_rollback":
        fail_closed_rules.append(
            "Do not treat live rollout image provenance scaffold templates as production evidence."
        )
    return {
        "evidence_key": evidence_key,
        "packet_kind": "raw_production_bundle",
        "commands_missing_entrypoints": 0,
        "required_operator_inputs": required_operator_inputs,
        "required_fields": [
            "status or evidence_status == VERIFIED HERE",
            "collector_id matches the intake manifest collector_id",
            "raw_id matches the intake manifest raw_id",
            "file_name matches the intake manifest file_name",
            "collected_at is a UTC timestamp",
            "collected_by is a specific operator or CI identity",
            "source_commands is a non-empty list of exact commands",
            "production_ready == true",
            "production_promotion_blockers is absent or empty",
            "claim_boundary/environment does not describe local context",
            "template/mock/placeholder markers are absent",
        ],
        "commands": commands,
        "fail_closed_rules": fail_closed_rules,
        "identity_updates_total": 1,
        "identity_update_plan": _raw_packet_identity_plan(evidence_key),
    }


def _operator_packet_index_payload() -> dict:
    packet_summaries = [
        _operator_packet_index_external_summary(),
        *[
            _operator_packet_index_raw_summary(key)
            for key in sorted(RAW_PRODUCTION_EVIDENCE_KEYS)
        ],
    ]
    return {
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "ALL_OPERATOR_PACKETS_ACTIONABLE",
        "all_packets_actionable": True,
        "summary": {
            "packets_total": len(REQUIRED_EVIDENCE_KEYS),
            "actionable_packets": len(REQUIRED_EVIDENCE_KEYS),
            "packets_with_missing_entrypoints": 0,
            "commands_missing_entrypoints_total": 0,
            "all_packets_actionable": True,
        },
        "packet_summaries": packet_summaries,
    }


def _write_json(root: Path, rel: str, payload: dict):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(root: Path, rel: str, text: str):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_governance_execute_readiness(root: Path, *, executed: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-readiness-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALREADY_EXECUTED" if executed else "NOT_READY_TIMELOCK_ACTIVE",
            "proposal_id": 1,
            "proposal_state": {
                "state_code": 6 if executed else 4,
                "state_label": "Executed" if executed else "Queued",
                "queued": not executed,
                "executed": executed,
                "vetoed": False,
            },
            "timelock": {
                "earliest_execution_time_utc": "2026-05-21T04:45:22Z",
                "seconds_until_earliest_execution_by_block_time": 0 if executed else 23210,
            },
            "summary": {
                "execute_ready_now": False,
                "proposal_queued": not executed,
                "proposal_executed": executed,
                "proposal_vetoed": False,
                "next_executable_after_utc": "2026-05-21T04:45:22Z",
                "safe_to_retry_readiness_check": not executed,
            },
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "submits_transaction": False,
            "runs_live_rpc": True,
            "not_verified_yet": [] if executed else [
                "execute(1) with explicit operator approval after proposal state becomes Ready",
                "execution transaction receipt and final Executed proposal state",
            ],
        },
    )


def _write_governance_execute_handoff(root: Path, *, executed: bool) -> None:
    readiness_decision = "ALREADY_EXECUTED" if executed else "NOT_READY_TIMELOCK_ACTIVE"
    _write_json(
        root,
        ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-governance-execute-operator-handoff-v2-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "handoff_decision": "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
            if executed
            else "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
            "handoff_actionable": True,
            "ready_for_operator_execute": False,
            "already_executed": executed,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "approval_boundary": {
                "approval_env": "X0T_EXECUTE_PROPOSAL_APPROVAL",
                "expected_value": "execute-proposal-1-base-sepolia",
                "private_key_required": True,
                "can_submit_without_operator_approval": False,
            },
            "summary": {
                "readiness_decision": readiness_decision,
                "execute_ready_now": False,
                "proposal_id": 1,
                "state_label": "Executed" if executed else "Queued",
                "proposal_executed": executed,
                "approval_env": "X0T_EXECUTE_PROPOSAL_APPROVAL",
                "approval_value_required": "execute-proposal-1-base-sepolia",
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


def _write_x0t_bridge_config(root: Path, *, ready: bool) -> None:
    bridge_address = "0x1111111111111111111111111111111111111111" if ready else ""
    configured_address = bridge_address or "0x0000000000000000000000000000000000000000"
    missing_inputs = [] if ready else [
        {
            "id": "bridge_contract_address",
            "environment": "X0T_BRIDGE_CONTRACT_ADDRESS",
            "status": "OPERATOR_REQUIRED",
            "reason": "bridge contract address is required and must not be zero or placeholder",
        }
    ]
    _write_json(
        root,
        ".tmp/validation-shards/x0t-bridge-config-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-bridge-config-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "X0T_BRIDGE_CONFIG_READY" if ready else "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
            "bridge_config_ready": ready,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "mutates_config": ready,
            "input": {
                "bridge_address": bridge_address,
                "ready": ready,
                "errors": [] if ready else ["bridge contract address is required and must not be zero or placeholder"],
            },
            "config": {
                "path": "charts/x0tta-mesh-operator/examples/meshcluster-production.yaml",
                "chain_id": 84532,
                "configured_bridge_address": configured_address,
                "configured_ready": ready,
                "config_matches_input": ready,
            },
            "write": {
                "approval_env": "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL",
                "approval_value_required": "apply-bridge-address-base-sepolia",
                "approval_ready": ready,
                "requested": ready,
                "performed": ready,
                "error": "",
            },
            "missing_inputs": missing_inputs,
            "summary": {
                "bridge_address_input_ready": ready,
                "configured_bridge_ready": ready,
                "bridge_config_ready": ready,
                "config_matches_input": ready,
                "approval_ready": ready,
                "write_requested": ready,
                "write_performed": ready,
                "missing_inputs_total": len(missing_inputs),
            },
        },
    )


def _write_x0t_contract_build_verification(root: Path) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/x0t-contract-build-verification-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-contract-build-verification-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "X0T_CONTRACT_BUILD_VERIFIED",
            "contract_build_verified": True,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "mutates_local_build_artifacts": True,
            "summary": {
                "required_node_runtime_ready": True,
                "hardhat_compile_ready": True,
                "hardhat_test_ready": True,
                "commands_total": 3,
                "commands_failed": 0,
                "preflight_errors_total": 0,
            },
        },
    )


def _write_x0t_contract_readiness(root: Path, *, ready: bool) -> None:
    missing_inputs = [] if ready else [
        {
            "id": "operator_contract_addresses",
            "status": "OPERATOR_INPUT_REQUIRED",
            "reason": "operator bridge config still needs its own deployed bridge contract address; do not substitute X0TToken or MeshGovernance",
            "paths": ["charts/x0tta-mesh-operator/examples/meshcluster-production.yaml"],
            "commands": [
                'export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"',
                'python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready',
                'X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready',
                "python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md",
            ],
        }
    ]
    _write_json(
        root,
        ".tmp/validation-shards/x0t-contract-readiness-current.json",
        {
            "schema_version": "x0tta6bl4-x0t-contract-readiness-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "CONTRACT_READINESS_CLEAR" if ready else "BLOCKED_ON_DEPLOYMENT_CONFIG",
            "contract_readiness_clear": ready,
            "goal_can_be_marked_complete": False,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "missing_inputs": missing_inputs,
            "summary": {
                "build_env_ready": True,
                "contract_build_verification_ready": True,
                "contract_dependencies_ready": True,
                "effective_node_runtime_ready": True,
                "base_sepolia_manifest_ready": True,
                "legacy_contract_surface_ready": True,
                "bridge_contract_source_ready": True,
                "deployment_config_ready": ready,
                "operator_configs_ready": ready,
                "contract_readiness_clear": ready,
                "missing_inputs_total": len(missing_inputs),
            },
        },
    )


def _base_root(tmp_path: Path) -> Path:
    root = tmp_path
    _write_text(root, "src/integration/spine.py", "class SpineIdentity: pass\nEventBus\nPOLICY_DENIED\nACTUATOR_SIMULATED\nreward_relay\n")
    _write_text(root, "src/integration/code_wiring.py", "def build_report(root): pass\n")
    _write_text(root, "src/dao/token_bridge.py", "BridgeDeposit BridgeRelease TokenBridge\n")
    _write_text(root, "src/integration/current_evidence_rollup.py", "def build_rollup(): pass\n")
    _write_text(root, "src/integration/semantic_production_blocker_queue.py", "def build_queue(): pass\n")
    _write_text(root, "src/integration/raw_evidence_inventory.py", "def build_inventory(): pass\n")
    _write_text(root, "src/integration/rollout_provenance.py", "def build_gate(): pass\n")
    _write_text(root, "src/integration/evidence_source_candidates.py", "def build_audit(): pass\n")
    _write_text(root, "src/integration/external_settlement.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/operator_bundle_gate.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/operator_bundle_identity.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/operator_evidence_packet.py", "def build_packet(): pass\n")
    _write_text(root, "src/integration/production_evidence_replacement_passport.py", "def build_passport(): pass\n")
    _write_text(root, "src/integration/required_evidence_consistency.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/rollup_approval_contract.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/production_input_return_acceptance.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/production_input_pipeline.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/production_closeout_review.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/x0t_governance_execute_readiness.py", "def build_readiness_report(): pass\n")
    _write_text(root, "src/integration/x0t_governance_execute_handoff.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/x0t_bridge_config.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/x0t_contract_readiness.py", "def build_report(): pass\n")
    _write_text(root, "src/integration/x0t_contract_build_verification.py", "def build_report(): pass\n")
    _write_text(root, "scripts/ops/import_production_raw_evidence_bundle.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/generate_production_raw_evidence_template_pack.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/apply_operator_bundle_identity_patch.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/scaffold_x0t_external_settlement_evidence.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/scaffold_live_rollout_image_provenance_evidence.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/verify_x0t_external_settlement_evidence.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/verify_x0t_external_settlement_live_rpc.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/check_x0t_governance_execute_readiness.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/run_x0t_governance_execute_handoff.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/apply_x0t_bridge_contract_address.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/check_x0t_contract_readiness.py", "def main(): pass\n")
    _write_text(root, "scripts/ops/verify_x0t_contract_build.py", "def main(): pass\n")
    _write_text(root, "src/dao/contracts/contracts/X0TBridge.sol", "contract X0TBridge {}\n")
    _write_text(root, "src/dao/contracts/scripts/deploy_bridge.js", "X0TBridge deploy-bridge-base-sepolia\n")
    _write_text(root, "src/dao/contracts/test/X0TBridge.test.js", "X0TBridge BridgeDeposit BridgeRelease\n")
    _write_text(root, "tests/unit/test_integration_spine.py", "def test_spine(): pass\n")
    _write_text(root, "tests/unit/dao/test_token_bridge_unit.py", "def test_token_bridge(): pass\n")
    _write_text(root, "tests/unit/test_integration_current_evidence_rollup.py", "def test_current_rollup(): pass\n")
    _write_text(root, "tests/unit/test_integration_semantic_production_blocker_queue.py", "def test_semantic_queue(): pass\n")
    _write_text(root, "tests/unit/test_integration_raw_evidence_inventory.py", "def test_raw_inventory(): pass\n")
    _write_text(root, "tests/unit/test_integration_rollout_provenance.py", "def test_rollout_provenance(): pass\n")
    _write_text(root, "tests/unit/test_integration_evidence_source_candidates.py", "def test_source_candidates(): pass\n")
    _write_text(root, "tests/unit/test_integration_operator_bundle_gate.py", "def test_operator_bundle_gate(): pass\n")
    _write_text(root, "tests/unit/test_integration_operator_bundle_identity.py", "def test_operator_bundle_identity(): pass\n")
    _write_text(root, "tests/unit/test_integration_operator_evidence_packet.py", "def test_operator_packet(): pass\n")
    _write_text(root, "tests/unit/test_integration_production_evidence_replacement_passport.py", "def test_passport(): pass\n")
    _write_text(root, "tests/unit/test_integration_required_evidence_consistency.py", "def test_consistency(): pass\n")
    _write_text(root, "tests/unit/test_integration_rollup_approval_contract.py", "def test_rollup(): pass\n")
    _write_text(root, "tests/unit/test_integration_production_input_return_acceptance.py", "def test_return_acceptance(): pass\n")
    _write_text(root, "tests/unit/test_integration_production_input_pipeline.py", "def test_input_pipeline(): pass\n")
    _write_text(root, "tests/unit/test_integration_production_closeout_review.py", "def test_closeout(): pass\n")
    _write_text(root, "tests/unit/test_x0t_governance_execute_readiness.py", "def test_governance(): pass\n")
    _write_text(root, "tests/unit/test_x0t_governance_execute_handoff.py", "def test_governance_handoff(): pass\n")
    _write_text(root, "tests/unit/dao/test_x0t_bridge_config.py", "def test_bridge_config(): pass\n")
    _write_text(root, "tests/unit/dao/test_x0t_contract_readiness.py", "def test_contract_readiness(): pass\n")
    _write_text(root, "tests/unit/dao/test_x0t_contract_build_verification.py", "def test_contract_build(): pass\n")
    _write_text(root, "tests/unit/test_ops_production_evidence_validation_wrappers.py", "def test_wrappers(): pass\n")
    _write_text(root, "tests/unit/scripts/test_apply_operator_bundle_identity_patch.py", "def test_identity_patch(): pass\n")
    _write_text(
        root,
        "scripts/verify-v1.1.sh",
        (
            "pytest tests/unit/test_integration_completion_audit.py "
            "tests/unit/test_integration_current_evidence_rollup.py "
            "tests/unit/test_integration_semantic_production_blocker_queue.py "
            "tests/unit/test_integration_raw_evidence_inventory.py "
            "tests/unit/test_integration_evidence_source_candidates.py "
            "tests/unit/test_integration_operator_bundle_gate.py "
            "tests/unit/test_integration_operator_bundle_identity.py "
            "tests/unit/test_integration_operator_evidence_packet.py "
            "tests/unit/test_integration_production_evidence_replacement_passport.py "
            "tests/unit/test_ops_production_evidence_validation_wrappers.py "
            "tests/unit/scripts/test_apply_operator_bundle_identity_patch.py "
            "tests/unit/test_integration_required_evidence_consistency.py "
            "tests/unit/test_integration_rollup_approval_contract.py "
            "tests/unit/test_integration_production_input_return_acceptance.py "
            "tests/unit/test_integration_production_input_pipeline.py "
            "tests/unit/test_integration_production_closeout_review.py "
            "tests/unit/test_integration_production_evidence_intake.py "
            "tests/unit/test_integration_evidence_readiness.py "
            "tests/unit/test_integration_external_settlement.py "
            "tests/unit/dao/test_token_bridge_unit.py "
            "tests/unit/test_x0t_governance_execute_readiness.py "
            "tests/unit/test_x0t_governance_execute_handoff.py "
            "tests/unit/dao/test_x0t_bridge_config.py "
            "tests/unit/dao/test_x0t_contract_readiness.py "
            "tests/unit/dao/test_x0t_contract_build_verification.py "
            "tests/unit/test_integration_rollout_provenance.py "
            "tests/unit/test_integration_spine.py\n"
            "python3 -m src.integration.external_settlement --preflight-capture-inputs --require-preflight-ready\n"
            "integration-spine external settlement capture preflight fails closed\n"
            "CAPTURE_INPUTS_BLOCKED\n"
            "python3 scripts/ops/generate_production_raw_evidence_template_pack.py --write-template-files\n"
            "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --evidence external-settlement-evidence/settlement-submit.json --require-ready\n"
            "integration-spine external settlement template is rejected as retained evidence\n"
            "template_only must not be true\n"
            "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files\n"
            "python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready\n"
            "integration-spine production raw evidence templates are rejected as operator bundle evidence\n"
            "integration-spine live rollout image template is rejected as operator bundle evidence\n"
            "template/mock/placeholder markers must be absent\n"
            "X0T governance execute operator handoff is actionable and read-only\n"
            "X0T bridge config current shard is actionable and fail-closed\n"
            "X0T contract build verification artifact proves Node 22 Hardhat compile/test\n"
            "X0T contract/deployment readiness current shard is verified and fail-closed\n"
        ),
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-code-wiring-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "schema_version": "x0tta6bl4-integration-spine-code-wiring-evidence-v2-repo-generated",
            "goal_can_be_marked_complete": False,
            "mutates_runtime": False,
            "contacts_live_systems": False,
            "submits_transaction": False,
            "wiring_covered": {
                "identity": "ok",
                "event_bus": "ok",
                "policy_engine": "ok",
                "safe_actuator": "ok",
                "settlement_reward_loop": "ok",
            },
            "summary": {
                "trace_cases_total": 7,
                "trace_cases_passed": 7,
                "trace_cases_failed": 0,
                "canonical_identity_consistent": True,
                "policy_before_actuator_verified": True,
                "simulated_actuator_blocks_settlement": True,
                "settlement_failure_fails_closed": True,
                "simulated_settlement_fails_closed": True,
                "token_rewards_local_only_fails_closed": True,
            },
            "verify_entrypoint_integration": {"status": "VERIFIED HERE"},
        },
    )
    _write_governance_execute_readiness(root, executed=False)
    _write_governance_execute_handoff(root, executed=False)
    _write_x0t_bridge_config(root, ready=False)
    _write_x0t_contract_build_verification(root)
    _write_x0t_contract_readiness(root, ready=False)
    return root


def _write_operator_bundle_gates(root: Path, *, ready: bool) -> None:
    manifest_identity_mismatches = 0 if ready else 1
    for rel, prefix in [
        (".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json", "zero_trust_pqc"),
        (".tmp/validation-shards/self-healing-pqc-mesh-evidence-gate-current.json", "self_healing_pqc_mesh"),
        (".tmp/validation-shards/paid-client-serviceability-evidence-gate-current.json", "paid_client_serviceability"),
        (".tmp/validation-shards/live-rollout-evidence-gate-current.json", "live_rollout"),
    ]:
        _write_json(
            root,
            rel,
            {
                "status": "VERIFIED HERE",
                "ok": True,
                "decision": "READY_TO_INSTALL" if ready else "BLOCKED",
                f"{prefix}_decision": "READY" if ready else "BLOCKED",
                "goal_can_be_marked_complete": False,
                "summary": {
                    "bundle_files_total": 1,
                    "bundle_files_available": 1,
                    "bundle_manifest_identity_mismatches_total": manifest_identity_mismatches,
                    "bundle_raw_id_mismatches": 0,
                    "bundle_collector_id_mismatches": manifest_identity_mismatches,
                    "bundle_file_name_mismatches": 0,
                    "production_ready": ready,
                    f"{prefix}_ready": ready,
                },
            },
        )


def _write_operator_bundle_identity(root: Path, *, clean: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-bundle-identity-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "OPERATOR_BUNDLE_IDENTITY_CLEAN" if clean else "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED",
            "goal_can_be_marked_complete": False,
            "summary": {
                "files_total": 1,
                "files_available": 1,
                "files_needing_identity_update": 0 if clean else 1,
                "manifest_identity_mismatches_total": 0 if clean else 1,
                "collector_id_mismatches": 0 if clean else 1,
                "raw_id_mismatches": 0,
                "file_name_mismatches": 0,
                "identity_patch_entries_total": 0 if clean else 1,
                "identity_patch_operations_total": 0 if clean else 1,
                "clean": clean,
            },
        },
    )


def _write_operator_bundle_identity_patch(root: Path, *, clean: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-bundle-identity-patch-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "IDENTITY_PATCH_NOT_NEEDED" if clean else "IDENTITY_PATCH_DRY_RUN_READY",
            "goal_can_be_marked_complete": False,
            "apply_requested": False,
            "mutates_files": False,
            "mutates_files_outside_operator_bundle": False,
            "mutates_nl": False,
            "mutates_spb": False,
            "mutates_vpn_runtime": False,
            "materializes_evidence": False,
            "installs_raw_evidence": False,
            "promotes_production_ready": False,
            "changes_evidence_status": False,
            "summary": {
                "plan_entries_total": 0 if clean else 1,
                "would_update_files": 0 if clean else 1,
                "updated_files": 0,
                "unsafe_operations_total": 0,
            },
        },
    )


def _write_replacement_passport(root: Path, *, ready: bool) -> None:
    decision = "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR" if ready else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": decision,
            "production_ready": ready,
            "summary": {
                "items_total": 31,
                "items_ready": 31 if ready else 0,
                "items_blocking": 0 if ready else 31,
                "required_evidence_files_total": 31,
                "required_evidence_files_ready": 31 if ready else 0,
                "raw_install_claim_source": "return_acceptance",
                "current_raw_files_installed": 30 if ready else 0,
                "coverage_raw_files_reported_installed": 30,
                "return_acceptance_raw_files_staged": 30 if ready else 0,
                "return_acceptance_raw_files_local_observation": 0 if ready else 30,
                "source_errors_total": 0,
            },
            "replacement_items": [
                {
                    "replacement_contract": {
                        "validation_commands": [
                            "python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready",
                            "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready",
                            "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready",
                        ],
                        "external_scaffold_command": "python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py --write-template-files --force",
                    }
                }
            ],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
            if ready
            else "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR",
            "valid": True,
            "summary": {
                "checks_failed": 0,
                "passport_decision": decision,
            },
        },
    )


def _write_required_evidence_consistency(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR"
            if ready
            else "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR",
            "valid": True,
            "production_ready": ready,
            "summary": {
                "errors_total": 0,
                "required_evidence_files_total": 31,
                "required_evidence_files_ready": 31 if ready else 0,
                "required_evidence_files_blocking": 0 if ready else 31,
                "raw_required_evidence_files_total": 30,
                "raw_required_evidence_files_ready": 30 if ready else 0,
                "external_required_evidence_files_total": 1,
                "external_required_evidence_files_ready": 1 if ready else 0,
                "packet_required_evidence_files_total": 31,
                "packet_passport_item_coverage_ready": True,
                "raw_operator_packet_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS"
                if ready
                else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_operator_packet_readiness_ready_for_collectors": ready,
                "raw_operator_packet_readiness_collectors_ready": 1 if ready else 0,
                "raw_operator_packet_readiness_collectors_blocked": 0 if ready else 1,
                "raw_operator_packet_readiness_collectors_total": 1,
                "raw_operator_packet_readiness_raw_files_ready": 30 if ready else 0,
                "raw_operator_packet_readiness_raw_files_local_observation": 0 if ready else 30,
                "raw_operator_packet_readiness_raw_files_total": 30,
                "raw_operator_packet_production_ready_blocked_by_raw_readiness": False,
            },
        },
    )


def _write_rollup_approval_contract(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-rollup-approval-contract-v2",
            "status": "VERIFIED HERE",
            "ok": True,
            "ready": ready,
            "decision": "ROLLUP_APPROVAL_READY" if ready else "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "sources_total": 8,
                "sources_ready": 8 if ready else 0,
                "source_errors_total": 0,
                "evidence_files_total": 31,
                "evidence_files_valid": 31 if ready else 0,
            },
        },
    )


def _write_production_input_return_acceptance(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-input-return-acceptance-v4",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE",
            "acceptance_decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED",
            "ready_to_stage": ready,
            "ready_for_pipeline_install": ready,
            "goal_can_be_marked_complete": False,
            "summary": {
                "source_errors_total": 0,
                "evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "evidence_keys_ready_to_stage": len(REQUIRED_EVIDENCE_KEYS) if ready else 4,
                "raw_files_expected": 30,
                "raw_files_staged": 30 if ready else 0,
                "raw_files_local_observation": 0 if ready else 30,
                "external_artifacts_expected": 1,
                "external_settlement_live_rpc_ready": ready,
                "ready_for_pipeline_install": ready,
            },
        },
    )


def _write_production_input_pipeline(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-input-pipeline-v4-repo-generated",
            "status": "VERIFIED HERE",
            "ok": True,
            "pipeline_decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW"
            if ready
            else "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE",
            "ready": ready,
            "goal_can_be_marked_complete": False,
            "mutates_files": False,
            "runs_collectors": False,
            "runs_live_rpc": False,
            "summary": {
                "source_errors_total": 0,
                "ready": ready,
                "raw_files_install_claim_source": "return_acceptance",
                "raw_files_installed": 30 if ready else 0,
                "raw_files_staged": 30 if ready else 0,
                "raw_files_preflight_reported_installed": 30 if ready else 0,
                "raw_files_local_observation": 0 if ready else 30,
                "blocking_inputs_total": 0 if ready else 5,
                "external_settlement_live_rpc_ready": ready,
            },
        },
    )


def _write_production_closeout_review(root: Path, *, ready: bool) -> None:
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-closeout-review-current.json",
        {
            "schema_version": "x0tta6bl4-integration-spine-production-closeout-v4",
            "status": "VERIFIED HERE",
            "ok": True,
            "ready": ready,
            "decision": "CLOSEOUT_REVIEW_READY" if ready else "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "ready": ready,
                "sources_total": 6,
                "sources_ready": 6 if ready else 0,
                "source_errors_total": 0,
                "blocking_inputs_total": 0 if ready else 1,
                "raw_files_installed": 30 if ready else 0,
                "raw_files_install_claim_source": "return_acceptance",
                "raw_files_pipeline_reported_installed": 30,
                "raw_files_existing_or_retained": 30,
                "required_evidence_files_total": 31,
                "rollup_evidence_files_total": 31,
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
                "x0t_contract_handoff_operator_sequence_ready": False if ready else True,
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
                "live_rollout_handoff_operator_sequence_ready": False if ready else True,
            },
        },
    )


def _write_production_ready(root: Path):
    _write_governance_execute_readiness(root, executed=True)
    _write_governance_execute_handoff(root, executed=True)
    _write_x0t_bridge_config(root, ready=True)
    _write_x0t_contract_build_verification(root)
    _write_x0t_contract_readiness(root, ready=True)
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "goal_can_be_marked_complete": True,
            "completion_decision": "COMPLETE",
            "summary": {
                "blocking_items_total": 0,
                "semantic_preflight_errors_total": 0,
                "current_raw_files_installed": 30,
                "raw_install_claim_source": "return_acceptance",
                "pipeline_raw_files_reported_installed": 30,
                "return_acceptance_raw_files_local_observation": 0,
                "source_errors_total": 0,
                "by_layer": {},
                "by_collector": {},
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-evidence-readiness-current.json",
        {
            "decision": "READY_TO_PROMOTE",
            "summary": {
                "raw_inventory_ready": True,
                "semantic_queue_ready": True,
                "production_evidence_ready": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_SOURCE_CANDIDATES_AVAILABLE",
            "required_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
            "summary": {
                "required_inputs_ready": len(REQUIRED_EVIDENCE_KEYS),
                "required_inputs_total": len(REQUIRED_EVIDENCE_KEYS),
                "ready_source_candidates_total": len(REQUIRED_EVIDENCE_KEYS),
                "routes_total": len(REQUIRED_EVIDENCE_KEYS),
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json",
        {
            "decision": "READY_FOR_INSTALL",
            "summary": {
                "ready_for_install": True,
                "required_evidence_keys_ready": len(REQUIRED_EVIDENCE_KEYS),
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "required_evidence_keys_pending": 0,
                "raw_operator_bundle_syntax_ready": True,
                "source_candidate_gate_ready": True,
                "production_import_gate_ready": True,
            },
            "pending_evidence_keys": [],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "NO_PRODUCTION_EVIDENCE_GAPS",
            "goal_can_be_marked_complete": True,
            "summary": {
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "ready_evidence_keys": len(REQUIRED_EVIDENCE_KEYS),
                "pending_evidence_keys": 0,
                "missing_source_artifacts": 0,
                "blocked_source_artifacts": 0,
                "route_missing": 0,
                "import_mismatches": 0,
                "source_artifacts_clear": True,
                "completion_audit_clear": True,
                "primary_blocker_evidence_key": "",
                "external_settlement_handoff_clear": True,
                "external_settlement_handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY",
                "external_settlement_handoff_ready_for_completion_rerun": True,
                "external_settlement_capture_preflight_decision": "CAPTURE_INPUTS_READY",
                "external_settlement_handoff_operator_command_entrypoints_missing": 0,
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "external_settlement_handoff_operator_command_shell_surface_ready": True,
                "raw_operator_packet_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS",
                "raw_operator_packet_readiness_ready_for_collectors": True,
                "raw_operator_packet_readiness_collectors_ready": 1,
                "raw_operator_packet_readiness_collectors_blocked": 0,
                "raw_operator_packet_readiness_collectors_total": 1,
                "raw_operator_packet_readiness_raw_files_ready": 30,
                "raw_operator_packet_readiness_raw_files_local_observation": 0,
                "raw_operator_packet_readiness_raw_files_total": 30,
            },
            "operator_priority_order": [],
            "blocking_evidence_keys": [],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "actionable": True,
            "decision": "NO_ACTION_REQUIRED",
            "selected_evidence_key": "",
            "summary": {
                "selected_evidence_key": "",
                "required_artifacts_total": 0,
                "commands_total": 0,
                "commands_missing_entrypoints": 0,
                "operator_action_required": False,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALL_OPERATOR_PACKETS_ACTIONABLE",
            "all_packets_actionable": True,
            "summary": {
                "packets_total": 0,
                "actionable_packets": 0,
                "packets_with_missing_entrypoints": 0,
                "commands_missing_entrypoints_total": 0,
                "all_packets_actionable": True,
            },
        },
    )
    _write_operator_bundle_gates(root, ready=True)
    _write_operator_bundle_identity(root, clean=True)
    _write_operator_bundle_identity_patch(root, clean=True)
    _write_replacement_passport(root, ready=True)
    _write_required_evidence_consistency(root, ready=True)
    _write_rollup_approval_contract(root, ready=True)
    _write_production_input_return_acceptance(root, ready=True)
    _write_production_input_pipeline(root, ready=True)
    _write_production_closeout_review(root, ready=True)
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
        {
            "decision": "READY_TO_CLOSE",
            "summary": {
                "expected_evidence_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                "expected_evidence_file_exists": True,
                "x0t_external_settlement_ready": True,
                "live_rpc_ready": True,
                "fake_external_settlement_prevention_enforced": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "READY_TO_CLOSE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "can_close_image_digests_blocker": True,
                "collector_image_digest_preflight_errors": 0,
                "raw_deploy_images_total": 7,
                "raw_deploy_images_digest_pinned": 7,
                "runtime_image_provenance_artifacts_retained_here": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/live-rollout-image-provenance-scaffold-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "scaffold_decision": "TEMPLATE_ONLY_NOT_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "materializes_evidence": False,
            "contacts_registry": False,
            "contacts_cluster": False,
            "runs_cosign": False,
            "mutates_vpn_runtime": False,
            "summary": {
                "template_files_total": 4,
                "templates_marked_not_evidence": True,
                "template_validation_rejects_as_rollout_evidence": True,
                "current_runtime_tag_refs_total": 7,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE",
            "goal_can_be_marked_complete": True,
            "summary": {
                "files_total": 30,
                "pipeline_raw_files_installed": 30,
                "pipeline_raw_files_reported_installed": 30,
                "raw_install_claim_source": "return_acceptance",
                "return_acceptance_raw_files_expected": 30,
                "return_acceptance_raw_files_staged": 30,
                "return_acceptance_raw_files_ready_to_stage": 30,
                "return_acceptance_raw_files_destination_existing": 30,
                "return_acceptance_raw_files_local_observation": 0,
                "return_acceptance_raw_ready_to_stage": True,
                "usable_for_goal_completion_files": 30,
                "semantic_blockers_total": 0,
                "source_errors_total": 0,
                "classification_counts": {"PRODUCTION_GRADE": 30},
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "COMPLETE",
            "goal_can_be_marked_complete": True,
            "summary": {
                "source_errors_total": 0,
                "top_blockers_total": 0,
                "external_settlement_decision": "READY_TO_CLOSE",
                "image_digests_decision": "READY_TO_CLOSE",
                "semantic_blocking_items_total": 0,
            },
        },
    )


def test_completion_audit_reports_local_wiring_passed_but_production_blocked(tmp_path):
    root = _base_root(tmp_path)
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "goal_can_be_marked_complete": False,
            "completion_decision": "NOT_COMPLETE",
            "summary": {
                "blocking_items_total": 71,
                "semantic_preflight_errors_total": 70,
                "current_raw_files_installed": 0,
                "raw_install_claim_source": "return_acceptance",
                "pipeline_raw_files_reported_installed": 30,
                "return_acceptance_raw_files_local_observation": 30,
                "source_errors_total": 0,
                "by_layer": {"safe_actuator": 41},
                "by_collector": {"live-rollout": 17},
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-evidence-readiness-current.json",
        {
            "decision": "BLOCKED_ON_PRODUCTION_EVIDENCE",
            "summary": {
                "raw_inventory_ready": False,
                "semantic_queue_ready": False,
                "production_evidence_ready": False,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED",
            "required_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
            "summary": {
                "required_inputs_ready": 0,
                "required_inputs_total": len(REQUIRED_EVIDENCE_KEYS),
                "ready_source_candidates_total": 0,
                "routes_total": len(REQUIRED_EVIDENCE_KEYS),
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json",
        {
            "decision": "BLOCKED_OPERATOR_EVIDENCE_REQUIRED",
            "summary": {
                "ready_for_install": False,
                "required_evidence_keys_ready": 0,
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "required_evidence_keys_pending": len(REQUIRED_EVIDENCE_KEYS),
                "raw_operator_bundle_syntax_ready": True,
                "source_candidate_gate_ready": False,
                "production_import_gate_ready": False,
            },
            "pending_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-production-gap-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "BLOCKED_ON_OPERATOR_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "required_evidence_keys_total": len(REQUIRED_EVIDENCE_KEYS),
                "ready_evidence_keys": 0,
                "pending_evidence_keys": len(REQUIRED_EVIDENCE_KEYS),
                "missing_source_artifacts": 1,
                "blocked_source_artifacts": len(REQUIRED_EVIDENCE_KEYS) - 1,
                "route_missing": 0,
                "import_mismatches": 0,
                "source_artifacts_clear": False,
                "completion_audit_clear": False,
                "primary_blocker_evidence_key": "external_settlement",
                "external_settlement_handoff_clear": True,
                "external_settlement_handoff_decision": "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
                "external_settlement_handoff_ready_for_completion_rerun": False,
                "external_settlement_capture_preflight_decision": "CAPTURE_INPUTS_BLOCKED",
                "external_settlement_handoff_operator_command_entrypoints_missing": 0,
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": 0,
                "external_settlement_handoff_operator_command_shell_surface_ready": True,
                "raw_operator_packet_readiness_decision": "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_operator_packet_readiness_ready_for_collectors": False,
                "raw_operator_packet_readiness_collectors_ready": 0,
                "raw_operator_packet_readiness_collectors_blocked": 1,
                "raw_operator_packet_readiness_collectors_total": 1,
                "raw_operator_packet_readiness_raw_files_ready": 0,
                "raw_operator_packet_readiness_raw_files_local_observation": 30,
                "raw_operator_packet_readiness_raw_files_total": 30,
            },
            "operator_priority_order": sorted(REQUIRED_EVIDENCE_KEYS),
            "blocking_evidence_keys": sorted(REQUIRED_EVIDENCE_KEYS),
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "actionable": True,
            "decision": "OPERATOR_ACTION_REQUIRED",
            "selected_evidence_key": "external_settlement",
            "summary": {
                "selected_evidence_key": "external_settlement",
                "required_artifacts_total": 4,
                "commands_total": 7,
                "commands_missing_entrypoints": 0,
                "operator_action_required": True,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "OPERATOR_PACKET_ENTRYPOINTS_MISSING",
            "all_packets_actionable": False,
            "summary": {
                "packets_total": 5,
                "actionable_packets": 1,
                "packets_with_missing_entrypoints": 4,
                "commands_missing_entrypoints_total": 8,
                "all_packets_actionable": False,
            },
            "packet_summaries": [
                {
                    "evidence_key": "external_settlement",
                    "packet_kind": "external_settlement",
                    "commands_missing_entrypoints": 0,
                    "required_operator_inputs": [
                        "real submitted X0T transaction hash",
                        "destination Base chain",
                        "settlement_id tied to the integration-spine reward/settlement loop",
                        "read-only RPC URL for the same Base chain",
                        "retained source commands and explorer URL proving the receipt",
                    ],
                    "required_fields": [
                        "transaction_hash is a 0x-prefixed 32-byte hash",
                        "destination_chain is base-sepolia/base_sepolia or base-mainnet/base",
                        "settlement_id is specific and non-placeholder",
                        "source_commands contains exact retained commands",
                        "explorer_url is HTTPS and matches destination_chain",
                        "packet_hash is a 64-character lowercase hex digest",
                    ],
                    "commands": [
                        {
                            "command": "python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py --write-template-files --force",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "export X0T_BASE_RPC_URL='<read-only Base RPC URL for the matching chain>'",
                            "existing_entrypoint": True,
                            "requires_operator_input": True,
                        },
                        {
                            "command": "export X0T_SETTLEMENT_TX_HASH='<0x-prefixed submitted settlement transaction hash>'",
                            "existing_entrypoint": True,
                            "requires_operator_input": True,
                        },
                        {
                            "command": "export X0T_DESTINATION_CHAIN='<base-sepolia|base|base-mainnet>'",
                            "existing_entrypoint": True,
                            "requires_operator_input": True,
                        },
                        {
                            "command": "export X0T_SETTLEMENT_ID='<non-placeholder settlement id>'",
                            "existing_entrypoint": True,
                            "requires_operator_input": True,
                        },
                        {
                            "command": "python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --require-preflight-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.external_settlement --root . --capture-from-rpc --write-evidence --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_input_return_acceptance --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_input_pipeline --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_closeout_review --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                    ],
                    "fail_closed_rules": [
                        "Do not treat external settlement scaffold templates as production evidence."
                    ],
                },
                *[
                    {
                        "evidence_key": key,
                        "packet_kind": "raw_production_bundle",
                        "required_operator_inputs": [
                            "production environment identifier",
                            "operator or CI identity that collected the evidence",
                            "exact source_commands for every JSON file",
                            "domain-specific production observations required by the collector",
                        ],
                        "required_fields": [
                            "status or evidence_status == VERIFIED HERE",
                            "collector_id matches the intake manifest collector_id",
                            "raw_id matches the intake manifest raw_id",
                            "file_name matches the intake manifest file_name",
                            "collected_at is a UTC timestamp",
                            "collected_by is a specific operator or CI identity",
                            "source_commands is a non-empty list of exact commands",
                            "production_ready == true",
                            "production_promotion_blockers is absent or empty",
                            "claim_boundary/environment does not describe local context",
                            "template/mock/placeholder markers are absent",
                        ],
                        "commands": [
                            {
                                "command": "python3 scripts/ops/generate_production_raw_evidence_template_pack.py --write-template-files --force",
                                "existing_entrypoint": True,
                            },
                            {
                                "command": "write real production JSON files to the required operator bundle paths",
                                "existing_entrypoint": True,
                                "requires_operator_input": True,
                            },
                            {
                                "command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json",
                                "existing_entrypoint": True,
                            },
                            {
                                "command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json --apply",
                                "existing_entrypoint": True,
                            },
                            {
                                "command": "python3 -m src.integration.production_input_return_acceptance --root . --require-ready",
                                "existing_entrypoint": True,
                            },
                            {
                                "command": "python3 -m src.integration.production_input_pipeline --root . --require-ready",
                                "existing_entrypoint": True,
                            },
                            {
                                "command": "python3 -m src.integration.production_closeout_review --root . --require-ready",
                                "existing_entrypoint": True,
                            },
                        ],
                        "fail_closed_rules": [
                            "Do not treat production raw evidence template pack files as production evidence."
                        ],
                    }
                    for key in ("live_spire_mtls", "multi_host_mesh", "paid_client_path")
                ],
                {
                    "evidence_key": "safe_rollout_rollback",
                    "packet_kind": "raw_production_bundle",
                    "required_operator_inputs": [
                        "production environment identifier",
                        "operator or CI identity that collected the evidence",
                        "exact source_commands for every JSON file",
                        "domain-specific production observations required by the collector",
                        "digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image",
                        "retained per-image cosign/SLSA provenance artifacts for current deployed image digests",
                    ],
                    "required_fields": [
                        "status or evidence_status == VERIFIED HERE",
                        "collector_id matches the intake manifest collector_id",
                        "raw_id matches the intake manifest raw_id",
                        "file_name matches the intake manifest file_name",
                        "collected_at is a UTC timestamp",
                        "collected_by is a specific operator or CI identity",
                        "source_commands is a non-empty list of exact commands",
                        "production_ready == true",
                        "production_promotion_blockers is absent or empty",
                        "claim_boundary/environment does not describe local context",
                        "template/mock/placeholder markers are absent",
                    ],
                    "commands": [
                        {
                            "command": "python3 scripts/ops/generate_production_raw_evidence_template_pack.py --write-template-files --force",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "write real production JSON files to the required operator bundle paths",
                            "existing_entrypoint": True,
                            "requires_operator_input": True,
                        },
                        {
                            "command": "python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --identity-report .tmp/validation-shards/integration-spine-operator-bundle-identity-current.json --apply",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_input_return_acceptance --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_input_pipeline --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                        {
                            "command": "python3 -m src.integration.production_closeout_review --root . --require-ready",
                            "existing_entrypoint": True,
                        },
                    ],
                    "fail_closed_rules": [
                        "Do not treat production raw evidence template pack files as production evidence.",
                        "Do not treat live rollout image provenance scaffold templates as production evidence.",
                    ],
                },
            ],
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json",
        _operator_packet_index_payload(),
    )
    _write_operator_bundle_gates(root, ready=False)
    _write_operator_bundle_identity(root, clean=False)
    _write_operator_bundle_identity_patch(root, clean=False)
    _write_replacement_passport(root, ready=False)
    _write_required_evidence_consistency(root, ready=False)
    _write_rollup_approval_contract(root, ready=False)
    _write_production_input_return_acceptance(root, ready=False)
    _write_production_input_pipeline(root, ready=False)
    _write_production_closeout_review(root, ready=False)
    _write_json(
        root,
        ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json",
        {
            "decision": "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
            "summary": {
                "expected_evidence_file_exists": False,
                "x0t_external_settlement_ready": False,
                "live_rpc_ready": False,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
            "goal_can_be_marked_complete": False,
            "summary": {
                "can_close_image_digests_blocker": False,
                "collector_image_digest_preflight_errors": 7,
                "raw_deploy_images_total": 7,
                "raw_deploy_images_digest_pinned": 0,
                "runtime_image_provenance_artifacts_retained_here": False,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/live-rollout-image-provenance-scaffold-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "scaffold_decision": "TEMPLATE_ONLY_NOT_EVIDENCE",
            "goal_can_be_marked_complete": False,
            "materializes_evidence": False,
            "contacts_registry": False,
            "contacts_cluster": False,
            "runs_cosign": False,
            "mutates_vpn_runtime": False,
            "summary": {
                "template_files_total": 4,
                "templates_marked_not_evidence": True,
                "template_validation_rejects_as_rollout_evidence": True,
                "current_runtime_tag_refs_total": 7,
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "files_total": 30,
                "pipeline_raw_files_installed": 30,
                "pipeline_raw_files_reported_installed": 30,
                "raw_install_claim_source": "return_acceptance",
                "return_acceptance_raw_files_expected": 30,
                "return_acceptance_raw_files_staged": 0,
                "return_acceptance_raw_files_ready_to_stage": 0,
                "return_acceptance_raw_files_destination_existing": 30,
                "return_acceptance_raw_files_local_observation": 30,
                "return_acceptance_raw_ready_to_stage": False,
                "usable_for_goal_completion_files": 0,
                "semantic_blockers_total": 70,
                "source_errors_total": 0,
                "classification_counts": {"RETAINED_COMPONENT_EVIDENCE_NOT_PRODUCTION_GRADE": 30},
            },
        },
    )
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "summary": {
                "source_errors_total": 0,
                "top_blockers_total": 3,
                "external_settlement_decision": "BLOCKED_ON_REAL_SETTLEMENT_RECEIPT",
                "image_digests_decision": "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS",
                "semantic_blocking_items_total": 71,
            },
        },
    )

    audit = build_audit(root)

    assert audit["completion_decision"] == "NOT_COMPLETE"
    assert audit["goal_can_be_marked_complete"] is False
    assert audit["summary"]["local_wiring_passed"] is True
    assert audit["summary"]["production_readiness_passed"] is False
    assert audit["summary"]["checklist_generic_blocking"] == 0
    assert audit["summary"]["checklist_operator_input_required"] == 8
    assert audit["summary"]["checklist_operator_approval_required"] == 0
    assert audit["summary"]["checklist_after_blockers"] == 2
    assert audit["summary"]["checklist_status_counts"]["OPERATOR_INPUT_REQUIRED"] == 8
    assert audit["summary"]["checklist_status_counts"]["AFTER_BLOCKERS"] == 2
    assert audit["summary"]["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert audit["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert audit["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 0
    assert audit["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 1
    assert audit["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 30
    assert audit["summary"]["raw_operator_packet_readiness_raw_files_total"] == 30
    assert audit["summary"]["x0t_governance_execute_decision"] == "NOT_READY_TIMELOCK_ACTIVE"
    assert audit["summary"]["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS"
    )
    assert audit["summary"]["x0t_governance_execute_handoff_actionable"] is True
    assert audit["summary"]["x0t_governance_ready_for_operator_execute"] is False
    assert audit["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
    assert audit["summary"]["x0t_governance_handoff_operator_commands_total"] == 5
    assert audit["summary"]["x0t_governance_handoff_operator_command_entrypoints_missing"] == 0
    assert audit["summary"]["x0t_governance_handoff_operator_command_surface_ready"] is True
    assert audit["summary"]["x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert audit["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert audit["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert audit["summary"]["x0t_governance_proposal_executed"] is False
    assert audit["summary"]["x0t_bridge_config_decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    assert audit["summary"]["x0t_bridge_config_ready"] is False
    assert audit["summary"]["x0t_bridge_address_input_ready"] is False
    assert audit["summary"]["x0t_bridge_configured_bridge_ready"] is False
    assert audit["summary"]["x0t_contract_readiness_decision"] == "BLOCKED_ON_DEPLOYMENT_CONFIG"
    assert audit["summary"]["x0t_contract_readiness_clear"] is False
    assert audit["summary"]["x0t_contract_build_env_ready"] is True
    assert audit["summary"]["x0t_contract_build_verification_ready"] is True
    assert audit["summary"]["x0t_contract_bridge_source_ready"] is True
    assert audit["summary"]["x0t_contract_operator_configs_ready"] is False
    assert audit["summary"]["x0t_contract_missing_inputs_total"] == 1
    assert audit["summary"]["x0t_contract_deployment_ready"] is False
    assert audit["summary"]["x0t_contract_handoff_available"] is True
    assert audit["summary"]["x0t_contract_handoff_decision"] == (
        "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
    )
    assert audit["summary"]["x0t_contract_handoff_deployment_ready"] is False
    assert audit["summary"]["x0t_contract_handoff_approval_value_required"] == (
        "apply-bridge-address-base-sepolia"
    )
    assert audit["summary"]["x0t_contract_handoff_missing_inputs_total"] == 1
    assert audit["summary"]["x0t_contract_handoff_operator_actions_total"] == 6
    assert audit["summary"]["x0t_contract_handoff_operator_approval_required_actions_total"] == 1
    assert audit["summary"]["x0t_contract_handoff_operator_commands_total"] == 5
    assert audit["summary"]["x0t_contract_handoff_operator_command_entrypoints_missing"] == 0
    assert audit["summary"]["x0t_contract_handoff_operator_command_surface_ready"] is True
    assert audit["summary"]["x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert audit["summary"]["x0t_contract_handoff_operator_command_shell_surface_ready"] is True
    assert audit["summary"]["x0t_contract_handoff_operator_sequence_ready"] is True
    assert audit["summary"]["live_rollout_handoff_available"] is True
    assert audit["summary"]["live_rollout_handoff_decision"] == (
        "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
    )
    assert audit["summary"]["live_rollout_handoff_ready_for_completion_rerun"] is False
    assert audit["summary"]["live_rollout_handoff_can_close_image_digests_blocker"] is False
    assert audit["summary"]["live_rollout_handoff_missing_inputs_total"] == 1
    assert audit["summary"]["live_rollout_handoff_operator_actions_total"] == 5
    assert audit["summary"]["live_rollout_handoff_operator_input_required_actions_total"] == 2
    assert audit["summary"]["live_rollout_handoff_operator_commands_total"] == 4
    assert audit["summary"]["live_rollout_handoff_operator_command_entrypoints_missing"] == 0
    assert audit["summary"]["live_rollout_handoff_operator_command_surface_ready"] is True
    assert audit["summary"]["live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert audit["summary"]["live_rollout_handoff_operator_command_shell_surface_ready"] is True
    assert audit["summary"]["live_rollout_handoff_operator_sequence_ready"] is True
    assert audit["summary"]["external_settlement_handoff_clear"] is True
    assert audit["summary"]["external_settlement_handoff_decision"] == (
        "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    )
    assert audit["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is False
    assert audit["summary"]["external_settlement_capture_preflight_decision"] == "CAPTURE_INPUTS_BLOCKED"
    assert audit["summary"]["external_settlement_handoff_operator_command_entrypoints_missing"] == 0
    assert audit["summary"]["external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert audit["summary"]["external_settlement_handoff_operator_command_shell_surface_ready"] is True
    blocking_ids = {item["id"] for item in audit["blocking_items"]}
    assert "operator_evidence_packet_actionable" not in blocking_ids
    assert "current_evidence_rollup_reproducible" not in blocking_ids
    assert "operator_bundle_gates_fail_closed" not in blocking_ids
    assert "operator_bundle_manifest_identity_audited" not in blocking_ids
    assert "semantic_production_blocker_queue_reproducible" not in blocking_ids
    assert "raw_evidence_inventory_reproducible" not in blocking_ids
    assert "rollout_provenance_gate_reproducible" not in blocking_ids
    assert "rollout_image_provenance_scaffold_available" not in blocking_ids
    assert "operator_bundle_identity_plan_available" not in blocking_ids
    assert "operator_bundle_identity_patch_entrypoint_available" not in blocking_ids
    assert "operator_packet_identity_patch_dry_run_command_available" not in blocking_ids
    assert "operator_evidence_packet_index_complete" not in blocking_ids
    assert "operator_packet_identity_suggestions_available" not in blocking_ids
    assert "operator_packet_replacement_passport_command_available" not in blocking_ids
    assert "operator_packet_post_intake_commands_available" not in blocking_ids
    assert "operator_packet_external_settlement_wrapper_commands_available" not in blocking_ids
    assert "operator_packet_external_settlement_operator_inputs_available" not in blocking_ids
    assert "operator_packet_external_settlement_capture_commands_available" not in blocking_ids
    assert "external_settlement_template_rejection_smoke_available" not in blocking_ids
    assert "raw_evidence_template_rejection_smoke_available" not in blocking_ids
    assert "live_rollout_image_template_rejection_smoke_available" not in blocking_ids
    assert "operator_packet_raw_template_pack_command_available" not in blocking_ids
    assert "operator_packet_raw_required_inputs_available" not in blocking_ids
    assert "replacement_passport_validation_commands_available" not in blocking_ids
    assert "replacement_passport_external_scaffold_command_available" not in blocking_ids
    assert "x0t_bridge_config_handoff_actionable" not in blocking_ids
    assert "x0t_contract_readiness_reproducible" not in blocking_ids
    assert "x0t_governance_execute_readiness_reproducible" not in blocking_ids
    assert "x0t_governance_execute_handoff_actionable" not in blocking_ids
    assert "required_evidence_consistency_valid" not in blocking_ids
    assert "rollup_approval_contract_reproducible" not in blocking_ids
    assert "production_input_return_acceptance_reproducible" not in blocking_ids
    assert "production_input_pipeline_reproducible" not in blocking_ids
    assert "production_closeout_review_reproducible" not in blocking_ids
    assert "production_evidence_replacement_passport_clear" in blocking_ids
    assert "production_evidence_intake_ready" in blocking_ids
    assert "production_gap_index_sources_clear" in blocking_ids
    assert "external_x0t_settlement_ready" in blocking_ids
    assert "x0t_governance_proposal_executed" in blocking_ids
    assert "x0t_contract_deployment_ready" in blocking_ids
    assert "live_rollout_digest_and_provenance_ready" in blocking_ids
    blocking_statuses = {item["id"]: item["status"] for item in audit["blocking_items"]}
    assert blocking_statuses["production_evidence_replacement_passport_clear"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["production_evidence_intake_ready"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["production_gap_index_sources_clear"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["semantic_production_blockers_closed"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["external_x0t_settlement_ready"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["x0t_governance_proposal_executed"] == "AFTER_BLOCKERS"
    assert blocking_statuses["x0t_contract_deployment_ready"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["live_rollout_digest_and_provenance_ready"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["raw_evidence_is_production_grade"] == "OPERATOR_INPUT_REQUIRED"
    assert blocking_statuses["current_rollup_complete"] == "AFTER_BLOCKERS"


def test_completion_audit_can_mark_complete_when_every_artifact_is_ready(tmp_path):
    root = _base_root(tmp_path)
    _write_production_ready(root)

    audit = build_audit(root)

    assert audit["completion_decision"] == "COMPLETE"
    assert audit["goal_can_be_marked_complete"] is True
    assert audit["summary"]["checklist_total"] == 54
    assert audit["summary"]["checklist_generic_blocking"] == 0
    assert audit["summary"]["checklist_operator_input_required"] == 0
    assert audit["summary"]["checklist_operator_approval_required"] == 0
    assert audit["summary"]["checklist_after_blockers"] == 0
    assert audit["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is True
    assert audit["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 30
    assert audit["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 0
    assert audit["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 0
    assert audit["summary"]["x0t_governance_execute_decision"] == "ALREADY_EXECUTED"
    assert audit["summary"]["x0t_governance_execute_handoff_decision"] == (
        "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED"
    )
    assert audit["summary"]["x0t_governance_execute_handoff_actionable"] is True
    assert audit["summary"]["x0t_governance_proposal_executed"] is True
    assert audit["summary"]["x0t_governance_handoff_operator_actions_total"] == 5
    assert audit["summary"]["x0t_governance_handoff_operator_commands_total"] == 5
    assert audit["summary"]["x0t_governance_handoff_operator_command_entrypoints_missing"] == 0
    assert audit["summary"]["x0t_governance_handoff_operator_command_surface_ready"] is True
    assert audit["summary"]["x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"] == 0
    assert audit["summary"]["x0t_governance_handoff_operator_command_shell_surface_ready"] is True
    assert audit["summary"]["x0t_governance_handoff_operator_sequence_ready"] is True
    assert audit["summary"]["x0t_bridge_config_decision"] == "X0T_BRIDGE_CONFIG_READY"
    assert audit["summary"]["x0t_bridge_config_ready"] is True
    assert audit["summary"]["x0t_bridge_address_input_ready"] is True
    assert audit["summary"]["x0t_bridge_configured_bridge_ready"] is True
    assert audit["summary"]["x0t_contract_readiness_decision"] == "CONTRACT_READINESS_CLEAR"
    assert audit["summary"]["x0t_contract_readiness_clear"] is True
    assert audit["summary"]["x0t_contract_build_env_ready"] is True
    assert audit["summary"]["x0t_contract_build_verification_ready"] is True
    assert audit["summary"]["x0t_contract_bridge_source_ready"] is True
    assert audit["summary"]["x0t_contract_operator_configs_ready"] is True
    assert audit["summary"]["x0t_contract_missing_inputs_total"] == 0
    assert audit["summary"]["x0t_contract_deployment_ready"] is True
    assert audit["summary"]["x0t_contract_handoff_available"] is True
    assert audit["summary"]["x0t_contract_handoff_decision"] == "X0T_CONTRACT_DEPLOYMENT_CONFIG_READY"
    assert audit["summary"]["x0t_contract_handoff_deployment_ready"] is True
    assert audit["summary"]["x0t_contract_handoff_operator_actions_total"] == 0
    assert audit["summary"]["x0t_contract_handoff_operator_commands_total"] == 0
    assert audit["summary"]["live_rollout_handoff_available"] is True
    assert audit["summary"]["live_rollout_handoff_decision"] == "LIVE_ROLLOUT_IMAGE_DIGESTS_READY"
    assert audit["summary"]["live_rollout_handoff_ready_for_completion_rerun"] is True
    assert audit["summary"]["live_rollout_handoff_operator_actions_total"] == 0
    assert audit["summary"]["live_rollout_handoff_operator_commands_total"] == 0
    assert audit["summary"]["external_settlement_handoff_clear"] is True
    assert audit["summary"]["external_settlement_handoff_decision"] == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY"
    assert audit["summary"]["external_settlement_handoff_ready_for_completion_rerun"] is True
    assert audit["blocking_items"] == []


def test_completion_audit_blocks_when_bundle_manifest_identity_counters_are_missing(tmp_path):
    root = _base_root(tmp_path)
    _write_production_ready(root)
    gate_path = root / ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["summary"].pop("bundle_manifest_identity_mismatches_total")
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    audit = build_audit(root)

    blocking_ids = {item["id"] for item in audit["blocking_items"]}
    assert audit["completion_decision"] == "NOT_COMPLETE"
    assert "operator_bundle_manifest_identity_audited" in blocking_ids


def test_completion_audit_blocks_when_external_scaffold_entrypoint_is_missing(tmp_path):
    root = _base_root(tmp_path)
    _write_production_ready(root)
    (root / "scripts/ops/scaffold_x0t_external_settlement_evidence.py").unlink()

    audit = build_audit(root)

    blocking_ids = {item["id"] for item in audit["blocking_items"]}
    assert audit["completion_decision"] == "NOT_COMPLETE"
    assert "replacement_passport_external_scaffold_command_available" in blocking_ids


def test_completion_audit_requires_governance_execute_handoff(tmp_path):
    root = _base_root(tmp_path)
    (root / ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json").unlink()

    audit = build_audit(root)

    blocking_ids = {item["id"] for item in audit["blocking_items"]}
    blocking_statuses = {item["id"]: item["status"] for item in audit["blocking_items"]}
    assert audit["completion_decision"] == "NOT_COMPLETE"
    assert audit["summary"]["local_wiring_passed"] is False
    assert "x0t_governance_execute_handoff_actionable" in blocking_ids
    assert blocking_statuses["x0t_governance_execute_handoff_actionable"] == "BLOCKING"


def test_completion_audit_require_complete_returns_two_when_blocked(tmp_path):
    root = _base_root(tmp_path)
    _write_production_ready(root)
    _write_json(
        root,
        ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json",
        {
            "completion_decision": "NOT_COMPLETE",
            "goal_can_be_marked_complete": False,
            "summary": {},
        },
    )

    output_json = tmp_path / "audit.json"
    exit_code = main([
        "--root",
        str(root),
        "--output-json",
        str(output_json),
        "--require-complete",
    ])

    assert exit_code == 2
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["completion_decision"] == "NOT_COMPLETE"
