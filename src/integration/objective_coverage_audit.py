"""Repo-backed objective coverage audit for integration-spine production closeout.

This report maps the user's objective to concrete artifacts. It replaces the
old source-restored coverage shard with a read-only audit generated from the
current repo artifacts. It does not collect evidence, contact live systems,
stage files, mutate runtime, submit transactions, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS
from src.integration.x0t_governance_execute_readiness import (
    VALID_DECISIONS as GOVERNANCE_EXECUTE_READINESS_DECISIONS,
)


OBJECTIVE = (
    "Connect all x0tta6bl4 layers and components into one system through a "
    "single identity, event bus, policy engine, safe actuator, and "
    "settlement/reward loop, then bring that system to production."
)

DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"

DEFAULT_CODE_WIRING = ".tmp/validation-shards/integration-spine-code-wiring-current.json"
DEFAULT_PRODUCTION_INPUT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_PRODUCTION_INTAKE = ".tmp/validation-shards/integration-spine-production-evidence-intake-current.json"
DEFAULT_SOURCE_CANDIDATES = ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
DEFAULT_RAW_INVENTORY = ".tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json"
DEFAULT_SEMANTIC_QUEUE = ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json"
DEFAULT_REQUIRED_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_ROLLUP_CONTRACT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_CLOSEOUT_REVIEW = ".tmp/validation-shards/integration-spine-production-closeout-review-current.json"
DEFAULT_CLOSURE_PREFLIGHT = ".tmp/validation-shards/integration-spine-production-closure-preflight-current.json"
DEFAULT_FINAL_REVIEW = ".tmp/validation-shards/integration-spine-production-final-review-current.json"
DEFAULT_COMPLETION_AUDIT = ".tmp/validation-shards/integration-spine-completion-audit-current.json"
DEFAULT_PRODUCTION_GAP_INDEX = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_CURRENT_ROLLUP = ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
DEFAULT_EXTERNAL_SETTLEMENT = ".tmp/validation-shards/x0t-external-settlement-current-blocker-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF = ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json"
DEFAULT_GOVERNANCE_EXECUTE_READINESS = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"
DEFAULT_GOVERNANCE_EXECUTE_HANDOFF = ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json"
DEFAULT_IMAGE_DIGESTS = ".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json"
DEFAULT_COLLECTION_CHECKLIST = ".tmp/validation-shards/integration-spine-collection-checklist-progress-current.json"
DEFAULT_OPERATOR_PACKET_INDEX = ".tmp/validation-shards/integration-spine-operator-evidence-packet-index-current.json"
DEFAULT_RAW_OPERATOR_PACKET_INDEX = ".tmp/validation-shards/production-raw-evidence-operator-packet-index-current.json"
DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT = ".tmp/validation-shards/production-grade-goal-audit-current.json"
DEFAULT_CROSS_PLANE_PROOF_GATE = ".tmp/validation-shards/cross-plane-proof-gate-current.json"

OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "settlement_finality",
    "dpi_bypass",
)
CROSS_PLANE_PROOF_GATE_SCHEMA = "x0tta6bl4.cross_plane_proof_gate.v1"
CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION = "CROSS_PLANE_CLAIMS_ALLOWED"

EXTERNAL_SETTLEMENT_HANDOFF_DECISIONS = {
    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_READY",
    "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR",
}
EXTERNAL_SETTLEMENT_HANDOFF_CAPTURE_PREFLIGHT_DECISIONS = {
    "CAPTURE_INPUTS_READY",
    "CAPTURE_INPUTS_BLOCKED",
}
GOVERNANCE_EXECUTE_HANDOFF_DECISIONS = {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}


REQUIRED_GOAL_AUDIT_ROWS = {
    "goal_audit:single_identity",
    "goal_audit:event_bus",
    "goal_audit:runtime_contract",
    "goal_audit:policy_engine",
    "goal_audit:safe_actuator",
    "goal_audit:settlement_reward_loop",
    "goal_audit:mapek_recovery_router",
    "goal_audit:paid_client_entitlement_router",
    "goal_audit:external_settlement_export",
    "goal_audit:safe_rollout_rollback_envelope",
    "goal_audit:observability_sla_truth",
    "goal_audit:production_evidence_intake",
    "goal_audit:production_input_pipeline",
    "goal_audit:production_evidence_source_hygiene",
    "goal_audit:production_evidence_import",
    "goal_audit:production_raw_evidence_operator_packet",
    "goal_audit:external_settlement_submitted",
    "goal_audit:broad_production_hardening",
    "goal_audit:cross_plane_proof_gate",
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


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _production_grade_next_actions(prod_grade: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for item in _dicts((prod_grade or {}).get("next_actions")):
        action = dict(item)
        action.setdefault("source_artifact", DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT)
        action["source"] = "production_grade_goal_audit"
        actions.append(action)
    return actions


def _strings(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _value(data: Optional[Dict[str, Any]], dotted: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _cross_plane_proof_gate_command() -> str:
    claims = " ".join(f"--claim {claim_id}" for claim_id in OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS)
    return (
        f"python3 scripts/ops/run_cross_plane_proof_gate.py {claims} --json --require-allowed "
        f"--output-json {DEFAULT_CROSS_PLANE_PROOF_GATE}"
    )


def _cross_plane_proof_gate_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    claim_ids: List[str] = []
    for result in _dicts((data or {}).get("claim_results")):
        claim_id = result.get("claim_id")
        if isinstance(claim_id, str) and claim_id:
            claim_ids.append(claim_id)
    return sorted(set(claim_ids))


def _cross_plane_proof_gate_missing_claim_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    return sorted(set(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS) - set(_cross_plane_proof_gate_claim_ids(data)))


def _cross_plane_proof_gate_blocker_ids(data: Optional[Dict[str, Any]]) -> List[str]:
    blockers: List[str] = []
    if not data:
        return ["cross_plane_proof_gate_missing"]
    if data.get("schema") != CROSS_PLANE_PROOF_GATE_SCHEMA:
        blockers.append("cross_plane_proof_gate_schema_invalid")
    if data.get("decision") != CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION:
        blockers.append("cross_plane_proof_gate_not_allowed")
    if data.get("allowed") is not True:
        blockers.append("cross_plane_proof_gate_blocked")
    for claim_id in _cross_plane_proof_gate_missing_claim_ids(data):
        blockers.append(f"cross_plane_proof_gate_missing_claim:{claim_id}")
    for result in _dicts(data.get("claim_results")):
        claim_id = str(result.get("claim_id") or "unknown_claim")
        if result.get("allowed") is True:
            continue
        blockers.append(f"claim_blocked:{claim_id}")
        blockers.extend(str(item) for item in result.get("blockers") or [] if item)
    return sorted(set(blockers))


def _cross_plane_proof_gate_local_ready(data: Optional[Dict[str, Any]]) -> bool:
    return (
        isinstance(data, dict)
        and data.get("schema") == CROSS_PLANE_PROOF_GATE_SCHEMA
        and not _cross_plane_proof_gate_missing_claim_ids(data)
    )


def _cross_plane_proof_gate_allowed(data: Optional[Dict[str, Any]]) -> bool:
    if not _cross_plane_proof_gate_local_ready(data):
        return False
    required_claim_ids = set(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS)
    claim_results = {
        str(result.get("claim_id")): result
        for result in _dicts((data or {}).get("claim_results"))
        if isinstance(result.get("claim_id"), str)
    }
    return (
        data.get("decision") == CROSS_PLANE_PROOF_GATE_ALLOWED_DECISION
        and data.get("allowed") is True
        and all(claim_results[claim_id].get("allowed") is True for claim_id in required_claim_ids)
    )


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    path: str


@dataclass(frozen=True)
class RowSpec:
    row_id: str
    requirement: str
    artifact_keys: List[str]
    commands: List[str]
    local_ready: bool
    production_ready: bool
    evidence: Dict[str, Any]
    blocking_gaps: List[str]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_artifacts(root: Path, specs: Iterable[ArtifactSpec]) -> Dict[str, Dict[str, Any]]:
    loaded: Dict[str, Dict[str, Any]] = {}
    for spec in specs:
        path = _resolve(root, spec.path)
        data = _read_json(path)
        loaded[spec.key] = {
            "path": spec.path,
            "exists": path.exists(),
            "loaded": data is not None,
            "error": "" if data is not None else f"missing or unreadable artifact: {spec.path}",
            "data": data,
        }
    return loaded


def _artifact_loads(artifacts: Dict[str, Dict[str, Any]], keys: Iterable[str]) -> List[Dict[str, Any]]:
    loads: List[Dict[str, Any]] = []
    for key in keys:
        artifact = artifacts.get(key, {})
        loads.append(
            {
                "path": artifact.get("path", key),
                "exists": artifact.get("exists") is True,
                "loaded": artifact.get("loaded") is True,
                "error": artifact.get("error", ""),
            }
        )
    return loads


def _all_loaded(artifacts: Dict[str, Dict[str, Any]], keys: Iterable[str]) -> bool:
    return all(artifacts.get(key, {}).get("loaded") is True for key in keys)


def _row_status(local_ready: bool, production_ready: bool) -> str:
    if local_ready and production_ready:
        return "VERIFIED_READY"
    if local_ready:
        return "VERIFIED_LOCAL_PRODUCTION_GAP"
    return "BLOCKED"


def _governance_execute_next_action_status(
    *,
    proposal_executed: bool,
    ready_for_operator_execute: bool,
) -> str:
    if proposal_executed:
        return "DONE"
    if ready_for_operator_execute:
        return "OPERATOR_APPROVAL_REQUIRED"
    return "BLOCKING"


def _external_settlement_next_action_status(
    *,
    external_ready: bool,
    handoff_local_ready: bool,
    ready_for_completion_rerun: bool,
) -> str:
    if external_ready:
        return "DONE"
    if handoff_local_ready and not ready_for_completion_rerun:
        return "OPERATOR_INPUT_REQUIRED"
    return "BLOCKING"


def _raw_evidence_next_action_status(
    *,
    raw_ready: bool,
    raw_operator_packet_local_handoff_complete: bool,
    raw_operator_packet_replacement_required: int,
    raw_operator_packet_readiness_decision: Any,
) -> str:
    if raw_ready:
        return "DONE"
    if (
        raw_operator_packet_local_handoff_complete
        and raw_operator_packet_replacement_required > 0
        and raw_operator_packet_readiness_decision == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    ):
        return "OPERATOR_INPUT_REQUIRED"
    return "BLOCKING"


def _blocking_gaps(*gaps: Any) -> List[str]:
    result: List[str] = []
    for gap in gaps:
        if isinstance(gap, str) and gap:
            result.append(gap)
        elif isinstance(gap, list):
            result.extend(str(item) for item in gap if item)
    return result


def _as_row(artifacts: Dict[str, Dict[str, Any]], spec: RowSpec) -> Dict[str, Any]:
    return {
        "id": spec.row_id,
        "requirement": spec.requirement,
        "status": _row_status(spec.local_ready, spec.production_ready),
        "local_ready": spec.local_ready,
        "production_ready": spec.production_ready,
        "blocking_gaps": spec.blocking_gaps,
        "artifact_paths": [str(artifacts.get(key, {}).get("path", key)) for key in spec.artifact_keys],
        "artifact_loads": _artifact_loads(artifacts, spec.artifact_keys),
        "commands": spec.commands,
        "evidence": spec.evidence,
    }


def _source_status(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "MISSING"
    if data.get("status") == "VERIFIED HERE" and data.get("ok") is True:
        return "VERIFIED HERE"
    return str(data.get("status", "UNKNOWN"))


def _external_settlement_handoff_source_clear(data: Optional[Dict[str, Any]]) -> bool:
    summary = _summary(data)
    return (
        _source_status(data) == "VERIFIED HERE"
        and str((data or {}).get("schema_version", "")).endswith("v6-repo-generated")
        and (data or {}).get("handoff_decision") in EXTERNAL_SETTLEMENT_HANDOFF_DECISIONS
        and (data or {}).get("goal_can_be_marked_complete") is False
        and (data or {}).get("mutates_chain") is False
        and (data or {}).get("runs_live_rpc") is False
        and (data or {}).get("submits_transaction") is False
        and summary.get("source_errors_total") == 0
        and summary.get("capture_preflight_available") is True
        and summary.get("capture_preflight_decision") in EXTERNAL_SETTLEMENT_HANDOFF_CAPTURE_PREFLIGHT_DECISIONS
        and summary.get("operator_actions_total") == 6
        and summary.get("operator_commands_total") == 5
        and summary.get("operator_command_entrypoints_missing") == 0
        and summary.get("operator_command_surface_ready") is True
        and summary.get("operator_commands_with_shell_redirection_placeholders") == 0
        and summary.get("operator_command_shell_surface_ready") is True
        and summary.get("operator_sequence_ready") is True
    )


def _external_settlement_handoff_local_ready(
    data: Optional[Dict[str, Any]],
    gap_summary: Dict[str, Any],
) -> bool:
    return (
        _external_settlement_handoff_source_clear(data)
        and gap_summary.get("external_settlement_handoff_clear") is True
    )


def _governance_execute_handoff_source_clear(
    handoff: Optional[Dict[str, Any]],
    readiness: Optional[Dict[str, Any]],
) -> bool:
    summary = _summary(handoff)
    approval = (handoff or {}).get("approval_boundary", {})
    if not isinstance(approval, dict):
        approval = {}
    readiness_decision = (readiness or {}).get("decision")
    return (
        _source_status(handoff) == "VERIFIED HERE"
        and str((handoff or {}).get("schema_version", "")).endswith("v2-repo-generated")
        and (handoff or {}).get("handoff_decision") in GOVERNANCE_EXECUTE_HANDOFF_DECISIONS
        and (handoff or {}).get("handoff_actionable") is True
        and (handoff or {}).get("goal_can_be_marked_complete") is False
        and (handoff or {}).get("mutates_chain") is False
        and (handoff or {}).get("runs_live_rpc") is False
        and (handoff or {}).get("submits_transaction") is False
        and summary.get("source_errors_total") == 0
        and (
            readiness_decision is None
            or (
                readiness_decision in GOVERNANCE_EXECUTE_READINESS_DECISIONS
                and summary.get("readiness_decision") == readiness_decision
            )
        )
        and approval.get("approval_env") == "X0T_EXECUTE_PROPOSAL_APPROVAL"
        and approval.get("expected_value") == "execute-proposal-1-base-sepolia"
        and approval.get("can_submit_without_operator_approval") is False
        and summary.get("operator_actions_total") == 5
        and summary.get("operator_commands_total") == 5
        and summary.get("operator_command_entrypoints_missing") == 0
        and summary.get("operator_command_surface_ready") is True
        and summary.get("operator_commands_with_shell_redirection_placeholders") == 0
        and summary.get("operator_command_shell_surface_ready") is True
        and summary.get("operator_sequence_ready") is True
    )


def _governance_execute_handoff_local_ready(
    handoff: Optional[Dict[str, Any]],
    readiness: Optional[Dict[str, Any]],
    gap_summary: Dict[str, Any],
) -> bool:
    return (
        _governance_execute_handoff_source_clear(handoff, readiness)
        and gap_summary.get("x0t_governance_execute_handoff_clear") is True
    )


def _governance_proposal_executed(readiness: Optional[Dict[str, Any]]) -> bool:
    proposal_state = (readiness or {}).get("proposal_state", {})
    if not isinstance(proposal_state, dict):
        proposal_state = {}
    return (
        (readiness or {}).get("decision") == "ALREADY_EXECUTED"
        and proposal_state.get("executed") is True
        and proposal_state.get("vetoed") is False
    )


def _rows(artifacts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    code = artifacts["code_wiring"]["data"]
    pipeline = artifacts["production_input_pipeline"]["data"]
    return_acceptance = artifacts["return_acceptance"]["data"]
    intake = artifacts["production_intake"]["data"]
    source_candidates = artifacts["source_candidates"]["data"]
    raw_inventory = artifacts["raw_inventory"]["data"]
    semantic = artifacts["semantic_queue"]["data"]
    consistency = artifacts["required_consistency"]["data"]
    rollup_contract = artifacts["rollup_contract"]["data"]
    closeout = artifacts["closeout_review"]["data"]
    preflight = artifacts["closure_preflight"]["data"]
    final_review = artifacts["final_review"]["data"]
    completion = artifacts["completion_audit"]["data"]
    gap_index = artifacts["production_gap_index"]["data"]
    current_rollup = artifacts["current_rollup"]["data"]
    external = artifacts["external_settlement"]["data"]
    external_handoff = artifacts["external_settlement_handoff"]["data"]
    governance_readiness = artifacts["governance_execute_readiness"]["data"]
    governance_handoff = artifacts["governance_execute_handoff"]["data"]
    image = artifacts["image_digests"]["data"]
    checklist = artifacts["collection_checklist"]["data"]
    packet_index = artifacts["operator_packet_index"]["data"]
    raw_packet_index = artifacts["raw_operator_packet_index"]["data"]
    prod_grade = artifacts["production_grade_goal_audit"]["data"]
    cross_plane_gate = artifacts["cross_plane_proof_gate"]["data"]

    code_ok = _source_status(code) == "VERIFIED HERE"
    wiring = code.get("wiring_covered", {}) if isinstance(code, dict) else {}
    pipeline_summary = _summary(pipeline)
    return_summary = _summary(return_acceptance)
    intake_summary = _summary(intake)
    source_summary = _summary(source_candidates)
    raw_summary = _summary(raw_inventory)
    semantic_summary = _summary(semantic)
    consistency_summary = _summary(consistency)
    rollup_summary = _summary(rollup_contract)
    closeout_summary = _summary(closeout)
    preflight_summary = _summary(preflight)
    final_summary = _summary(final_review)
    completion_summary = _summary(completion)
    gap_summary = _summary(gap_index)
    current_rollup_summary = _summary(current_rollup)
    external_summary = _summary(external)
    external_handoff_summary = _summary(external_handoff)
    governance_readiness_summary = _summary(governance_readiness)
    governance_handoff_summary = _summary(governance_handoff)
    image_summary = _summary(image)
    checklist_summary = _summary(checklist)
    packet_summary = _summary(packet_index)
    raw_packet_summary = _summary(raw_packet_index)
    prod_grade_summary = _summary(prod_grade)
    cross_plane_gate_summary = _summary(cross_plane_gate)
    cross_plane_gate_context = _mapping((cross_plane_gate or {}).get("context"))
    cross_plane_gate_local_ready = _cross_plane_proof_gate_local_ready(cross_plane_gate)
    cross_plane_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_gate)
    cross_plane_gate_blocker_ids = _cross_plane_proof_gate_blocker_ids(cross_plane_gate)

    raw_expected = _int_value(return_summary, "raw_files_expected") or _int_value(pipeline_summary, "raw_files_expected")
    raw_staged = _int_value(return_summary, "raw_files_staged")
    raw_local_observation = _int_value(return_summary, "raw_files_local_observation")
    raw_usable = _int_value(raw_summary, "usable_for_goal_completion_files")
    semantic_blockers = _int_value(semantic_summary, "blocking_items_total")
    semantic_errors = _int_value(semantic_summary, "semantic_preflight_errors_total")
    collector_blockers = _int_value(pipeline_summary, "collector_evidence_blockers")
    external_ready = external_summary.get("x0t_external_settlement_ready") is True
    external_handoff_local_ready = _external_settlement_handoff_local_ready(external_handoff, gap_summary)
    external_handoff_ready_for_completion = (
        external_handoff_local_ready and (external_handoff or {}).get("ready_for_completion_rerun") is True
    )
    external_handoff_production_ready = external_handoff_ready_for_completion and external_ready
    governance_handoff_local_ready = _governance_execute_handoff_local_ready(
        governance_handoff,
        governance_readiness,
        gap_summary,
    )
    governance_proposal_executed = _governance_proposal_executed(governance_readiness)
    governance_handoff_production_ready = governance_handoff_local_ready and governance_proposal_executed
    image_ready = image_summary.get("can_close_image_digests_blocker") is True

    row_specs = [
        RowSpec(
            "goal_audit:single_identity",
            "All components resolve through one canonical identity surface.",
            ["code_wiring"],
            ["python3 -m pytest tests/unit/test_integration_spine.py -q --no-cov"],
            code_ok and bool(wiring.get("identity")),
            code_ok and bool(wiring.get("identity")),
            {"source_status": _source_status(code), "identity": wiring.get("identity", "")},
            [],
        ),
        RowSpec(
            "goal_audit:event_bus",
            "The integration uses an event bus with replayable/hash-chain journal evidence.",
            ["code_wiring"],
            ["python3 -m pytest tests/unit/test_integration_spine.py -q --no-cov"],
            code_ok and bool(wiring.get("event_bus")),
            code_ok and bool(wiring.get("event_bus")),
            {"source_status": _source_status(code), "event_bus": wiring.get("event_bus", "")},
            [],
        ),
        RowSpec(
            "goal_audit:runtime_contract",
            "The local spine ties identity, events, policy, safe actuator, settlement, and external export together.",
            ["code_wiring"],
            ["python3 -m pytest tests/unit/test_integration_spine.py -q --no-cov"],
            code_ok,
            code_ok,
            {"source_status": _source_status(code), "verification": code.get("verification", []) if isinstance(code, dict) else []},
            [],
        ),
        RowSpec(
            "goal_audit:policy_engine",
            "Every action path is gated by the policy engine.",
            ["code_wiring"],
            ["python3 -m pytest tests/unit/test_integration_spine.py -q --no-cov"],
            code_ok and bool(wiring.get("policy_engine")),
            code_ok and bool(wiring.get("policy_engine")),
            {"source_status": _source_status(code), "policy_engine": wiring.get("policy_engine", "")},
            [],
        ),
        RowSpec(
            "goal_audit:safe_actuator",
            "Actuation is queued/rejected through a non-executing safe actuator and requires rollout evidence before production closeout.",
            ["code_wiring", "image_digests", "raw_inventory"],
            ["python3 -m src.integration.rollout_provenance --root . --require-ready"],
            code_ok and bool(wiring.get("safe_actuator")),
            code_ok and bool(wiring.get("safe_actuator")) and image_ready and raw_usable == raw_expected and raw_expected > 0,
            {
                "source_status": _source_status(code),
                "safe_actuator": wiring.get("safe_actuator", ""),
                "image_digests_decision": (image or {}).get("decision"),
                "raw_files_usable_for_goal_completion": raw_usable,
                "raw_files_expected": raw_expected,
            },
            _blocking_gaps(
                "live rollout digest/provenance gate is not ready" if not image_ready else "",
                "retained raw evidence is not production-grade" if raw_usable != raw_expected or raw_expected == 0 else "",
            ),
        ),
        RowSpec(
            "goal_audit:settlement_reward_loop",
            "The DAO/X0T earn-settlement loop is backed by a submitted external X0T settlement receipt.",
            ["code_wiring", "external_settlement"],
            ["python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready"],
            code_ok and bool(wiring.get("settlement_reward_loop")),
            code_ok and bool(wiring.get("settlement_reward_loop")) and external_ready,
            {
                "source_status": _source_status(code),
                "settlement_reward_loop": wiring.get("settlement_reward_loop", ""),
                "external_settlement_decision": (external or {}).get("decision"),
                "live_rpc_ready": external_summary.get("live_rpc_ready", False),
                "expected_evidence_file_exists": external_summary.get("expected_evidence_file_exists", False),
            },
            _blocking_gaps("real external X0T settlement receipt verified against live Base RPC is missing" if not external_ready else ""),
        ),
        RowSpec(
            "goal_audit:mapek_recovery_router",
            "MAPE-K recovery decisions are routed into policy and safe actuator plans.",
            ["code_wiring"],
            ["python3 -m pytest tests/unit/test_integration_spine.py -q --no-cov"],
            code_ok,
            code_ok,
            {"source_status": _source_status(code)},
            [],
        ),
        RowSpec(
            "goal_audit:paid_client_entitlement_router",
            "Paid-client entitlements route into subscription provisioning plans and require production serviceability evidence.",
            ["code_wiring", "raw_inventory"],
            ["python3 scripts/ops/verify_paid_client_serviceability_evidence_gate.py --require-ready"],
            code_ok,
            raw_summary.get("collector_classification_counts", {}).get("paid-client-serviceability", {}).get("PRODUCTION_GRADE", 0) == 8,
            {"paid_client_serviceability": raw_summary.get("collector_classification_counts", {}).get("paid-client-serviceability", {})},
            _blocking_gaps("paid-client-serviceability raw evidence is not production-grade"),
        ),
        RowSpec(
            "goal_audit:external_settlement_export",
            "Settlement export is retained and verifiable through a real external settlement artifact.",
            ["external_settlement"],
            ["python3 -m src.integration.external_settlement --root . --capture-from-rpc --write-evidence --require-ready"],
            _source_status(external) == "VERIFIED HERE",
            external_ready,
            {"decision": (external or {}).get("decision"), "summary": external_summary},
            _blocking_gaps("retained external settlement evidence/live RPC gate is not ready" if not external_ready else ""),
        ),
        RowSpec(
            "goal_audit:safe_rollout_rollback_envelope",
            "Safe rollout and rollback envelope has retained production evidence.",
            ["image_digests", "raw_inventory"],
            ["python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready"],
            _source_status(image) == "VERIFIED HERE",
            image_ready and raw_summary.get("collector_classification_counts", {}).get("live-rollout", {}).get("PRODUCTION_GRADE", 0) == 6,
            {"image_digests_decision": (image or {}).get("decision"), "summary": image_summary},
            _blocking_gaps("live rollout image digest/provenance evidence is not ready" if not image_ready else ""),
        ),
        RowSpec(
            "goal_audit:observability_sla_truth",
            "Claim boundaries keep observability/SLA claims truth-bound and do not promote simulated metrics.",
            ["completion_audit"],
            ["bash scripts/verify-v1.1.sh --fast --json"],
            _source_status(completion) == "VERIFIED HERE",
            _source_status(completion) == "VERIFIED HERE",
            {"completion_decision": (completion or {}).get("completion_decision")},
            [],
        ),
        RowSpec(
            "goal_audit:production_evidence_intake",
            "Production evidence intake is available, fail-closed, and lists every required evidence key.",
            ["production_intake", "operator_packet_index"],
            ["python3 -m src.integration.production_evidence_intake --root . --require-ready"],
            _source_status(intake) == "VERIFIED HERE"
            and packet_summary.get("packets_total", 0) >= len(REQUIRED_EVIDENCE_KEYS),
            (intake or {}).get("decision") == "READY_FOR_PRODUCTION_EVIDENCE_INSTALL" and intake_summary.get("ready_for_install") is True,
            {"decision": (intake or {}).get("decision"), "summary": intake_summary},
            _blocking_gaps("operator production evidence intake is blocked on required evidence keys" if intake_summary.get("ready_for_install") is not True else ""),
        ),
        RowSpec(
            "goal_audit:production_input_pipeline",
            "The scoped production input bundle is accepted only when raw and external evidence are ready.",
            ["production_input_pipeline", "return_acceptance"],
            ["python3 scripts/ops/run_integration_spine_production_input_pipeline.py --output json --require-ready"],
            _source_status(pipeline) == "VERIFIED HERE",
            (pipeline or {}).get("pipeline_decision") == "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" and pipeline_summary.get("raw_files_installed") == raw_expected and raw_expected > 0,
            {
                "pipeline_decision": (pipeline or {}).get("pipeline_decision"),
                "raw_files_expected": raw_expected,
                "raw_files_installed": pipeline_summary.get("raw_files_installed", 0),
                "raw_files_staged": raw_staged,
                "raw_files_install_claim_source": pipeline_summary.get("raw_files_install_claim_source", ""),
                "raw_files_local_observation": raw_local_observation,
                "collector_evidence_blockers": collector_blockers,
                "external_settlement_live_rpc_ready": pipeline_summary.get("external_settlement_live_rpc_ready", False),
            },
            _blocking_gaps(
                "external settlement live RPC readiness is false" if pipeline_summary.get("external_settlement_live_rpc_ready") is not True else "",
                f"collector semantic evidence blockers remain: {collector_blockers}" if collector_blockers else "",
                "return_acceptance.raw_files_staged is not equal to expected raw files" if raw_staged != raw_expected or raw_expected == 0 else "",
            ),
        ),
        RowSpec(
            "goal_audit:production_evidence_source_hygiene",
            "Source-candidate audit refuses local, template, mock, or operator-required routes as production proof.",
            ["source_candidates", "raw_inventory"],
            ["python3 -m src.integration.evidence_source_candidates --root . --require-ready"],
            _source_status(source_candidates) == "VERIFIED HERE",
            source_summary.get("ready_source_candidates_total", 0) >= len(REQUIRED_EVIDENCE_KEYS)
            and raw_usable == raw_expected
            and raw_expected > 0,
            {"decision": (source_candidates or {}).get("decision"), "summary": source_summary},
            _blocking_gaps(
                "no required production source candidates are ready"
                if source_summary.get("ready_source_candidates_total", 0) < len(REQUIRED_EVIDENCE_KEYS)
                else ""
            ),
        ),
        RowSpec(
            "goal_audit:production_evidence_import",
            "Every required production evidence file is imported and marked ready.",
            ["raw_inventory", "production_intake", "raw_operator_packet_index"],
            ["python3 -m src.integration.production_evidence_intake --root . --require-ready"],
            _source_status(raw_inventory) == "VERIFIED HERE" and _source_status(intake) == "VERIFIED HERE",
            raw_usable == raw_expected and raw_expected > 0 and intake_summary.get("ready_for_install") is True,
            {
                "raw_files_total": raw_summary.get("files_total", 0),
                "usable_for_goal_completion_files": raw_usable,
                "classification_counts": raw_summary.get("classification_counts", {}),
                "pending_evidence_keys": (intake or {}).get("pending_evidence_keys", []),
                "raw_operator_packet_summary": raw_packet_summary,
            },
            _blocking_gaps(
                f"{raw_expected} retained raw evidence files are still not production-grade"
                if raw_usable != raw_expected or raw_expected == 0
                else ""
            ),
        ),
        RowSpec(
            "goal_audit:production_raw_evidence_operator_packet",
            "Operator raw-evidence handoff covers every production-grade collector file and remains fail-closed until replacement.",
            ["raw_operator_packet_index"],
            ["python3 -m src.integration.production_raw_evidence_operator_packet --root . --require-actionable"],
            _source_status(raw_packet_index) == "VERIFIED HERE"
            and (raw_packet_index or {}).get("local_handoff_complete") is True
            and raw_packet_summary.get("raw_files_total", 0) > 0
            and raw_packet_summary.get("local_entrypoints_missing") == 0,
            (raw_packet_index or {}).get("production_ready") is True
            and raw_packet_summary.get("operator_bundle_files_production_ready") == raw_packet_summary.get("raw_files_total")
            and raw_packet_summary.get("raw_files_total", 0) > 0,
            {
                "decision": (raw_packet_index or {}).get("decision"),
                "local_handoff_complete": (raw_packet_index or {}).get("local_handoff_complete"),
                "production_ready": (raw_packet_index or {}).get("production_ready"),
                "summary": raw_packet_summary,
            },
            _blocking_gaps(
                "raw-evidence operator packet is not locally complete"
                if not (
                    _source_status(raw_packet_index) == "VERIFIED HERE"
                    and (raw_packet_index or {}).get("local_handoff_complete") is True
                    and raw_packet_summary.get("local_entrypoints_missing") == 0
                )
                else "",
                "operator bundle files are not production-ready"
                if (raw_packet_index or {}).get("production_ready") is not True
                else "",
            ),
        ),
        RowSpec(
            "goal_audit:external_settlement_submitted",
            "A real external X0T transaction receipt is retained and live-RPC verified.",
            ["external_settlement"],
            ["python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready"],
            _source_status(external) == "VERIFIED HERE",
            external_ready,
            {"decision": (external or {}).get("decision"), "summary": external_summary},
            _blocking_gaps("real submitted settlement receipt/live RPC evidence is missing" if not external_ready else ""),
        ),
        RowSpec(
            "goal_audit:broad_production_hardening",
            "Broader production-grade hardening audit has no production gaps.",
            ["production_grade_goal_audit"],
            ["python3 scripts/ops/audit_production_grade_goal.py --output json"],
            artifacts["production_grade_goal_audit"]["loaded"] is True,
            (prod_grade or {}).get("goal_can_be_marked_complete") is True,
            {"decision": (prod_grade or {}).get("completion_decision"), "summary": prod_grade_summary},
            _blocking_gaps("broader production-grade goal audit still reports production gaps" if (prod_grade or {}).get("goal_can_be_marked_complete") is not True else ""),
        ),
        RowSpec(
            "goal_audit:cross_plane_proof_gate",
            "Reusable cross-plane proof gate allows the objective's strong production/dataplane/traffic/DPI/settlement claims.",
            ["cross_plane_proof_gate"],
            [_cross_plane_proof_gate_command()],
            cross_plane_gate_local_ready,
            cross_plane_gate_allowed,
            {
                "schema": (cross_plane_gate or {}).get("schema"),
                "decision": (cross_plane_gate or {}).get("decision"),
                "allowed": (cross_plane_gate or {}).get("allowed"),
                "required_claim_ids": list(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS),
                "reported_claim_ids": _cross_plane_proof_gate_claim_ids(cross_plane_gate),
                "claims_total": _int_value(cross_plane_gate_summary, "claims_total"),
                "claims_allowed": _int_value(cross_plane_gate_summary, "claims_allowed"),
                "claims_blocked": _int_value(cross_plane_gate_summary, "claims_blocked"),
                "open_gap_ids": cross_plane_gate_context.get("open_gap_ids", []),
                "next_action_ids": cross_plane_gate_context.get("next_action_ids", []),
                "blocker_ids": cross_plane_gate_blocker_ids,
            },
            _blocking_gaps(
                "cross-plane proof gate artifact is missing or does not cover every objective strong claim"
                if not cross_plane_gate_local_ready
                else "",
                "cross-plane proof gate has not allowed objective strong claims" if not cross_plane_gate_allowed else "",
                cross_plane_gate_blocker_ids,
            ),
        ),
        RowSpec(
            "checklist_delta_manifest",
            "Collection checklist delta manifest is available for every required evidence item.",
            ["collection_checklist"],
            ["python3 -m src.integration.production_evidence_replacement_passport --root . --require-valid"],
            _source_status(checklist) == "VERIFIED HERE" and checklist_summary.get("items_total", 31) >= 31,
            checklist_summary.get("items_ready", 0) == checklist_summary.get("items_total", 31),
            {"decision": (checklist or {}).get("decision"), "summary": checklist_summary},
            _blocking_gaps("collection checklist still has operator-required evidence items"),
        ),
        RowSpec(
            "production_input_return_acceptance",
            "Returned operator inputs are accepted for staging/install only when raw and external settlement evidence are ready.",
            ["return_acceptance"],
            ["python3 -m src.integration.production_input_return_acceptance --root . --require-ready"],
            _source_status(return_acceptance) == "VERIFIED HERE",
            (return_acceptance or {}).get("ready_for_pipeline_install") is True,
            {"decision": (return_acceptance or {}).get("decision"), "summary": return_summary},
            _blocking_gaps(
                "raw files are local observations, not staged production evidence" if raw_local_observation else "",
                "external settlement live RPC gate is not ready" if return_summary.get("external_settlement_live_rpc_ready") is not True else "",
            ),
        ),
        RowSpec(
            "return_packet_verification",
            "Operator return packet verification covers required raw and external artifacts.",
            ["operator_packet_index", "production_intake"],
            ["python3 -m src.integration.operator_evidence_packet --root . --all-blockers --require-all-actionable"],
            _source_status(packet_index) == "VERIFIED HERE" and (packet_index or {}).get("all_packets_actionable") is True,
            intake_summary.get("required_evidence_keys_ready") == intake_summary.get("required_evidence_keys_total") and intake_summary.get("required_evidence_keys_total", 0) > 0,
            {"packet_summary": packet_summary, "intake_summary": intake_summary},
            _blocking_gaps("operator packet is actionable, but required evidence keys are not ready"),
        ),
        RowSpec(
            "production_next_inputs_verification",
            "Next production inputs are explicit and actionable for the operator.",
            ["production_gap_index", "operator_packet_index"],
            ["python3 -m src.integration.production_gap_index --root . --require-clear"],
            _source_status(gap_index) == "VERIFIED HERE"
            and packet_summary.get("packets_total", 0) >= len(REQUIRED_EVIDENCE_KEYS),
            (gap_index or {}).get("decision") == "NO_PRODUCTION_EVIDENCE_GAPS",
            {"operator_priority_order": (gap_index or {}).get("operator_priority_order", []), "summary": gap_summary},
            _blocking_gaps("production gap index still has pending evidence keys" if gap_summary.get("pending_evidence_keys", 0) else ""),
        ),
        RowSpec(
            "external_settlement_live_rpc_gate",
            "External X0T settlement live RPC gate is ready.",
            ["external_settlement"],
            ["python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready"],
            _source_status(external) == "VERIFIED HERE",
            external_ready,
            {"summary": external_summary},
            _blocking_gaps("live RPC settlement verification is not ready" if not external_ready else ""),
        ),
        RowSpec(
            "external_settlement_operator_handoff",
            "External settlement operator handoff points to exact evidence and verification commands.",
            ["external_settlement_handoff", "production_gap_index", "operator_packet_index", "external_settlement"],
            [
                "python3 -m src.integration.external_settlement_operator_handoff --root . --require-ready",
                "python3 -m src.integration.operator_evidence_packet --root . --evidence-key external_settlement --require-actionable",
            ],
            external_handoff_local_ready,
            external_handoff_production_ready,
            {
                "handoff_source_status": _source_status(external_handoff),
                "handoff_schema_version": (external_handoff or {}).get("schema_version"),
                "handoff_decision": (external_handoff or {}).get("handoff_decision"),
                "ready_for_completion_rerun": (external_handoff or {}).get("ready_for_completion_rerun"),
                "capture_preflight_decision": external_handoff_summary.get("capture_preflight_decision"),
                "capture_inputs_ready": external_handoff_summary.get("capture_inputs_ready"),
                "missing_inputs_total": external_handoff_summary.get("missing_inputs_total"),
                "source_errors_total": external_handoff_summary.get("source_errors_total"),
                "operator_actions_total": external_handoff_summary.get("operator_actions_total"),
                "operator_commands_total": external_handoff_summary.get("operator_commands_total"),
                "operator_command_entrypoints_missing": external_handoff_summary.get(
                    "operator_command_entrypoints_missing"
                ),
                "operator_command_surface_ready": external_handoff_summary.get("operator_command_surface_ready"),
                "operator_commands_with_shell_redirection_placeholders": external_handoff_summary.get(
                    "operator_commands_with_shell_redirection_placeholders"
                ),
                "operator_command_shell_surface_ready": external_handoff_summary.get(
                    "operator_command_shell_surface_ready"
                ),
                "operator_sequence_ready": external_handoff_summary.get("operator_sequence_ready"),
                "gap_external_settlement_handoff_clear": gap_summary.get("external_settlement_handoff_clear"),
                "gap_external_settlement_handoff_ready_for_completion_rerun": gap_summary.get(
                    "external_settlement_handoff_ready_for_completion_rerun"
                ),
                "operator_priority_order": (packet_index or {}).get("operator_priority_order", []),
                "external_summary": external_summary,
            },
            _blocking_gaps(
                "external settlement operator handoff current shard is missing/stale/not read-only/not command-surface clean"
                if not external_handoff_local_ready
                else "",
                "external settlement handoff is clear, but settlement evidence/live RPC are still missing"
                if external_handoff_local_ready and not external_handoff_production_ready
                else "",
            ),
        ),
        RowSpec(
            "x0t_governance_execute_handoff",
            "X0T governance proposal execution has a read-only operator handoff and cannot count as production-ready until proposal 1 is Executed.",
            ["governance_execute_readiness", "governance_execute_handoff", "production_gap_index", "completion_audit"],
            [
                "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md --require-ready",
                "python3 scripts/ops/run_x0t_governance_execute_handoff.py --write-md --require-actionable",
            ],
            governance_handoff_local_ready,
            governance_handoff_production_ready,
            {
                "readiness_source_status": _source_status(governance_readiness),
                "readiness_decision": (governance_readiness or {}).get("decision"),
                "execute_ready_now": governance_readiness_summary.get("execute_ready_now"),
                "proposal_state": (governance_readiness or {}).get("proposal_state", {}),
                "next_executable_after_utc": governance_readiness_summary.get("next_executable_after_utc"),
                "seconds_until_earliest_execution_by_block_time": _value(
                    governance_readiness,
                    "timelock.seconds_until_earliest_execution_by_block_time",
                ),
                "handoff_source_status": _source_status(governance_handoff),
                "handoff_schema_version": (governance_handoff or {}).get("schema_version"),
                "handoff_decision": (governance_handoff or {}).get("handoff_decision"),
                "handoff_actionable": (governance_handoff or {}).get("handoff_actionable"),
                "ready_for_operator_execute": (governance_handoff or {}).get("ready_for_operator_execute"),
                "missing_inputs_total": governance_handoff_summary.get("missing_inputs_total"),
                "source_errors_total": governance_handoff_summary.get("source_errors_total"),
                "operator_actions_total": governance_handoff_summary.get("operator_actions_total"),
                "operator_commands_total": governance_handoff_summary.get("operator_commands_total"),
                "operator_command_entrypoints_missing": governance_handoff_summary.get(
                    "operator_command_entrypoints_missing"
                ),
                "operator_command_surface_ready": governance_handoff_summary.get("operator_command_surface_ready"),
                "operator_commands_with_shell_redirection_placeholders": governance_handoff_summary.get(
                    "operator_commands_with_shell_redirection_placeholders"
                ),
                "operator_command_shell_surface_ready": governance_handoff_summary.get(
                    "operator_command_shell_surface_ready"
                ),
                "operator_sequence_ready": governance_handoff_summary.get("operator_sequence_ready"),
                "gap_governance_handoff_clear": gap_summary.get("x0t_governance_execute_handoff_clear"),
                "gap_governance_proposal_executed": gap_summary.get("x0t_governance_proposal_executed"),
                "approval_value_required": _value(
                    governance_handoff,
                    "approval_boundary.expected_value",
                ),
            },
            _blocking_gaps(
                "X0T governance execute handoff current shard is missing/stale/not read-only/not command-surface clean"
                if not governance_handoff_local_ready
                else "",
                "governance execute handoff is clear, but proposal 1 is not yet Executed"
                if governance_handoff_local_ready and not governance_handoff_production_ready
                else "",
            ),
        ),
        RowSpec(
            "production_closure_preflight",
            "Closure preflight blocks until closeout sources are ready.",
            ["closure_preflight"],
            ["python3 scripts/ops/run_integration_spine_production_closure_preflight.py --output json --require-ready"],
            _source_status(preflight) == "VERIFIED HERE",
            (preflight or {}).get("ready") is True,
            {"decision": (preflight or {}).get("decision"), "summary": preflight_summary},
            _blocking_gaps("closure preflight is blocked on operator evidence" if (preflight or {}).get("ready") is not True else ""),
        ),
        RowSpec(
            "production_final_review",
            "Final review blocks until production closeout is ready.",
            ["final_review"],
            ["python3 scripts/ops/run_integration_spine_production_final_review.py --output json --require-ready"],
            _source_status(final_review) == "VERIFIED HERE",
            (final_review or {}).get("ready") is True,
            {"decision": (final_review or {}).get("decision"), "summary": final_summary},
            _blocking_gaps("final review is blocked on operator evidence" if (final_review or {}).get("ready") is not True else ""),
        ),
        RowSpec(
            "production_closeout_review",
            "Closeout review is the last local authority before marking the objective complete.",
            ["closeout_review"],
            ["python3 -m src.integration.production_closeout_review --root . --require-ready"],
            _source_status(closeout) == "VERIFIED HERE",
            (closeout or {}).get("ready") is True,
            {"decision": (closeout or {}).get("decision"), "summary": closeout_summary},
            _blocking_gaps("closeout review is blocked on operator evidence" if (closeout or {}).get("ready") is not True else ""),
        ),
        RowSpec(
            "production_evidence_replacement_passport",
            "Replacement passport is clear only when every local/template/mock input is replaced by production evidence.",
            ["raw_inventory", "production_intake"],
            ["python3 -m src.integration.production_evidence_replacement_passport --root . --require-valid --require-ready"],
            _source_status(raw_inventory) == "VERIFIED HERE",
            raw_usable == raw_expected and raw_expected > 0 and intake_summary.get("ready_for_install") is True,
            {"raw_inventory_summary": raw_summary, "intake_summary": intake_summary},
            _blocking_gaps("replacement passport remains operator-required"),
        ),
        RowSpec(
            "required_evidence_consistency",
            "Required evidence consistency agrees all required evidence files are ready.",
            ["required_consistency"],
            ["python3 -m src.integration.required_evidence_consistency --root . --require-ready"],
            _source_status(consistency) == "VERIFIED HERE",
            (consistency or {}).get("production_ready") is True,
            {"decision": (consistency or {}).get("decision"), "summary": consistency_summary},
            _blocking_gaps("required evidence consistency is valid but blocked on operator evidence" if (consistency or {}).get("production_ready") is not True else ""),
        ),
        RowSpec(
            "completion_gate_runner",
            "Completion audit must return COMPLETE and goal_can_be_marked_complete=true.",
            ["completion_audit", "current_rollup"],
            ["python3 -m src.integration.completion_audit --root . --require-complete"],
            _source_status(completion) == "VERIFIED HERE",
            (completion or {}).get("goal_can_be_marked_complete") is True and (current_rollup or {}).get("goal_can_be_marked_complete") is True,
            {"completion_summary": completion_summary, "current_rollup_summary": current_rollup_summary},
            _blocking_gaps("completion audit/current rollup still report NOT_COMPLETE"),
        ),
        RowSpec(
            "production_grade_hardening",
            "Broader production-grade hardening audit has no production gaps.",
            ["production_grade_goal_audit"],
            ["python3 scripts/ops/audit_production_grade_goal.py --output json"],
            artifacts["production_grade_goal_audit"]["loaded"] is True,
            (prod_grade or {}).get("goal_can_be_marked_complete") is True,
            {"decision": (prod_grade or {}).get("completion_decision"), "summary": prod_grade_summary},
            _blocking_gaps("production-grade hardening audit remains blocked" if (prod_grade or {}).get("goal_can_be_marked_complete") is not True else ""),
        ),
    ]

    return [_as_row(artifacts, row) for row in row_specs]


def build_report(root: Path) -> Dict[str, Any]:
    specs = [
        ArtifactSpec("code_wiring", DEFAULT_CODE_WIRING),
        ArtifactSpec("production_input_pipeline", DEFAULT_PRODUCTION_INPUT_PIPELINE),
        ArtifactSpec("return_acceptance", DEFAULT_RETURN_ACCEPTANCE),
        ArtifactSpec("production_intake", DEFAULT_PRODUCTION_INTAKE),
        ArtifactSpec("source_candidates", DEFAULT_SOURCE_CANDIDATES),
        ArtifactSpec("raw_inventory", DEFAULT_RAW_INVENTORY),
        ArtifactSpec("semantic_queue", DEFAULT_SEMANTIC_QUEUE),
        ArtifactSpec("required_consistency", DEFAULT_REQUIRED_CONSISTENCY),
        ArtifactSpec("rollup_contract", DEFAULT_ROLLUP_CONTRACT),
        ArtifactSpec("closeout_review", DEFAULT_CLOSEOUT_REVIEW),
        ArtifactSpec("closure_preflight", DEFAULT_CLOSURE_PREFLIGHT),
        ArtifactSpec("final_review", DEFAULT_FINAL_REVIEW),
        ArtifactSpec("completion_audit", DEFAULT_COMPLETION_AUDIT),
        ArtifactSpec("production_gap_index", DEFAULT_PRODUCTION_GAP_INDEX),
        ArtifactSpec("current_rollup", DEFAULT_CURRENT_ROLLUP),
        ArtifactSpec("external_settlement", DEFAULT_EXTERNAL_SETTLEMENT),
        ArtifactSpec("external_settlement_handoff", DEFAULT_EXTERNAL_SETTLEMENT_HANDOFF),
        ArtifactSpec("governance_execute_readiness", DEFAULT_GOVERNANCE_EXECUTE_READINESS),
        ArtifactSpec("governance_execute_handoff", DEFAULT_GOVERNANCE_EXECUTE_HANDOFF),
        ArtifactSpec("image_digests", DEFAULT_IMAGE_DIGESTS),
        ArtifactSpec("collection_checklist", DEFAULT_COLLECTION_CHECKLIST),
        ArtifactSpec("operator_packet_index", DEFAULT_OPERATOR_PACKET_INDEX),
        ArtifactSpec("raw_operator_packet_index", DEFAULT_RAW_OPERATOR_PACKET_INDEX),
        ArtifactSpec("production_grade_goal_audit", DEFAULT_PRODUCTION_GRADE_GOAL_AUDIT),
        ArtifactSpec("cross_plane_proof_gate", DEFAULT_CROSS_PLANE_PROOF_GATE),
    ]
    artifacts = _load_artifacts(root, specs)
    rows = _rows(artifacts)

    source_errors = [
        artifact["error"]
        for artifact in artifacts.values()
        if artifact.get("loaded") is not True and artifact.get("key") != "production_grade_goal_audit"
    ]
    # production-grade audit is useful context but may be absent in reduced test roots.
    source_errors = [
        artifact.get("error", "")
        for key, artifact in artifacts.items()
        if key != "production_grade_goal_audit" and artifact.get("loaded") is not True
    ]

    row_ids = {str(row.get("id")) for row in rows}
    missing_required = sorted(REQUIRED_GOAL_AUDIT_ROWS - row_ids)
    blocking_rows = [row for row in rows if row.get("production_ready") is not True]
    local_ready_rows = [row for row in rows if row.get("local_ready") is True]
    production_ready_rows = [row for row in rows if row.get("production_ready") is True]

    pipeline_summary = _summary(artifacts["production_input_pipeline"]["data"])
    return_summary = _summary(artifacts["return_acceptance"]["data"])
    raw_summary = _summary(artifacts["raw_inventory"]["data"])
    semantic_summary = _summary(artifacts["semantic_queue"]["data"])
    external_summary = _summary(artifacts["external_settlement"]["data"])
    external_ready = external_summary.get("x0t_external_settlement_ready") is True
    external_handoff = artifacts["external_settlement_handoff"]["data"]
    external_handoff_summary = _summary(external_handoff)
    governance_readiness = artifacts["governance_execute_readiness"]["data"]
    governance_handoff = artifacts["governance_execute_handoff"]["data"]
    governance_readiness_summary = _summary(governance_readiness)
    governance_handoff_summary = _summary(governance_handoff)
    completion_summary = _summary(artifacts["completion_audit"]["data"])
    gap_summary = _summary(artifacts["production_gap_index"]["data"])
    closeout = artifacts["closeout_review"]["data"]
    closeout_summary = _summary(closeout)
    closeout_handoffs = _mapping((closeout or {}).get("operator_handoffs"))
    raw_operator_packet = artifacts["raw_operator_packet_index"]["data"]
    raw_packet_summary = _summary(artifacts["raw_operator_packet_index"]["data"])
    prod_grade = artifacts["production_grade_goal_audit"]["data"]
    prod_grade_summary = _summary(prod_grade)
    prod_grade_next_actions = _production_grade_next_actions(prod_grade)
    cross_plane_gate = artifacts["cross_plane_proof_gate"]["data"]
    cross_plane_gate_summary = _summary(cross_plane_gate)
    cross_plane_gate_context = _mapping((cross_plane_gate or {}).get("context"))
    cross_plane_gate_allowed = _cross_plane_proof_gate_allowed(cross_plane_gate)
    cross_plane_gate_blocker_ids = _cross_plane_proof_gate_blocker_ids(cross_plane_gate)
    raw_expected = _int_value(return_summary, "raw_files_expected") or _int_value(pipeline_summary, "raw_files_expected")
    external_ready = external_summary.get("x0t_external_settlement_ready") is True
    external_handoff_local_ready = _external_settlement_handoff_local_ready(external_handoff, gap_summary)
    governance_handoff_local_ready = _governance_execute_handoff_local_ready(
        governance_handoff,
        governance_readiness,
        gap_summary,
    )
    governance_proposal_executed = _governance_proposal_executed(governance_readiness)
    ready = not source_errors and not blocking_rows and not missing_required

    return {
        "schema_version": "x0tta6bl4-integration-spine-objective-coverage-audit-v4-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "objective": OBJECTIVE,
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "goal_can_be_marked_complete": ready,
        "goal_completion_authority": (
            "completion_audit + current_rollup + production closeout gates + reusable cross-plane proof gate"
        ),
        "local_integration_ready": completion_summary.get("local_wiring_passed") is True,
        "production_ready": ready,
        "ready_for_production_closeout_review": ready,
        "closeout_review_required_for_goal_completion": True,
        "claim_boundary": (
            "Repo-generated read-only prompt-to-artifact coverage audit. It maps the objective "
            "to current artifacts and refuses production completion while operator evidence is "
            "missing or the reusable cross-plane proof gate blocks strong claims. It does not "
            "collect evidence, contact live systems, mutate runtime, submit transactions, or close /goal."
        ),
        "source_artifacts": [spec.path for spec in specs],
        "source_errors": source_errors,
        "success_criteria": [
            "single canonical identity surface is verified",
            "event bus/hash-chain journal is verified",
            "policy engine gates action paths",
            "safe actuator is wired and production-safe rollout evidence is ready",
            "settlement/reward loop is backed by submitted external X0T settlement evidence",
            "all production evidence keys are ready",
            "reusable cross-plane proof gate allows the objective's strong claims",
            "completion/final/closeout gates allow production closeout",
        ],
        "prompt_to_artifact_checklist": rows,
        "blocking_row_ids": [str(row.get("id")) for row in blocking_rows],
        "not_verified_yet": []
        if ready
        else [
            "real external X0T settlement receipt verified against live Base RPC",
            f"{raw_expected} local-observation/operator-required raw evidence files replaced by production-grade retained evidence",
            "live rollout image digest/provenance gate ready",
            "reusable cross-plane proof gate allows objective strong claims",
            "required evidence consistency, rollup, closeout, final review, and completion audit all clear",
        ],
        "next_actions": [
            {
                "id": "submit_external_settlement_receipt",
                "status": _external_settlement_next_action_status(
                    external_ready=external_ready,
                    handoff_local_ready=external_handoff_local_ready,
                    ready_for_completion_rerun=(external_handoff or {}).get("ready_for_completion_rerun") is True,
                ),
                "action": "Provide a real submitted X0T settlement receipt and matching Base RPC verification.",
                "handoff_decision": (external_handoff or {}).get("handoff_decision"),
                "ready_for_completion_rerun": (external_handoff or {}).get("ready_for_completion_rerun"),
                "capture_inputs_ready": external_handoff_summary.get("capture_inputs_ready"),
                "command": (
                    "python3 -m src.integration.external_settlement --root . --capture-from-rpc "
                    "--transaction-hash \"$X0T_SETTLEMENT_TX_HASH\" --destination-chain \"$X0T_DESTINATION_CHAIN\" "
                    "--settlement-id \"$X0T_SETTLEMENT_ID\" --rpc-url \"$X0T_BASE_RPC_URL\" "
                    "--evidence .tmp/external-settlement-evidence/settlement-submit.json --write-evidence --require-ready"
                ),
            },
            {
                "id": "replace_semantically_blocked_raw_evidence",
                "status": _raw_evidence_next_action_status(
                    raw_ready=raw_summary.get("usable_for_goal_completion_files", 0) == raw_summary.get("files_total", 0),
                    raw_operator_packet_local_handoff_complete=(raw_operator_packet or {}).get("local_handoff_complete") is True,
                    raw_operator_packet_replacement_required=_int_value(
                        raw_packet_summary,
                        "operator_bundle_files_replacement_required",
                    )
                    or 0,
                    raw_operator_packet_readiness_decision=raw_packet_summary.get("raw_readiness_decision"),
                ),
                "action": "Replace retained/local raw JSON with operator-captured production JSON for every required raw file.",
                "raw_operator_packet_decision": (raw_operator_packet or {}).get("decision"),
                "raw_operator_packet_local_handoff_complete": (raw_operator_packet or {}).get("local_handoff_complete"),
                "raw_operator_packet_files_replacement_required": _int_value(
                    raw_packet_summary,
                    "operator_bundle_files_replacement_required",
                ),
                "raw_operator_packet_readiness_decision": raw_packet_summary.get("raw_readiness_decision"),
                "raw_operator_packet_readiness_raw_files_local_observation": _int_value(
                    raw_packet_summary,
                    "raw_readiness_raw_files_local_observation",
                ),
                "raw_inventory_files_total": _int_value(raw_summary, "files_total"),
                "raw_inventory_usable_for_goal_completion": _int_value(
                    raw_summary,
                    "usable_for_goal_completion_files",
                ),
                "command": "python3 scripts/ops/import_production_raw_evidence_bundle.py --bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready",
            },
            {
                "id": "execute_x0t_governance_proposal_after_timelock",
                "status": _governance_execute_next_action_status(
                    proposal_executed=governance_proposal_executed,
                    ready_for_operator_execute=(governance_handoff or {}).get("ready_for_operator_execute") is True,
                ),
                "action": (
                    "After readiness becomes READY_TO_EXECUTE, dry-run proposal execution, then execute only with "
                    "explicit operator approval and retain the mined Executed-state receipt."
                ),
                "readiness_decision": (governance_readiness or {}).get("decision"),
                "ready_for_operator_execute": (governance_handoff or {}).get("ready_for_operator_execute"),
                "next_executable_after_utc": governance_readiness_summary.get("next_executable_after_utc"),
                "seconds_until_earliest_execution_by_block_time": _value(
                    governance_readiness,
                    "timelock.seconds_until_earliest_execution_by_block_time",
                ),
                "approval_env": "X0T_EXECUTE_PROPOSAL_APPROVAL",
                "approval_value_required": "execute-proposal-1-base-sepolia",
                "requires_operator_approval": True,
                "submits_transaction": True,
                "commands": [
                    "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md --require-ready",
                    "python3 execute_dao_proposal.py --dry-run",
                    "X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia PRIVATE_KEY=\"$PRIVATE_KEY\" python3 execute_dao_proposal.py",
                ],
                "required_artifact": ".tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json",
                "acceptance_rule": "receipt ok=true only when transaction status is 1 and final proposal state is Executed",
            },
            {
                "id": "rerun_closeout_chain",
                "status": "AFTER_BLOCKERS" if not ready else "DONE",
                "action": "Rerun coverage, passport, semantic queue, pipeline, closeout, final review, and completion audit.",
                "command": "python3 scripts/ops/audit_integration_spine_objective_coverage.py --output text",
            },
            {
                "id": "clear_cross_plane_proof_gate",
                "status": "DONE" if cross_plane_gate_allowed else "BLOCKING",
                "action": (
                    "Run the reusable cross-plane proof gate for the objective's strong claims and clear every "
                    "blocker before treating the objective coverage audit as complete."
                ),
                "source_artifact": DEFAULT_CROSS_PLANE_PROOF_GATE,
                "command": _cross_plane_proof_gate_command(),
                "requested_claim_ids": list(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS),
                "reported_claim_ids": _cross_plane_proof_gate_claim_ids(cross_plane_gate),
                "blocker_ids": cross_plane_gate_blocker_ids,
            },
            *prod_grade_next_actions,
        ],
        "production_grade_next_actions": prod_grade_next_actions,
        "summary": {
            "artifact_errors_total": len(source_errors),
            "coverage_rows_total": len(rows),
            "coverage_rows_local_ready": len(local_ready_rows),
            "coverage_rows_production_ready": len(production_ready_rows),
            "coverage_rows_blocking": len(blocking_rows),
            "blocking_row_ids": [str(row.get("id")) for row in blocking_rows],
            "required_goal_audit_rows_total": len(REQUIRED_GOAL_AUDIT_ROWS),
            "required_goal_audit_rows_present": len(REQUIRED_GOAL_AUDIT_ROWS & row_ids),
            "required_goal_audit_rows_missing": missing_required,
            "current_collector_evidence_blockers": _int_value(pipeline_summary, "collector_evidence_blockers"),
            "current_external_settlement_ready": external_summary.get("x0t_external_settlement_ready", False),
            "closeout_operator_handoff_source_artifact": closeout_handoffs.get("source_artifact", ""),
            "closeout_operator_handoff_source_available": closeout_summary.get(
                "operator_handoff_source_available"
            ),
            "closeout_operator_handoff_source_errors_total": _int_value(
                closeout_summary,
                "operator_handoff_source_errors_total",
            ),
            "closeout_x0t_governance_handoff_operator_actions_total": _int_value(
                closeout_summary,
                "x0t_governance_handoff_operator_actions_total",
            ),
            "closeout_x0t_governance_handoff_operator_commands_total": _int_value(
                closeout_summary,
                "x0t_governance_handoff_operator_commands_total",
            ),
            "closeout_x0t_governance_handoff_operator_sequence_ready": closeout_summary.get(
                "x0t_governance_handoff_operator_sequence_ready"
            ),
            "closeout_external_settlement_handoff_operator_actions_total": _int_value(
                closeout_summary,
                "external_settlement_handoff_operator_actions_total",
            ),
            "closeout_external_settlement_handoff_operator_commands_total": _int_value(
                closeout_summary,
                "external_settlement_handoff_operator_commands_total",
            ),
            "closeout_external_settlement_handoff_operator_sequence_ready": closeout_summary.get(
                "external_settlement_handoff_operator_sequence_ready"
            ),
            "closeout_x0t_contract_handoff_available": closeout_summary.get(
                "x0t_contract_handoff_available"
            ),
            "closeout_x0t_contract_handoff_decision": closeout_summary.get(
                "x0t_contract_handoff_decision"
            ),
            "closeout_x0t_contract_handoff_deployment_ready": closeout_summary.get(
                "x0t_contract_handoff_deployment_ready"
            ),
            "closeout_x0t_contract_handoff_operator_actions_total": _int_value(
                closeout_summary,
                "x0t_contract_handoff_operator_actions_total",
            ),
            "closeout_x0t_contract_handoff_operator_commands_total": _int_value(
                closeout_summary,
                "x0t_contract_handoff_operator_commands_total",
            ),
            "closeout_x0t_contract_handoff_operator_sequence_ready": closeout_summary.get(
                "x0t_contract_handoff_operator_sequence_ready"
            ),
            "closeout_live_rollout_handoff_available": closeout_summary.get(
                "live_rollout_handoff_available"
            ),
            "closeout_live_rollout_handoff_decision": closeout_summary.get(
                "live_rollout_handoff_decision"
            ),
            "closeout_live_rollout_handoff_ready_for_completion_rerun": closeout_summary.get(
                "live_rollout_handoff_ready_for_completion_rerun"
            ),
            "closeout_live_rollout_handoff_operator_actions_total": _int_value(
                closeout_summary,
                "live_rollout_handoff_operator_actions_total",
            ),
            "closeout_live_rollout_handoff_operator_commands_total": _int_value(
                closeout_summary,
                "live_rollout_handoff_operator_commands_total",
            ),
            "closeout_live_rollout_handoff_operator_command_entrypoints_missing": _int_value(
                closeout_summary,
                "live_rollout_handoff_operator_command_entrypoints_missing",
            ),
            "closeout_live_rollout_handoff_operator_sequence_ready": closeout_summary.get(
                "live_rollout_handoff_operator_sequence_ready"
            ),
            "production_grade_goal_audit_available": artifacts["production_grade_goal_audit"]["loaded"] is True,
            "production_grade_goal_decision": (prod_grade or {}).get("completion_decision"),
            "production_grade_goal_can_be_marked_complete": (prod_grade or {}).get(
                "goal_can_be_marked_complete"
            ),
            "production_grade_next_actions_total": _int_value(prod_grade_summary, "next_actions_total"),
            "production_grade_next_actions_operator_input_required": _int_value(
                prod_grade_summary,
                "next_actions_operator_input_required",
            ),
            "production_grade_next_actions_operator_approval_required": _int_value(
                prod_grade_summary,
                "next_actions_operator_approval_required",
            ),
            "production_grade_next_actions_after_blockers": _int_value(
                prod_grade_summary,
                "next_actions_after_blockers",
            ),
            "production_grade_next_actions_generic_blocking": _int_value(
                prod_grade_summary,
                "next_actions_generic_blocking",
            ),
            "production_grade_completion_gate_runner_available": prod_grade_summary.get(
                "completion_gate_runner_available"
            ),
            "production_grade_completion_gate_runner_decision": prod_grade_summary.get(
                "completion_gate_runner_decision"
            ),
            "production_grade_completion_gate_production_input_return_packet_available": prod_grade_summary.get(
                "completion_gate_production_input_return_packet_available"
            ),
            "production_grade_completion_gate_production_input_return_packet_decision": prod_grade_summary.get(
                "completion_gate_production_input_return_packet_decision"
            ),
            "production_grade_completion_gate_production_input_return_packet_blocking_inputs_total": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_blocking_inputs_total",
            ),
            "production_grade_completion_gate_production_input_return_packet_blocking_raw_inputs": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_blocking_raw_inputs",
            ),
            "production_grade_completion_gate_production_input_return_packet_blocking_external_inputs": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_blocking_external_inputs",
            ),
            "production_grade_completion_gate_production_input_return_packet_blocking_inputs_operator_input_required": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_blocking_inputs_operator_input_required",
            ),
            "production_grade_completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required",
            ),
            "production_grade_completion_gate_production_input_return_packet_operator_next_actions_total": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_operator_next_actions_total",
            ),
            "production_grade_completion_gate_production_input_return_packet_operator_next_actions_operator_input_required": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_operator_next_actions_operator_input_required",
            ),
            "production_grade_completion_gate_production_input_return_packet_operator_next_actions_generic_blocking": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_operator_next_actions_generic_blocking",
            ),
            "production_grade_completion_gate_production_input_return_packet_raw_files_expected": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_raw_files_expected",
            ),
            "production_grade_completion_gate_production_input_return_packet_raw_files_missing": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_raw_files_missing",
            ),
            "production_grade_completion_gate_production_input_return_packet_raw_files_local_observation": _int_value(
                prod_grade_summary,
                "completion_gate_production_input_return_packet_raw_files_local_observation",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_decision": prod_grade_summary.get(
                "completion_gate_x0t_contract_handoff_decision"
            ),
            "production_grade_completion_gate_x0t_contract_handoff_approval_value_required": (
                prod_grade_summary.get("completion_gate_x0t_contract_handoff_approval_value_required")
            ),
            "production_grade_completion_gate_x0t_contract_handoff_missing_inputs_total": _int_value(
                prod_grade_summary,
                "completion_gate_x0t_contract_handoff_missing_inputs_total",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_actions_total": _int_value(
                prod_grade_summary,
                "completion_gate_x0t_contract_handoff_operator_actions_total",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_approval_required_actions_total": _int_value(
                prod_grade_summary,
                "completion_gate_x0t_contract_handoff_operator_approval_required_actions_total",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_commands_total": _int_value(
                prod_grade_summary,
                "completion_gate_x0t_contract_handoff_operator_commands_total",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready": prod_grade_summary.get(
                "completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready"
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": _int_value(
                prod_grade_summary,
                "completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders",
            ),
            "production_grade_completion_gate_x0t_contract_handoff_operator_sequence_ready": prod_grade_summary.get(
                "completion_gate_x0t_contract_handoff_operator_sequence_ready"
            ),
            "production_grade_completion_gate_live_rollout_handoff_decision": prod_grade_summary.get(
                "completion_gate_live_rollout_handoff_decision"
            ),
            "production_grade_completion_gate_live_rollout_handoff_missing_inputs_total": _int_value(
                prod_grade_summary,
                "completion_gate_live_rollout_handoff_missing_inputs_total",
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_actions_total": _int_value(
                prod_grade_summary,
                "completion_gate_live_rollout_handoff_operator_actions_total",
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_input_required_actions_total": _int_value(
                prod_grade_summary,
                "completion_gate_live_rollout_handoff_operator_input_required_actions_total",
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_commands_total": _int_value(
                prod_grade_summary,
                "completion_gate_live_rollout_handoff_operator_commands_total",
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_command_shell_surface_ready": prod_grade_summary.get(
                "completion_gate_live_rollout_handoff_operator_command_shell_surface_ready"
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _int_value(
                prod_grade_summary,
                "completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders",
            ),
            "production_grade_completion_gate_live_rollout_handoff_operator_sequence_ready": prod_grade_summary.get(
                "completion_gate_live_rollout_handoff_operator_sequence_ready"
            ),
            "cross_plane_proof_gate_available": artifacts["cross_plane_proof_gate"]["loaded"] is True,
            "cross_plane_proof_gate_decision": (cross_plane_gate or {}).get("decision"),
            "cross_plane_proof_gate_allowed": cross_plane_gate_allowed,
            "cross_plane_proof_gate_required_claim_ids": list(OBJECTIVE_COVERAGE_CROSS_PLANE_CLAIMS),
            "cross_plane_proof_gate_reported_claim_ids": _cross_plane_proof_gate_claim_ids(cross_plane_gate),
            "cross_plane_proof_gate_claims_total": _int_value(cross_plane_gate_summary, "claims_total"),
            "cross_plane_proof_gate_claims_allowed": _int_value(cross_plane_gate_summary, "claims_allowed"),
            "cross_plane_proof_gate_claims_blocked": _int_value(cross_plane_gate_summary, "claims_blocked"),
            "cross_plane_proof_gate_open_gap_ids": cross_plane_gate_context.get("open_gap_ids", []),
            "cross_plane_proof_gate_next_action_ids": cross_plane_gate_context.get("next_action_ids", []),
            "cross_plane_proof_gate_blocker_ids": cross_plane_gate_blocker_ids,
            "external_settlement_handoff_available": artifacts["external_settlement_handoff"]["loaded"] is True,
            "external_settlement_handoff_clear": external_handoff_local_ready,
            "external_settlement_handoff_decision": (external_handoff or {}).get("handoff_decision"),
            "external_settlement_handoff_ready_for_completion_rerun": (external_handoff or {}).get(
                "ready_for_completion_rerun"
            ),
            "external_settlement_capture_preflight_decision": external_handoff_summary.get(
                "capture_preflight_decision"
            ),
            "external_settlement_handoff_source_errors_total": _int_value(
                external_handoff_summary,
                "source_errors_total",
            ),
            "external_settlement_handoff_missing_inputs_total": _int_value(
                external_handoff_summary,
                "missing_inputs_total",
            ),
            "external_settlement_handoff_operator_actions_total": _int_value(
                external_handoff_summary,
                "operator_actions_total",
            ),
            "external_settlement_handoff_operator_commands_total": _int_value(
                external_handoff_summary,
                "operator_commands_total",
            ),
            "external_settlement_handoff_operator_command_entrypoints_missing": _int_value(
                external_handoff_summary,
                "operator_command_entrypoints_missing",
            ),
            "external_settlement_handoff_operator_command_surface_ready": external_handoff_summary.get(
                "operator_command_surface_ready"
            ),
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": _int_value(
                external_handoff_summary,
                "operator_commands_with_shell_redirection_placeholders",
            ),
            "external_settlement_handoff_operator_command_shell_surface_ready": external_handoff_summary.get(
                "operator_command_shell_surface_ready"
            ),
            "x0t_governance_execute_readiness_available": artifacts["governance_execute_readiness"]["loaded"] is True,
            "x0t_governance_execute_decision": (governance_readiness or {}).get("decision"),
            "x0t_governance_execute_ready_now": governance_readiness_summary.get("execute_ready_now"),
            "x0t_governance_proposal_executed": governance_proposal_executed,
            "x0t_governance_state_label": _value(governance_readiness, "proposal_state.state_label"),
            "x0t_governance_next_executable_after_utc": governance_readiness_summary.get("next_executable_after_utc"),
            "x0t_governance_seconds_until_earliest_execution_by_block_time": _value(
                governance_readiness,
                "timelock.seconds_until_earliest_execution_by_block_time",
            ),
            "x0t_governance_execute_handoff_available": artifacts["governance_execute_handoff"]["loaded"] is True,
            "x0t_governance_execute_handoff_clear": governance_handoff_local_ready,
            "x0t_governance_execute_handoff_decision": (governance_handoff or {}).get("handoff_decision"),
            "x0t_governance_execute_handoff_actionable": (governance_handoff or {}).get("handoff_actionable"),
            "x0t_governance_ready_for_operator_execute": (governance_handoff or {}).get(
                "ready_for_operator_execute"
            ),
            "x0t_governance_execute_handoff_missing_inputs_total": _int_value(
                governance_handoff_summary,
                "missing_inputs_total",
            ),
            "x0t_governance_execute_handoff_source_errors_total": _int_value(
                governance_handoff_summary,
                "source_errors_total",
            ),
            "x0t_governance_execute_handoff_operator_actions_total": _int_value(
                governance_handoff_summary,
                "operator_actions_total",
            ),
            "x0t_governance_execute_handoff_operator_commands_total": _int_value(
                governance_handoff_summary,
                "operator_commands_total",
            ),
            "x0t_governance_execute_handoff_operator_command_entrypoints_missing": _int_value(
                governance_handoff_summary,
                "operator_command_entrypoints_missing",
            ),
            "x0t_governance_execute_handoff_operator_command_surface_ready": governance_handoff_summary.get(
                "operator_command_surface_ready"
            ),
            "x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders": _int_value(
                governance_handoff_summary,
                "operator_commands_with_shell_redirection_placeholders",
            ),
            "x0t_governance_execute_handoff_operator_command_shell_surface_ready": governance_handoff_summary.get(
                "operator_command_shell_surface_ready"
            ),
            "x0t_governance_execute_handoff_operator_sequence_ready": governance_handoff_summary.get(
                "operator_sequence_ready"
            ),
            "current_raw_files_expected": raw_expected,
            "current_raw_files_installed": _int_value(return_summary, "raw_files_staged"),
            "raw_install_claim_source": "return_acceptance",
            "pipeline_raw_files_reported_installed": _int_value(pipeline_summary, "raw_files_installed"),
            "return_acceptance_raw_files_staged": _int_value(return_summary, "raw_files_staged"),
            "return_acceptance_raw_files_local_observation": _int_value(return_summary, "raw_files_local_observation"),
            "raw_inventory_files_total": _int_value(raw_summary, "files_total"),
            "raw_inventory_usable_for_goal_completion": _int_value(raw_summary, "usable_for_goal_completion_files"),
            "raw_inventory_classification_counts": raw_summary.get("classification_counts", {}),
            "raw_operator_packet_files_total": _int_value(raw_packet_summary, "raw_files_total"),
            "raw_operator_packet_files_production_ready": _int_value(
                raw_packet_summary,
                "operator_bundle_files_production_ready",
            ),
            "raw_operator_packet_files_replacement_required": _int_value(
                raw_packet_summary,
                "operator_bundle_files_replacement_required",
            ),
            "raw_operator_packet_readiness_decision": raw_packet_summary.get("raw_readiness_decision"),
            "raw_operator_packet_readiness_ready_for_collectors": raw_packet_summary.get(
                "raw_readiness_ready_for_collectors"
            ),
            "raw_operator_packet_readiness_collectors_ready": _int_value(
                raw_packet_summary,
                "raw_readiness_collectors_ready",
            ),
            "raw_operator_packet_readiness_collectors_blocked": _int_value(
                raw_packet_summary,
                "raw_readiness_collectors_blocked",
            ),
            "raw_operator_packet_readiness_collectors_total": _int_value(
                raw_packet_summary,
                "raw_readiness_collectors_total",
            ),
            "raw_operator_packet_readiness_raw_files_ready": _int_value(
                raw_packet_summary,
                "raw_readiness_raw_files_ready",
            ),
            "raw_operator_packet_readiness_raw_files_local_observation": _int_value(
                raw_packet_summary,
                "raw_readiness_raw_files_local_observation",
            ),
            "raw_operator_packet_readiness_raw_files_total": _int_value(
                raw_packet_summary,
                "raw_readiness_raw_files_total",
            ),
            "raw_operator_packet_production_ready_blocked_by_raw_readiness": raw_packet_summary.get(
                "production_ready_blocked_by_raw_readiness"
            ),
            "semantic_blocking_items_total": _int_value(semantic_summary, "blocking_items_total"),
            "semantic_preflight_errors_total": _int_value(semantic_summary, "semantic_preflight_errors_total"),
            "completion_local_wiring_passed": completion_summary.get("local_wiring_passed", False),
            "completion_production_readiness_passed": completion_summary.get("production_readiness_passed", False),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "Integration Spine Objective Coverage Audit",
        f"completion_decision: {report.get('completion_decision')}",
        f"goal_can_be_marked_complete: {report.get('goal_can_be_marked_complete')}",
        f"local_integration_ready: {report.get('local_integration_ready')}",
        f"production_ready: {report.get('production_ready')}",
        f"coverage_rows_blocking: {summary.get('coverage_rows_blocking')}",
        f"cross_plane_proof_gate_allowed: {summary.get('cross_plane_proof_gate_allowed')}",
        f"current_raw_files_installed: {summary.get('current_raw_files_installed')}",
        f"raw_install_claim_source: {summary.get('raw_install_claim_source')}",
        f"return_acceptance_raw_files_local_observation: {summary.get('return_acceptance_raw_files_local_observation')}",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine objective coverage audit")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
    write_json(_resolve(root, args.output_json), report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_complete and report["completion_decision"] != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
