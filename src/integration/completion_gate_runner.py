"""Read-only completion gate runner for the integration spine.

The runner joins the current production input, consistency, closeout, final
review, coverage, and completion audit shards. It replaces the old
source-restored runner artifact with a repo-generated fail-closed report. It
does not execute collectors, stage evidence, contact live systems, mutate
runtime, submit transactions, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
DEFAULT_PRODUCTION_INPUT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_PRODUCTION_INPUT_RETURN_PACKET = ".tmp/validation-shards/integration-spine-production-input-return-packet-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_REQUIRED_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_ROLLUP_CONTRACT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_CLOSEOUT_REVIEW = ".tmp/validation-shards/integration-spine-production-closeout-review-current.json"
DEFAULT_CLOSURE_PREFLIGHT = ".tmp/validation-shards/integration-spine-production-closure-preflight-current.json"
DEFAULT_FINAL_REVIEW = ".tmp/validation-shards/integration-spine-production-final-review-current.json"
DEFAULT_OBJECTIVE_COVERAGE = ".tmp/validation-shards/integration-spine-objective-coverage-audit-current.json"
DEFAULT_COMPLETION_AUDIT = ".tmp/validation-shards/integration-spine-completion-audit-current.json"
DEFAULT_CURRENT_ROLLUP = ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
DEFAULT_PRODUCTION_GAP_INDEX = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_GOVERNANCE_EXECUTE_READINESS = ".tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json"


@dataclass(frozen=True)
class SourceSpec:
    label: str
    path: str
    decision_keys: List[str]
    ready_decision: str
    ready_path: str


SOURCE_SPECS = [
    SourceSpec(
        "production_input_pipeline",
        DEFAULT_PRODUCTION_INPUT_PIPELINE,
        ["pipeline_decision", "decision"],
        "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
        "ready",
    ),
    SourceSpec(
        "required_evidence_consistency",
        DEFAULT_REQUIRED_CONSISTENCY,
        ["decision"],
        "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR",
        "production_ready",
    ),
    SourceSpec(
        "rollup_approval_contract",
        DEFAULT_ROLLUP_CONTRACT,
        ["decision"],
        "ROLLUP_APPROVAL_READY",
        "ready",
    ),
    SourceSpec(
        "production_closeout_review",
        DEFAULT_CLOSEOUT_REVIEW,
        ["decision"],
        "CLOSEOUT_REVIEW_READY",
        "ready",
    ),
    SourceSpec(
        "closure_preflight",
        DEFAULT_CLOSURE_PREFLIGHT,
        ["decision"],
        "PREFLIGHT_READY_FOR_FINAL_REVIEW",
        "ready",
    ),
    SourceSpec(
        "final_review",
        DEFAULT_FINAL_REVIEW,
        ["decision"],
        "FINAL_REVIEW_READY",
        "ready",
    ),
    SourceSpec(
        "objective_coverage",
        DEFAULT_OBJECTIVE_COVERAGE,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "completion_audit",
        DEFAULT_COMPLETION_AUDIT,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "current_rollup",
        DEFAULT_CURRENT_ROLLUP,
        ["completion_decision", "decision"],
        "COMPLETE",
        "goal_can_be_marked_complete",
    ),
    SourceSpec(
        "production_gap_index",
        DEFAULT_PRODUCTION_GAP_INDEX,
        ["decision"],
        "NO_PRODUCTION_EVIDENCE_GAPS",
        "goal_can_be_marked_complete",
    ),
]


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
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _value(data: Optional[Dict[str, Any]], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _first_present(*lookups: tuple[Dict[str, Any], str], default: Any = None) -> Any:
    for data, key in lookups:
        if key in data:
            return data.get(key)
    return default


def _first_int(*lookups: tuple[Dict[str, Any], str]) -> int:
    value = _first_present(*lookups)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _source_decision(data: Optional[Dict[str, Any]], keys: Iterable[str]) -> str:
    for key in keys:
        value = (data or {}).get(key)
        if value:
            return str(value)
    return ""


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _source_report(root: Path, spec: SourceSpec) -> Dict[str, Any]:
    data = _read_json(_resolve(root, spec.path))
    if data is None:
        return {
            "label": spec.label,
            "path": spec.path,
            "status": "MISSING",
            "ok": False,
            "decision": "",
            "expected_decision": spec.ready_decision,
            "ready": False,
            "errors": [f"missing or unreadable source artifact: {spec.path}"],
        }
    decision = _source_decision(data, spec.decision_keys)
    ready = (
        data.get("status") == "VERIFIED HERE"
        and data.get("ok") is True
        and decision == spec.ready_decision
        and _value(data, spec.ready_path) is True
    )
    errors: List[str] = []
    if data.get("status") != "VERIFIED HERE":
        errors.append("source status must be VERIFIED HERE")
    if data.get("ok") is not True:
        errors.append("source ok must be true")
    if decision != spec.ready_decision:
        errors.append(f"decision must be {spec.ready_decision}")
    if _value(data, spec.ready_path) is not True:
        errors.append(f"{spec.ready_path} must be true")
    return {
        "label": spec.label,
        "path": spec.path,
        "schema_version": data.get("schema_version", ""),
        "status": data.get("status", ""),
        "ok": data.get("ok"),
        "decision": decision,
        "expected_decision": spec.ready_decision,
        "ready": ready,
        "errors": [] if ready else errors,
    }


def build_report(root: Path) -> Dict[str, Any]:
    source_reports = [_source_report(root, spec) for spec in SOURCE_SPECS]
    source_errors = [
        error
        for report in source_reports
        for error in report.get("errors", [])
        if report.get("status") == "MISSING"
        or error.startswith("source status")
        or error.startswith("source ok")
    ]
    steps_ready = sum(1 for report in source_reports if report.get("ready") is True)
    steps_total = len(source_reports)
    ready = not source_errors and steps_ready == steps_total

    pipeline = _read_json(root / DEFAULT_PRODUCTION_INPUT_PIPELINE) or {}
    pipeline_summary = _summary(pipeline)
    return_packet = _read_json(root / DEFAULT_PRODUCTION_INPUT_RETURN_PACKET)
    return_packet_summary = _summary(return_packet)
    return_acceptance = _read_json(root / DEFAULT_RETURN_ACCEPTANCE) or {}
    return_summary = _summary(return_acceptance)
    consistency = _read_json(root / DEFAULT_REQUIRED_CONSISTENCY) or {}
    consistency_summary = _summary(consistency)
    closeout = _read_json(root / DEFAULT_CLOSEOUT_REVIEW) or {}
    closeout_summary = _summary(closeout)
    coverage = _read_json(root / DEFAULT_OBJECTIVE_COVERAGE) or {}
    coverage_summary = _summary(coverage)
    completion = _read_json(root / DEFAULT_COMPLETION_AUDIT) or {}
    completion_summary = _summary(completion)
    current_rollup = _read_json(root / DEFAULT_CURRENT_ROLLUP) or {}
    current_rollup_summary = _summary(current_rollup)
    governance_execute = _read_json(root / DEFAULT_GOVERNANCE_EXECUTE_READINESS) or {}
    governance_summary = _summary(governance_execute)

    raw_expected = _int_value(return_summary, "raw_files_expected") or _int_value(pipeline_summary, "raw_files_expected")
    raw_staged = _int_value(return_summary, "raw_files_staged")
    external_ready = return_summary.get("external_settlement_live_rpc_ready") is True
    governance_proposal_state = governance_execute.get("proposal_state", {})
    if not isinstance(governance_proposal_state, dict):
        governance_proposal_state = {}
    governance_timelock = governance_execute.get("timelock", {})
    if not isinstance(governance_timelock, dict):
        governance_timelock = {}
    governance_executed = (
        governance_execute.get("decision") == "ALREADY_EXECUTED"
        and governance_proposal_state.get("executed") is True
        and governance_proposal_state.get("vetoed") is False
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-completion-gate-runner-v5-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "completion_decision": "COMPLETE" if ready else "NOT_COMPLETE",
        "goal_can_be_marked_complete": ready,
        "claim_boundary": (
            "Repo-generated read-only completion gate runner. It joins current gate artifacts "
            "and refuses completion until every production evidence gate is ready. It does not "
            "run collectors, stage files, contact live systems, mutate runtime, submit "
            "transactions, or close /goal."
        ),
        "source_artifacts": [spec.path for spec in SOURCE_SPECS]
        + [
            DEFAULT_PRODUCTION_INPUT_RETURN_PACKET,
            DEFAULT_RETURN_ACCEPTANCE,
            DEFAULT_GOVERNANCE_EXECUTE_READINESS,
        ],
        "source_errors": source_errors,
        "source_reports": source_reports,
        "not_verified_yet": []
        if ready
        else [
            "external X0T settlement live RPC receipt is ready",
            f"{raw_expected} raw evidence files are replaced by production-grade retained evidence",
            "X0T governance proposal execute receipt and final Executed state are retained",
            "objective coverage, required consistency, rollup, closeout, final review, and completion audit are complete",
        ],
        "summary": {
            "steps_total": steps_total,
            "steps_ready": steps_ready,
            "steps_blocked_expected": steps_total - steps_ready,
            "steps_failed_unexpected": len(source_errors),
            "production_input_blocking_inputs_total": pipeline_summary.get("blocking_inputs_total", 0),
            "production_input_blocking_external_inputs": pipeline_summary.get("blocking_external_inputs", 0),
            "production_input_blocking_raw_inputs": pipeline_summary.get("blocking_raw_inputs", 0),
            "production_input_return_packet_available": return_packet is not None,
            "production_input_return_packet_decision": (return_packet or {}).get("decision", ""),
            "production_input_return_packet_blocking_inputs_total": _int_value(
                return_packet_summary,
                "blocking_inputs_total",
            ),
            "production_input_return_packet_blocking_raw_inputs": _int_value(
                return_packet_summary,
                "blocking_raw_inputs",
            ),
            "production_input_return_packet_blocking_external_inputs": _int_value(
                return_packet_summary,
                "blocking_external_inputs",
            ),
            "production_input_return_packet_blocking_inputs_operator_input_required": _int_value(
                return_packet_summary,
                "blocking_inputs_operator_input_required",
            ),
            "production_input_return_packet_blocking_inputs_generic_operator_required": _int_value(
                return_packet_summary,
                "blocking_inputs_generic_operator_required",
            ),
            "production_input_return_packet_operator_next_actions_total": _int_value(
                return_packet_summary,
                "operator_next_actions_total",
            ),
            "production_input_return_packet_operator_next_actions_operator_input_required": _int_value(
                return_packet_summary,
                "operator_next_actions_operator_input_required",
            ),
            "production_input_return_packet_operator_next_actions_generic_blocking": _int_value(
                return_packet_summary,
                "operator_next_actions_generic_blocking",
            ),
            "production_input_return_packet_raw_files_expected": _int_value(
                return_packet_summary,
                "raw_files_expected",
            ),
            "production_input_return_packet_raw_files_missing": _int_value(
                return_packet_summary,
                "raw_files_missing",
            ),
            "production_input_return_packet_raw_files_local_observation": _int_value(
                return_packet_summary,
                "raw_files_local_observation",
            ),
            "production_input_return_packet_external_artifacts_operator_required": _int_value(
                return_packet_summary,
                "external_artifacts_operator_required",
            ),
            "collector_evidence_blockers": pipeline_summary.get("collector_evidence_blockers", 0),
            "external_settlement_ready": external_ready,
            "external_settlement_live_rpc_ready": external_ready,
            "raw_install_claim_source": "return_acceptance",
            "raw_required_evidence_files_total": raw_expected,
            "raw_required_evidence_files_ready": raw_staged,
            "required_evidence_files_total": consistency_summary.get("required_evidence_files_total", 0),
            "required_evidence_files_ready": consistency_summary.get("required_evidence_files_ready", 0),
            "raw_operator_packet_readiness_decision": consistency_summary.get(
                "raw_operator_packet_readiness_decision",
                coverage_summary.get("raw_operator_packet_readiness_decision"),
            ),
            "raw_operator_packet_readiness_ready_for_collectors": consistency_summary.get(
                "raw_operator_packet_readiness_ready_for_collectors",
                coverage_summary.get("raw_operator_packet_readiness_ready_for_collectors"),
            ),
            "raw_operator_packet_readiness_collectors_ready": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_ready",
                coverage_summary.get("raw_operator_packet_readiness_collectors_ready"),
            ),
            "raw_operator_packet_readiness_collectors_blocked": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_blocked",
                coverage_summary.get("raw_operator_packet_readiness_collectors_blocked"),
            ),
            "raw_operator_packet_readiness_collectors_total": consistency_summary.get(
                "raw_operator_packet_readiness_collectors_total",
                coverage_summary.get("raw_operator_packet_readiness_collectors_total"),
            ),
            "raw_operator_packet_readiness_raw_files_ready": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_ready",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_ready"),
            ),
            "raw_operator_packet_readiness_raw_files_local_observation": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_local_observation",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_local_observation"),
            ),
            "raw_operator_packet_readiness_raw_files_total": consistency_summary.get(
                "raw_operator_packet_readiness_raw_files_total",
                coverage_summary.get("raw_operator_packet_readiness_raw_files_total"),
            ),
            "raw_operator_packet_production_ready_blocked_by_raw_readiness": consistency_summary.get(
                "raw_operator_packet_production_ready_blocked_by_raw_readiness",
                coverage_summary.get("raw_operator_packet_production_ready_blocked_by_raw_readiness"),
            ),
            "external_required_evidence_files_total": consistency_summary.get("external_required_evidence_files_total", 0),
            "external_required_evidence_files_ready": consistency_summary.get("external_required_evidence_files_ready", 0),
            "current_raw_files_installed": raw_staged,
            "pipeline_raw_files_reported_installed": pipeline_summary.get("raw_files_installed", 0),
            "coverage_raw_files_reported_installed": coverage_summary.get("current_raw_files_installed", 0),
            "return_acceptance_raw_files_staged": raw_staged,
            "return_acceptance_raw_files_local_observation": return_summary.get("raw_files_local_observation", 0),
            "completion_checklist_total": completion_summary.get("checklist_total", 0),
            "completion_checklist_passed": completion_summary.get("checklist_passed", 0),
            "completion_checklist_blocking": completion_summary.get("checklist_blocking", 0),
            "completion_local_wiring_passed": completion_summary.get("local_wiring_passed", False),
            "completion_production_readiness_passed": completion_summary.get("production_readiness_passed", False),
            "external_settlement_handoff_clear": completion_summary.get("external_settlement_handoff_clear"),
            "external_settlement_handoff_decision": completion_summary.get("external_settlement_handoff_decision"),
            "external_settlement_handoff_ready_for_completion_rerun": completion_summary.get(
                "external_settlement_handoff_ready_for_completion_rerun"
            ),
            "external_settlement_capture_preflight_decision": completion_summary.get(
                "external_settlement_capture_preflight_decision"
            ),
            "external_settlement_handoff_operator_command_entrypoints_missing": completion_summary.get(
                "external_settlement_handoff_operator_command_entrypoints_missing"
            ),
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": completion_summary.get(
                "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "external_settlement_handoff_operator_command_shell_surface_ready": completion_summary.get(
                "external_settlement_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_governance_execute_decision": governance_execute.get(
                "decision",
                completion_summary.get("x0t_governance_execute_decision"),
            ),
            "x0t_governance_execute_ready_now": governance_summary.get(
                "execute_ready_now",
                completion_summary.get("x0t_governance_execute_ready_now"),
            ),
            "x0t_governance_execute_handoff_decision": completion_summary.get(
                "x0t_governance_execute_handoff_decision"
            ),
            "x0t_governance_execute_handoff_actionable": completion_summary.get(
                "x0t_governance_execute_handoff_actionable"
            ),
            "x0t_governance_ready_for_operator_execute": completion_summary.get(
                "x0t_governance_ready_for_operator_execute"
            ),
            "x0t_governance_handoff_operator_actions_total": completion_summary.get(
                "x0t_governance_handoff_operator_actions_total"
            ),
            "x0t_governance_handoff_operator_commands_total": completion_summary.get(
                "x0t_governance_handoff_operator_commands_total"
            ),
            "x0t_governance_handoff_operator_command_entrypoints_missing": completion_summary.get(
                "x0t_governance_handoff_operator_command_entrypoints_missing"
            ),
            "x0t_governance_handoff_operator_command_surface_ready": completion_summary.get(
                "x0t_governance_handoff_operator_command_surface_ready"
            ),
            "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": completion_summary.get(
                "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders"
            ),
            "x0t_governance_handoff_operator_command_shell_surface_ready": completion_summary.get(
                "x0t_governance_handoff_operator_command_shell_surface_ready"
            ),
            "x0t_governance_handoff_operator_sequence_ready": completion_summary.get(
                "x0t_governance_handoff_operator_sequence_ready"
            ),
            "x0t_governance_proposal_executed": governance_executed,
            "x0t_governance_state_label": governance_proposal_state.get(
                "state_label",
                completion_summary.get("x0t_governance_state_label"),
            ),
            "x0t_governance_next_executable_after_utc": governance_summary.get(
                "next_executable_after_utc",
                completion_summary.get("x0t_governance_next_executable_after_utc"),
            ),
            "x0t_governance_seconds_until_earliest_execution_by_block_time": governance_timelock.get(
                "seconds_until_earliest_execution_by_block_time",
                completion_summary.get("x0t_governance_seconds_until_earliest_execution_by_block_time"),
            ),
            "x0t_contract_handoff_available": _first_present(
                (closeout_summary, "x0t_contract_handoff_available"),
                (completion_summary, "x0t_contract_handoff_available"),
                (coverage_summary, "closeout_x0t_contract_handoff_available"),
                default=False,
            ),
            "x0t_contract_handoff_decision": _first_present(
                (closeout_summary, "x0t_contract_handoff_decision"),
                (completion_summary, "x0t_contract_handoff_decision"),
                (coverage_summary, "closeout_x0t_contract_handoff_decision"),
                default="",
            ),
            "x0t_contract_handoff_deployment_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_deployment_ready"),
                (completion_summary, "x0t_contract_handoff_deployment_ready"),
                (coverage_summary, "closeout_x0t_contract_handoff_deployment_ready"),
                default=False,
            ),
            "x0t_contract_handoff_approval_value_required": _first_present(
                (closeout_summary, "x0t_contract_handoff_approval_value_required"),
                (completion_summary, "x0t_contract_handoff_approval_value_required"),
                default="",
            ),
            "x0t_contract_handoff_missing_inputs_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_missing_inputs_total"),
                (completion_summary, "x0t_contract_handoff_missing_inputs_total"),
            ),
            "x0t_contract_handoff_operator_actions_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_actions_total"),
                (completion_summary, "x0t_contract_handoff_operator_actions_total"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_actions_total"),
            ),
            "x0t_contract_handoff_operator_approval_required_actions_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_approval_required_actions_total"),
                (completion_summary, "x0t_contract_handoff_operator_approval_required_actions_total"),
            ),
            "x0t_contract_handoff_operator_commands_total": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_commands_total"),
                (completion_summary, "x0t_contract_handoff_operator_commands_total"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_commands_total"),
            ),
            "x0t_contract_handoff_operator_command_entrypoints_missing": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_command_entrypoints_missing"),
                (completion_summary, "x0t_contract_handoff_operator_command_entrypoints_missing"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_command_entrypoints_missing"),
            ),
            "x0t_contract_handoff_operator_command_surface_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_command_surface_ready"),
                (completion_summary, "x0t_contract_handoff_operator_command_surface_ready"),
                default=False,
            ),
            "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": _first_int(
                (closeout_summary, "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"),
                (completion_summary, "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders"),
            ),
            "x0t_contract_handoff_operator_command_shell_surface_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_command_shell_surface_ready"),
                (completion_summary, "x0t_contract_handoff_operator_command_shell_surface_ready"),
                default=False,
            ),
            "x0t_contract_handoff_operator_sequence_ready": _first_present(
                (closeout_summary, "x0t_contract_handoff_operator_sequence_ready"),
                (completion_summary, "x0t_contract_handoff_operator_sequence_ready"),
                (coverage_summary, "closeout_x0t_contract_handoff_operator_sequence_ready"),
                default=False,
            ),
            "live_rollout_handoff_available": _first_present(
                (closeout_summary, "live_rollout_handoff_available"),
                (completion_summary, "live_rollout_handoff_available"),
                (coverage_summary, "closeout_live_rollout_handoff_available"),
                default=False,
            ),
            "live_rollout_handoff_decision": _first_present(
                (closeout_summary, "live_rollout_handoff_decision"),
                (completion_summary, "live_rollout_handoff_decision"),
                (coverage_summary, "closeout_live_rollout_handoff_decision"),
                default="",
            ),
            "live_rollout_handoff_ready_for_completion_rerun": _first_present(
                (closeout_summary, "live_rollout_handoff_ready_for_completion_rerun"),
                (completion_summary, "live_rollout_handoff_ready_for_completion_rerun"),
                (coverage_summary, "closeout_live_rollout_handoff_ready_for_completion_rerun"),
                default=False,
            ),
            "live_rollout_handoff_can_close_image_digests_blocker": _first_present(
                (closeout_summary, "live_rollout_handoff_can_close_image_digests_blocker"),
                (completion_summary, "live_rollout_handoff_can_close_image_digests_blocker"),
                default=False,
            ),
            "live_rollout_handoff_missing_inputs_total": _first_int(
                (closeout_summary, "live_rollout_handoff_missing_inputs_total"),
                (completion_summary, "live_rollout_handoff_missing_inputs_total"),
            ),
            "live_rollout_handoff_operator_actions_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_actions_total"),
                (completion_summary, "live_rollout_handoff_operator_actions_total"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_actions_total"),
            ),
            "live_rollout_handoff_operator_input_required_actions_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_input_required_actions_total"),
                (completion_summary, "live_rollout_handoff_operator_input_required_actions_total"),
            ),
            "live_rollout_handoff_operator_commands_total": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_commands_total"),
                (completion_summary, "live_rollout_handoff_operator_commands_total"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_commands_total"),
            ),
            "live_rollout_handoff_operator_command_entrypoints_missing": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_command_entrypoints_missing"),
                (completion_summary, "live_rollout_handoff_operator_command_entrypoints_missing"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_command_entrypoints_missing"),
            ),
            "live_rollout_handoff_operator_command_surface_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_command_surface_ready"),
                (completion_summary, "live_rollout_handoff_operator_command_surface_ready"),
                default=False,
            ),
            "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _first_int(
                (closeout_summary, "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"),
                (completion_summary, "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders"),
            ),
            "live_rollout_handoff_operator_command_shell_surface_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_command_shell_surface_ready"),
                (completion_summary, "live_rollout_handoff_operator_command_shell_surface_ready"),
                default=False,
            ),
            "live_rollout_handoff_operator_sequence_ready": _first_present(
                (closeout_summary, "live_rollout_handoff_operator_sequence_ready"),
                (completion_summary, "live_rollout_handoff_operator_sequence_ready"),
                (coverage_summary, "closeout_live_rollout_handoff_operator_sequence_ready"),
                default=False,
            ),
            "semantic_blocking_items_total": coverage_summary.get(
                "semantic_blocking_items_total",
                current_rollup_summary.get("semantic_blocking_items_total", 0),
            ),
            "semantic_preflight_errors_total": coverage_summary.get(
                "semantic_preflight_errors_total",
                current_rollup_summary.get("semantic_preflight_errors_total", 0),
            ),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Completion Gate Runner",
            f"completion_decision: {report.get('completion_decision')}",
            f"goal_can_be_marked_complete: {report.get('goal_can_be_marked_complete')}",
            f"steps_ready: {summary.get('steps_ready')}/{summary.get('steps_total')}",
            f"current_raw_files_installed: {summary.get('current_raw_files_installed')}",
            f"raw_install_claim_source: {summary.get('raw_install_claim_source')}",
            f"return_acceptance_raw_files_local_observation: {summary.get('return_acceptance_raw_files_local_observation')}",
            f"x0t_governance_execute_decision: {summary.get('x0t_governance_execute_decision')}",
            f"x0t_governance_proposal_executed: {summary.get('x0t_governance_proposal_executed')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine completion gate runner report")
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
