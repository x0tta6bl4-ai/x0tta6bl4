"""Read-only current evidence rollup for integration-spine completion.

The rollup composes the retained external settlement, rollout provenance, and
semantic blocker queue artifacts into one final completion signal. It does not
create evidence, contact live systems, mutate runtime/chain state, or mark the
thread goal complete.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.x0t_governance_execute_readiness import (
    VALID_DECISIONS as GOVERNANCE_EXECUTE_READINESS_DECISIONS,
)


DEFAULT_EXTERNAL_SETTLEMENT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF = ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json"
DEFAULT_GOVERNANCE_EXECUTE_READINESS = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"
DEFAULT_GOVERNANCE_EXECUTE_HANDOFF = ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json"
DEFAULT_X0T_CONTRACT_READINESS = ".tmp/validation-shards/x0t-contract-readiness-current.json"
DEFAULT_X0T_BRIDGE_CONFIG = ".tmp/validation-shards/x0t-bridge-config-current.json"
DEFAULT_IMAGE_DIGESTS = ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"

EXTERNAL_SETTLEMENT_HANDOFF_DECISIONS = {
    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY",
    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
}
LEGACY_GOVERNANCE_EXECUTE_READINESS_DECISIONS = {
    "NOT_READY_NOT_QUEUED",
    "READY_FOR_OPERATOR_EXECUTE",
    "BLOCKED_VETOED",
    "UNKNOWN_STATE",
}
ACCEPTED_GOVERNANCE_EXECUTE_READINESS_DECISIONS = (
    GOVERNANCE_EXECUTE_READINESS_DECISIONS | LEGACY_GOVERNANCE_EXECUTE_READINESS_DECISIONS
)
GOVERNANCE_EXECUTE_HANDOFF_DECISIONS = {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}
X0T_BRIDGE_CONFIG_DECISIONS = {
    "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR",
    "X0T_BRIDGE_CONFIG_READY_TO_APPLY",
    "X0T_BRIDGE_CONFIG_READY",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary")
    return value if isinstance(value, dict) else {}


def _state(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("proposal_state", {})
    return value if isinstance(value, dict) else {}


def _status_ok(data: Optional[Dict[str, Any]]) -> bool:
    return (data or {}).get("status") == "VERIFIED HERE" and (data or {}).get("ok") is True


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _external_handoff_clear(data: Optional[Dict[str, Any]]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and str((data or {}).get("schema_version", "")).endswith("v6-repo-generated")
        and (data or {}).get("handoff_decision") in EXTERNAL_SETTLEMENT_HANDOFF_DECISIONS
        and (data or {}).get("goal_can_be_marked_complete") is False
        and (data or {}).get("mutates_chain") is False
        and (data or {}).get("runs_live_rpc") is False
        and (data or {}).get("submits_transaction") is False
        and summary.get("source_errors_total") == 0
        and summary.get("capture_preflight_available") is True
        and summary.get("operator_actions_total") == 6
        and summary.get("operator_commands_total") == 5
        and summary.get("operator_command_entrypoints_missing") == 0
        and summary.get("operator_command_surface_ready") is True
        and summary.get("operator_commands_with_shell_redirection_placeholders") == 0
        and summary.get("operator_command_shell_surface_ready") is True
        and summary.get("operator_sequence_ready") is True
    )


def _governance_readiness_clear(data: Optional[Dict[str, Any]]) -> bool:
    return (
        _status_ok(data)
        and (data or {}).get("schema_version") == "x0tta6bl4-x0t-governance-execute-readiness-v2"
        and (data or {}).get("decision") in ACCEPTED_GOVERNANCE_EXECUTE_READINESS_DECISIONS
        and (data or {}).get("goal_can_be_marked_complete") is False
        and (data or {}).get("mutates_chain") is False
        and (data or {}).get("submits_transaction") is False
    )


def _governance_handoff_clear(data: Optional[Dict[str, Any]]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and str((data or {}).get("schema_version", "")).endswith("v2-repo-generated")
        and (data or {}).get("handoff_decision") in GOVERNANCE_EXECUTE_HANDOFF_DECISIONS
        and (data or {}).get("handoff_actionable") is True
        and (data or {}).get("goal_can_be_marked_complete") is False
        and (data or {}).get("mutates_chain") is False
        and (data or {}).get("runs_live_rpc") is False
        and (data or {}).get("submits_transaction") is False
        and summary.get("source_errors_total") == 0
        and summary.get("operator_actions_total") == 5
        and summary.get("operator_commands_total") == 5
        and summary.get("operator_command_entrypoints_missing") == 0
        and summary.get("operator_command_surface_ready") is True
        and summary.get("operator_commands_with_shell_redirection_placeholders") == 0
        and summary.get("operator_command_shell_surface_ready") is True
        and summary.get("operator_sequence_ready") is True
    )


def _x0t_contract_surface_clear(
    contract_readiness: Optional[Dict[str, Any]],
    bridge_config: Optional[Dict[str, Any]],
) -> bool:
    contract_summary = _summary(contract_readiness)
    bridge_summary = _summary(bridge_config)
    return (
        _status_ok(contract_readiness)
        and (contract_readiness or {}).get("schema_version") == "x0tta6bl4-x0t-contract-readiness-v1"
        and (contract_readiness or {}).get("goal_can_be_marked_complete") is False
        and (contract_readiness or {}).get("mutates_chain") is False
        and (contract_readiness or {}).get("runs_live_rpc") is False
        and (contract_readiness or {}).get("submits_transaction") is False
        and contract_summary.get("build_env_ready") is True
        and contract_summary.get("contract_build_verification_ready") is True
        and contract_summary.get("base_sepolia_manifest_ready") is True
        and contract_summary.get("legacy_contract_surface_ready") is True
        and contract_summary.get("bridge_contract_source_ready") is True
        and _status_ok(bridge_config)
        and (bridge_config or {}).get("schema_version") == "x0tta6bl4-x0t-bridge-config-v1"
        and (bridge_config or {}).get("decision") in X0T_BRIDGE_CONFIG_DECISIONS
        and (bridge_config or {}).get("goal_can_be_marked_complete") is False
        and (bridge_config or {}).get("mutates_chain") is False
        and (bridge_config or {}).get("runs_live_rpc") is False
        and (bridge_config or {}).get("submits_transaction") is False
        and (bridge_config or {}).get("write", {}).get("approval_env") == "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
        and (bridge_config or {}).get("write", {}).get("approval_value_required")
        == "apply-bridge-address-base-sepolia"
        and isinstance(bridge_summary.get("bridge_address_input_ready"), bool)
        and isinstance(bridge_summary.get("configured_bridge_ready"), bool)
    )


def _x0t_contract_deployment_ready(
    contract_readiness: Optional[Dict[str, Any]],
    bridge_config: Optional[Dict[str, Any]],
) -> bool:
    contract_summary = _summary(contract_readiness)
    bridge_summary = _summary(bridge_config)
    return (
        _x0t_contract_surface_clear(contract_readiness, bridge_config)
        and (contract_readiness or {}).get("decision") == "CONTRACT_READINESS_CLEAR"
        and (contract_readiness or {}).get("contract_readiness_clear") is True
        and contract_summary.get("deployment_config_ready") is True
        and contract_summary.get("operator_configs_ready") is True
        and contract_summary.get("missing_inputs_total") == 0
        and not (contract_readiness or {}).get("missing_inputs", [])
        and (bridge_config or {}).get("decision") == "X0T_BRIDGE_CONFIG_READY"
        and (bridge_config or {}).get("bridge_config_ready") is True
        and bridge_summary.get("bridge_address_input_ready") is True
        and bridge_summary.get("configured_bridge_ready") is True
        and bridge_summary.get("missing_inputs_total") == 0
        and not (bridge_config or {}).get("missing_inputs", [])
    )


def _external_handoff_details(data: Optional[Dict[str, Any]], *, source_artifact: str) -> Dict[str, Any]:
    summary = _summary(data)
    return {
        "available": data is not None,
        "source_artifact": source_artifact,
        "decision": (data or {}).get("handoff_decision"),
        "ready_for_completion_rerun": (data or {}).get("ready_for_completion_rerun"),
        "capture_preflight_decision": summary.get("capture_preflight_decision"),
        "capture_inputs_ready": summary.get("capture_inputs_ready"),
        "missing_inputs": _dicts((data or {}).get("missing_inputs")),
        "operator_next_actions": _dicts((data or {}).get("operator_next_actions")),
        "operator_command_checks": _dicts((data or {}).get("operator_command_checks")),
    }


def _governance_handoff_details(data: Optional[Dict[str, Any]], *, source_artifact: str) -> Dict[str, Any]:
    summary = _summary(data)
    return {
        "available": data is not None,
        "source_artifact": source_artifact,
        "decision": (data or {}).get("handoff_decision"),
        "actionable": (data or {}).get("handoff_actionable"),
        "ready_for_operator_execute": (data or {}).get("ready_for_operator_execute"),
        "approval_value_required": summary.get("approval_value_required"),
        "missing_inputs": _dicts((data or {}).get("missing_inputs")),
        "operator_next_actions": _dicts((data or {}).get("operator_next_actions")),
        "operator_command_checks": _dicts((data or {}).get("operator_command_checks")),
    }


def _image_handoff_details(data: Optional[Dict[str, Any]], *, source_artifact: str) -> Dict[str, Any]:
    summary = _summary(data)
    return {
        "available": data is not None,
        "source_artifact": source_artifact,
        "decision": (data or {}).get("operator_handoff_decision"),
        "ready_for_completion_rerun": (data or {}).get("ready_for_completion_rerun"),
        "missing_inputs_total": summary.get("missing_inputs_total", 0),
        "operator_actions_total": summary.get("operator_actions_total", 0),
        "operator_commands_total": summary.get("operator_commands_total", 0),
        "operator_command_entrypoints_missing": summary.get("operator_command_entrypoints_missing", 0),
        "operator_command_surface_ready": summary.get("operator_command_surface_ready"),
        "operator_commands_with_shell_redirection_placeholders": summary.get(
            "operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "operator_command_shell_surface_ready": summary.get("operator_command_shell_surface_ready"),
        "missing_inputs": _dicts((data or {}).get("missing_inputs")),
        "operator_next_actions": _dicts((data or {}).get("operator_next_actions")),
        "operator_command_checks": _dicts((data or {}).get("operator_command_checks")),
    }


def _top_blocker_status_counts(blockers: List[Dict[str, Any]]) -> Dict[str, int]:
    statuses = {
        "blocking": 0,
        "operator_input_required": 0,
        "operator_approval_required": 0,
    }
    for item in blockers:
        status = item.get("status")
        if status == "OPERATOR_INPUT_REQUIRED":
            statuses["operator_input_required"] += 1
        elif status == "OPERATOR_APPROVAL_REQUIRED":
            statuses["operator_approval_required"] += 1
        elif status == "BLOCKING":
            statuses["blocking"] += 1
    return statuses


def _top_blockers(
    external: Optional[Dict[str, Any]],
    external_handoff: Optional[Dict[str, Any]],
    governance_readiness: Optional[Dict[str, Any]],
    governance_handoff: Optional[Dict[str, Any]],
    contract_readiness: Optional[Dict[str, Any]],
    bridge_config: Optional[Dict[str, Any]],
    image: Optional[Dict[str, Any]],
    semantic: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    external_summary = _summary(external)
    external_handoff_summary = _summary(external_handoff)
    governance_summary = _summary(governance_readiness)
    governance_handoff_summary = _summary(governance_handoff)
    contract_summary = _summary(contract_readiness)
    bridge_summary = _summary(bridge_config)
    image_summary = _summary(image)
    semantic_summary = _summary(semantic)
    external_ready = external_summary.get("x0t_external_settlement_ready") is True
    external_handoff_clear = _external_handoff_clear(external_handoff)
    external_handoff_ready = (
        external_handoff_clear and (external_handoff or {}).get("ready_for_completion_rerun") is True
    )
    governance_readiness_clear = _governance_readiness_clear(governance_readiness)
    governance_handoff_clear = _governance_handoff_clear(governance_handoff)
    governance_state = _state(governance_readiness)
    governance_executed = (
        governance_readiness_clear
        and governance_summary.get("proposal_executed") is True
        and governance_state.get("state_label") == "Executed"
    )
    contract_surface_clear = _x0t_contract_surface_clear(contract_readiness, bridge_config)
    contract_deployment_ready = _x0t_contract_deployment_ready(contract_readiness, bridge_config)

    if not external_ready:
        blockers.append(
            {
                "id": "external_settlement:001",
                "status": "OPERATOR_INPUT_REQUIRED" if external_handoff_clear else "BLOCKING",
                "reason": "missing retained real X0T settlement receipt verified against live Base RPC",
                "required_evidence": [
                    "real submitted X0T settlement transaction hash",
                    "successful mined receipt fields from Base RPC: status, block_number, block_hash, from_address, to_address",
                    "source commands and HTTPS explorer URL containing the exact transaction hash",
                    "retained .tmp/external-settlement-evidence/settlement-submit.json with status/evidence_status VERIFIED HERE",
                ],
            }
        )

    if not external_handoff_clear:
        blockers.append(
            {
                "id": "external_settlement:operator-handoff",
                "status": "BLOCKING",
                "reason": "external settlement operator handoff current shard is missing, stale, unsafe, or command-surface incomplete",
                "required_evidence": [
                    "repo-generated v6 external settlement operator handoff",
                    "0 source errors, 6 operator actions, 5 operator commands, and 0 missing command entrypoints",
                    "0 shell redirection placeholders in operator commands",
                ],
            }
        )
    elif external_ready and not external_handoff_ready:
        blockers.append(
            {
                "id": "external_settlement:operator-handoff-ready",
                "status": "BLOCKING",
                "reason": "external settlement evidence is ready only after the operator handoff reports ready_for_completion_rerun=true",
                "required_evidence": [
                    "external settlement capture inputs ready",
                    "retained settlement receipt, live RPC, production import, and completion gate all ready",
                    f"current handoff decision: {(external_handoff or {}).get('handoff_decision')}",
                    f"missing inputs total: {external_handoff_summary.get('missing_inputs_total', 0)}",
                ],
            }
        )

    if not governance_readiness_clear or not governance_handoff_clear:
        blockers.append(
            {
                "id": "x0t-governance:operator-handoff",
                "status": "BLOCKING",
                "reason": "X0T governance execute readiness/handoff current shards are missing, stale, unsafe, or command-surface incomplete",
                "required_evidence": [
                    "repo-generated governance execute-readiness v2 shard",
                    "repo-generated governance execute operator handoff v2 shard",
                    "0 handoff source errors, 5 operator actions, 5 operator commands, and 0 shell placeholders",
                ],
            }
        )
    elif not governance_executed:
        blockers.append(
            {
                "id": "x0t-governance:proposal-execution",
                "status": "OPERATOR_APPROVAL_REQUIRED"
                if (governance_handoff or {}).get("ready_for_operator_execute") is True
                else "BLOCKING",
                "reason": "X0T governance proposal 1 is not yet retained as Executed final-state evidence",
                "required_evidence": [
                    "execute-readiness reports ALREADY_EXECUTED or final state Executed",
                    "operator executes only after explicit approval and readiness",
                    "retained status-1 receipt plus post-receipt Executed state",
                    f"current handoff decision: {(governance_handoff or {}).get('handoff_decision')}",
                    f"next executable after UTC: {governance_summary.get('next_executable_after_utc', '')}",
                ],
            }
        )

    if not contract_deployment_ready:
        blockers.append(
            {
                "id": "x0t-contract:deployment-config",
                "status": "OPERATOR_INPUT_REQUIRED" if contract_surface_clear else "BLOCKING",
                "reason": "X0T contract/deployment config is missing a deployed bridge contract address or has not been applied to operator config",
                "required_evidence": [
                    "x0t-contract-readiness current shard reports CONTRACT_READINESS_CLEAR",
                    "x0t-bridge-config current shard reports X0T_BRIDGE_CONFIG_READY",
                    "bridge address is a deployed Base Sepolia bridge contract, not X0TToken or MeshGovernance",
                    f"current contract decision: {(contract_readiness or {}).get('decision')}",
                    f"current bridge decision: {(bridge_config or {}).get('decision')}",
                    f"contract missing inputs total: {contract_summary.get('missing_inputs_total', 0)}",
                    f"bridge missing inputs total: {bridge_summary.get('missing_inputs_total', 0)}",
                ],
            }
        )

    if image_summary.get("can_close_image_digests_blocker") is not True:
        blockers.append(
            {
                "id": "live-rollout:image-digests",
                "status": "OPERATOR_INPUT_REQUIRED",
                "reason": "runtime/deploy image references are tag-based instead of digest-pinned and provenance artifacts are missing",
                "required_evidence": [
                    "digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image",
                    "retained per-image cosign/SLSA provenance artifacts for current deployed image digests",
                    "rerun verify_deploy_image_provenance_gate.py and collect_live_rollout_evidence_bundle.py after replacing raw evidence",
                    f"current handoff decision: {(image or {}).get('operator_handoff_decision')}",
                    f"missing inputs total: {image_summary.get('missing_inputs_total', 0)}",
                ],
            }
        )

    if semantic_summary.get("blocking_items_total", 0) != 0 or (semantic or {}).get("goal_can_be_marked_complete") is not True:
        blockers.append(
            {
                "id": "integration-spine:semantic-production-readiness",
                "status": "OPERATOR_INPUT_REQUIRED"
                if semantic_summary.get("source_errors_total", 0) == 0
                else "BLOCKING",
                "reason": "semantic blocker queue still reports production-closeout blockers across identity/policy/safe-actuator/settlement layers",
                "required_evidence": [
                    "external X0T settlement receipt verified against live RPC",
                    "all listed raw evidence files replaced with production-grade retained evidence",
                    "integration-spine objective coverage audit returns COMPLETE",
                ],
            }
        )

    return blockers


@dataclass(frozen=True)
class RollupInputs:
    root: Path
    external_settlement_path: Path
    image_digests_path: Path
    semantic_queue_path: Path
    external_settlement_display: str = DEFAULT_EXTERNAL_SETTLEMENT
    image_digests_display: str = DEFAULT_IMAGE_DIGESTS
    semantic_queue_display: str = DEFAULT_SEMANTIC_QUEUE
    external_settlement_handoff_path: Optional[Path] = None
    governance_execute_readiness_path: Optional[Path] = None
    governance_execute_handoff_path: Optional[Path] = None
    external_settlement_handoff_display: str = DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF
    governance_execute_readiness_display: str = DEFAULT_GOVERNANCE_EXECUTE_READINESS
    governance_execute_handoff_display: str = DEFAULT_GOVERNANCE_EXECUTE_HANDOFF
    x0t_contract_readiness_path: Optional[Path] = None
    x0t_bridge_config_path: Optional[Path] = None
    x0t_contract_readiness_display: str = DEFAULT_X0T_CONTRACT_READINESS
    x0t_bridge_config_display: str = DEFAULT_X0T_BRIDGE_CONFIG


def build_rollup(inputs: RollupInputs) -> Dict[str, Any]:
    external = _read_json(inputs.external_settlement_path)
    external_handoff_path = inputs.external_settlement_handoff_path or inputs.root / inputs.external_settlement_handoff_display
    governance_readiness_path = inputs.governance_execute_readiness_path or inputs.root / inputs.governance_execute_readiness_display
    governance_handoff_path = inputs.governance_execute_handoff_path or inputs.root / inputs.governance_execute_handoff_display
    contract_readiness_path = inputs.x0t_contract_readiness_path or inputs.root / inputs.x0t_contract_readiness_display
    bridge_config_path = inputs.x0t_bridge_config_path or inputs.root / inputs.x0t_bridge_config_display
    external_handoff = _read_json(external_handoff_path)
    governance_readiness = _read_json(governance_readiness_path)
    governance_handoff = _read_json(governance_handoff_path)
    contract_readiness = _read_json(contract_readiness_path)
    bridge_config = _read_json(bridge_config_path)
    image = _read_json(inputs.image_digests_path)
    semantic = _read_json(inputs.semantic_queue_path)
    source_errors: List[str] = []
    if external is None:
        source_errors.append(f"missing or unreadable external settlement rollup: {inputs.external_settlement_display}")
    if external_handoff is None:
        source_errors.append(
            f"missing or unreadable external settlement operator handoff rollup: {inputs.external_settlement_handoff_display}"
        )
    if governance_readiness is None:
        source_errors.append(
            f"missing or unreadable X0T governance execute-readiness rollup: {inputs.governance_execute_readiness_display}"
        )
    if governance_handoff is None:
        source_errors.append(
            f"missing or unreadable X0T governance execute operator handoff rollup: {inputs.governance_execute_handoff_display}"
        )
    if contract_readiness is None:
        source_errors.append(
            f"missing or unreadable X0T contract readiness rollup: {inputs.x0t_contract_readiness_display}"
        )
    if bridge_config is None:
        source_errors.append(
            f"missing or unreadable X0T bridge config rollup: {inputs.x0t_bridge_config_display}"
        )
    if image is None:
        source_errors.append(f"missing or unreadable live rollout image digest rollup: {inputs.image_digests_display}")
    if semantic is None:
        source_errors.append(f"missing or unreadable semantic blocker queue: {inputs.semantic_queue_display}")

    external_summary = _summary(external)
    external_handoff_summary = _summary(external_handoff)
    governance_summary = _summary(governance_readiness)
    governance_handoff_summary = _summary(governance_handoff)
    contract_summary = _summary(contract_readiness)
    bridge_summary = _summary(bridge_config)
    governance_state = _state(governance_readiness)
    image_summary = _summary(image)
    semantic_summary = _summary(semantic)
    external_handoff_clear = _external_handoff_clear(external_handoff)
    governance_readiness_clear = _governance_readiness_clear(governance_readiness)
    governance_handoff_clear = _governance_handoff_clear(governance_handoff)
    governance_executed = (
        governance_readiness_clear
        and governance_summary.get("proposal_executed") is True
        and governance_state.get("state_label") == "Executed"
    )
    contract_surface_clear = _x0t_contract_surface_clear(contract_readiness, bridge_config)
    contract_deployment_ready = _x0t_contract_deployment_ready(contract_readiness, bridge_config)
    blockers = _top_blockers(
        external,
        external_handoff,
        governance_readiness,
        governance_handoff,
        contract_readiness,
        bridge_config,
        image,
        semantic,
    )
    top_blocker_statuses = _top_blocker_status_counts(blockers)
    complete = not source_errors and not blockers

    return {
        "schema_version": "x0tta6bl4-integration-spine-current-evidence-rollup-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "completion_decision": "COMPLETE" if complete else "NOT_COMPLETE",
        "goal_can_be_marked_complete": complete,
        "claim_boundary": (
            "Read-only rollup of retained local evidence artifacts. It does not create "
            "production evidence, mutate runtime/chain state, or upgrade templates/mocks "
            "into verified evidence."
        ),
        "source_artifacts": {
            "external_settlement": inputs.external_settlement_display,
            "external_settlement_operator_handoff": inputs.external_settlement_handoff_display,
            "x0t_governance_execute_readiness": inputs.governance_execute_readiness_display,
            "x0t_governance_execute_handoff": inputs.governance_execute_handoff_display,
            "x0t_contract_readiness": inputs.x0t_contract_readiness_display,
            "x0t_bridge_config": inputs.x0t_bridge_config_display,
            "live_rollout_image_digests": inputs.image_digests_display,
            "semantic_blocker_queue": inputs.semantic_queue_display,
        },
        "source_errors": source_errors,
        "operator_handoffs": {
            "source_artifact": "current_evidence_rollup",
            "source_available": external_handoff is not None and governance_handoff is not None and image is not None,
            "external_settlement": _external_handoff_details(
                external_handoff,
                source_artifact=inputs.external_settlement_handoff_display,
            ),
            "x0t_governance_execute": _governance_handoff_details(
                governance_handoff,
                source_artifact=inputs.governance_execute_handoff_display,
            ),
            "live_rollout_image_digests": _image_handoff_details(
                image,
                source_artifact=inputs.image_digests_display,
            ),
        },
        "top_blockers": blockers,
        "not_verified_yet": []
        if complete
        else [
            "real retained external X0T settlement receipt verified against live RPC",
            "X0T contract deployment config has a deployed bridge address",
            "digest-pinned live rollout runtime images with retained provenance artifacts",
            "semantic production blocker queue complete",
        ],
        "summary": {
            "source_errors_total": len(source_errors),
            "top_blockers_total": len(blockers),
            "top_blockers_blocking": top_blocker_statuses["blocking"],
            "top_blockers_operator_input_required": top_blocker_statuses["operator_input_required"],
            "top_blockers_operator_approval_required": top_blocker_statuses["operator_approval_required"],
            "external_settlement_decision": (external or {}).get("decision"),
            "external_settlement_ready": external_summary.get("x0t_external_settlement_ready", False),
            "external_settlement_expected_evidence_file_exists": external_summary.get("expected_evidence_file_exists", False),
            "external_settlement_fake_prevention_enforced": external_summary.get(
                "fake_external_settlement_prevention_enforced",
                False,
            ),
            "external_settlement_handoff_available": external_handoff is not None,
            "external_settlement_handoff_clear": external_handoff_clear,
            "external_settlement_handoff_decision": (external_handoff or {}).get("handoff_decision"),
            "external_settlement_handoff_ready_for_completion_rerun": (external_handoff or {}).get(
                "ready_for_completion_rerun"
            ),
            "external_settlement_capture_preflight_decision": external_handoff_summary.get(
                "capture_preflight_decision"
            ),
            "external_settlement_capture_inputs_ready": external_handoff_summary.get("capture_inputs_ready"),
            "external_settlement_handoff_missing_inputs_total": external_handoff_summary.get(
                "missing_inputs_total",
                0,
            ),
            "external_settlement_handoff_operator_actions_total": external_handoff_summary.get(
                "operator_actions_total",
                0,
            ),
            "external_settlement_handoff_operator_commands_total": external_handoff_summary.get(
                "operator_commands_total",
                0,
            ),
            "external_settlement_handoff_operator_command_entrypoints_missing": external_handoff_summary.get(
                "operator_command_entrypoints_missing",
                0,
            ),
            "external_settlement_handoff_operator_command_surface_ready": external_handoff_summary.get(
                "operator_command_surface_ready"
            ),
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": external_handoff_summary.get(
                "operator_commands_with_shell_redirection_placeholders",
                0,
            ),
            "external_settlement_handoff_operator_command_shell_surface_ready": external_handoff_summary.get(
                "operator_command_shell_surface_ready"
            ),
            "external_settlement_handoff_operator_sequence_ready": external_handoff_summary.get(
                "operator_sequence_ready"
            ),
            "x0t_governance_execute_readiness_available": governance_readiness is not None,
            "x0t_governance_execute_readiness_clear": governance_readiness_clear,
            "x0t_governance_execute_decision": (governance_readiness or {}).get("decision"),
            "x0t_governance_execute_ready_now": governance_summary.get("execute_ready_now"),
            "x0t_governance_proposal_executed": governance_executed,
            "x0t_governance_state_label": governance_state.get("state_label"),
            "x0t_governance_next_executable_after_utc": governance_summary.get("next_executable_after_utc"),
            "x0t_governance_seconds_until_earliest_execution_by_block_time": governance_handoff_summary.get(
                "seconds_until_earliest_execution_by_block_time"
            ),
            "x0t_governance_execute_handoff_available": governance_handoff is not None,
            "x0t_governance_execute_handoff_clear": governance_handoff_clear,
            "x0t_governance_execute_handoff_decision": (governance_handoff or {}).get("handoff_decision"),
            "x0t_governance_execute_handoff_actionable": (governance_handoff or {}).get("handoff_actionable"),
            "x0t_governance_ready_for_operator_execute": (governance_handoff or {}).get(
                "ready_for_operator_execute"
            ),
            "x0t_governance_handoff_missing_inputs_total": governance_handoff_summary.get(
                "missing_inputs_total",
                0,
            ),
            "x0t_governance_handoff_operator_actions_total": governance_handoff_summary.get(
                "operator_actions_total",
                0,
            ),
            "x0t_governance_handoff_operator_commands_total": governance_handoff_summary.get(
                "operator_commands_total",
                0,
            ),
            "x0t_governance_handoff_operator_command_entrypoints_missing": governance_handoff_summary.get(
                "operator_command_entrypoints_missing",
                0,
            ),
            "x0t_governance_handoff_operator_command_surface_ready": governance_handoff_summary.get(
                "operator_command_surface_ready"
            ),
            "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": governance_handoff_summary.get(
                "operator_commands_with_shell_redirection_placeholders",
                0,
            ),
            "x0t_governance_handoff_operator_command_shell_surface_ready": governance_handoff_summary.get(
                "operator_command_shell_surface_ready"
            ),
            "x0t_governance_handoff_operator_sequence_ready": governance_handoff_summary.get(
                "operator_sequence_ready"
            ),
            "x0t_contract_readiness_available": contract_readiness is not None,
            "x0t_contract_surface_clear": contract_surface_clear,
            "x0t_contract_readiness_decision": (contract_readiness or {}).get("decision"),
            "x0t_contract_readiness_clear": (contract_readiness or {}).get("contract_readiness_clear"),
            "x0t_contract_build_env_ready": contract_summary.get("build_env_ready"),
            "x0t_contract_build_verification_ready": contract_summary.get("contract_build_verification_ready"),
            "x0t_contract_bridge_source_ready": contract_summary.get("bridge_contract_source_ready"),
            "x0t_contract_deployment_config_ready": contract_summary.get("deployment_config_ready"),
            "x0t_contract_operator_configs_ready": contract_summary.get("operator_configs_ready"),
            "x0t_contract_missing_inputs_total": contract_summary.get("missing_inputs_total", 0),
            "x0t_bridge_config_available": bridge_config is not None,
            "x0t_bridge_config_decision": (bridge_config or {}).get("decision"),
            "x0t_bridge_config_ready": (bridge_config or {}).get("bridge_config_ready"),
            "x0t_bridge_address_input_ready": bridge_summary.get("bridge_address_input_ready"),
            "x0t_bridge_configured_bridge_ready": bridge_summary.get("configured_bridge_ready"),
            "x0t_bridge_missing_inputs_total": bridge_summary.get("missing_inputs_total", 0),
            "x0t_contract_deployment_ready": contract_deployment_ready,
            "image_digests_decision": (image or {}).get("decision"),
            "image_digests_operator_handoff_decision": (image or {}).get("operator_handoff_decision"),
            "image_digests_ready_for_completion_rerun": (image or {}).get("ready_for_completion_rerun"),
            "image_digests_can_close": image_summary.get("can_close_image_digests_blocker", False),
            "image_digests_deploy_images_total": image_summary.get("raw_deploy_images_total", 0),
            "image_digests_deploy_images_digest_pinned": image_summary.get("raw_deploy_images_digest_pinned", 0),
            "image_digests_missing_inputs_total": image_summary.get("missing_inputs_total", 0),
            "image_digests_operator_actions_total": image_summary.get("operator_actions_total", 0),
            "image_digests_operator_commands_total": image_summary.get("operator_commands_total", 0),
            "image_digests_operator_command_entrypoints_missing": image_summary.get(
                "operator_command_entrypoints_missing",
                0,
            ),
            "image_digests_operator_command_surface_ready": image_summary.get("operator_command_surface_ready"),
            "image_digests_operator_commands_with_shell_redirection_placeholders": image_summary.get(
                "operator_commands_with_shell_redirection_placeholders",
                0,
            ),
            "image_digests_operator_command_shell_surface_ready": image_summary.get(
                "operator_command_shell_surface_ready"
            ),
            "semantic_goal_can_be_marked_complete": (semantic or {}).get("goal_can_be_marked_complete", False),
            "semantic_blocking_items_total": semantic_summary.get("blocking_items_total", 0),
            "semantic_preflight_errors_total": semantic_summary.get("semantic_preflight_errors_total", 0),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine current evidence rollup")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--external-settlement", default=DEFAULT_EXTERNAL_SETTLEMENT)
    parser.add_argument("--external-settlement-handoff", default=DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF)
    parser.add_argument("--governance-execute-readiness", default=DEFAULT_GOVERNANCE_EXECUTE_READINESS)
    parser.add_argument("--governance-execute-handoff", default=DEFAULT_GOVERNANCE_EXECUTE_HANDOFF)
    parser.add_argument("--x0t-contract-readiness", default=DEFAULT_X0T_CONTRACT_READINESS)
    parser.add_argument("--x0t-bridge-config", default=DEFAULT_X0T_BRIDGE_CONFIG)
    parser.add_argument("--image-digests", default=DEFAULT_IMAGE_DIGESTS)
    parser.add_argument("--semantic-queue", default=DEFAULT_SEMANTIC_QUEUE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-complete", action="store_true", help="Return 2 unless the rollup is complete.")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Alias for --require-complete and also return 2 when any blocker remains.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_rollup(
        RollupInputs(
            root=root,
            external_settlement_path=_resolve(root, args.external_settlement),
            image_digests_path=_resolve(root, args.image_digests),
            semantic_queue_path=_resolve(root, args.semantic_queue),
            external_settlement_display=args.external_settlement,
            image_digests_display=args.image_digests,
            semantic_queue_display=args.semantic_queue,
            external_settlement_handoff_path=_resolve(root, args.external_settlement_handoff),
            governance_execute_readiness_path=_resolve(root, args.governance_execute_readiness),
            governance_execute_handoff_path=_resolve(root, args.governance_execute_handoff),
            x0t_contract_readiness_path=_resolve(root, args.x0t_contract_readiness),
            x0t_bridge_config_path=_resolve(root, args.x0t_bridge_config),
            external_settlement_handoff_display=args.external_settlement_handoff,
            governance_execute_readiness_display=args.governance_execute_readiness,
            governance_execute_handoff_display=args.governance_execute_handoff,
            x0t_contract_readiness_display=args.x0t_contract_readiness,
            x0t_bridge_config_display=args.x0t_bridge_config,
        )
    )
    write_json(_resolve(root, args.output_json), report)
    print(
        json.dumps(
            {
                "completion_decision": report["completion_decision"],
                "goal_can_be_marked_complete": report["goal_can_be_marked_complete"],
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_complete and report["completion_decision"] != "COMPLETE":
        return 2
    if args.require_ready and (report.get("completion_decision") != "COMPLETE" or not report.get("x0t_contract_surface_clear") is True):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
