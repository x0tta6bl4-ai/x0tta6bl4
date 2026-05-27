"""Read-only production closeout review for the integration spine.

This report sits after input staging, pipeline, rollup approval, and required
evidence consistency. It is a local review gate only: it summarizes whether the
current evidence chain is ready for closeout and refuses to complete the goal
until the upstream reports are production-ready.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


DEFAULT_INPUT_MANIFEST = ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_INPUT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_ROLLUP_CONTRACT = ".tmp/validation-shards/integration-spine-rollup-approval-contract-current.json"
DEFAULT_REQUIRED_EVIDENCE_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_CURRENT_ROLLUP = ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
DEFAULT_PRODUCTION_GAP_INDEX = ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-closeout-review-current.json"
DEFAULT_CLOSURE_PREFLIGHT_OUTPUT = ".tmp/validation-shards/integration-spine-production-closure-preflight-current.json"
DEFAULT_FINAL_REVIEW_OUTPUT = ".tmp/validation-shards/integration-spine-production-final-review-current.json"

CURRENT_ROLLUP_CONTEXT_KEYS = [
    "top_blockers_total",
    "top_blockers_blocking",
    "top_blockers_operator_input_required",
    "top_blockers_operator_approval_required",
    "external_settlement_handoff_clear",
    "external_settlement_handoff_decision",
    "x0t_governance_execute_readiness_available",
    "x0t_governance_execute_readiness_clear",
    "x0t_governance_execute_decision",
    "x0t_governance_execute_ready_now",
    "x0t_governance_proposal_executed",
    "x0t_governance_state_label",
    "x0t_governance_next_executable_after_utc",
    "x0t_governance_seconds_until_earliest_execution_by_block_time",
    "x0t_governance_execute_handoff_available",
    "x0t_governance_execute_handoff_clear",
    "x0t_governance_execute_handoff_decision",
    "x0t_governance_execute_handoff_actionable",
    "x0t_governance_ready_for_operator_execute",
    "x0t_contract_readiness_available",
    "x0t_contract_surface_clear",
    "x0t_contract_readiness_decision",
    "x0t_contract_readiness_clear",
    "x0t_contract_build_env_ready",
    "x0t_contract_build_verification_ready",
    "x0t_contract_bridge_source_ready",
    "x0t_contract_deployment_config_ready",
    "x0t_contract_operator_configs_ready",
    "x0t_contract_missing_inputs_total",
    "x0t_bridge_config_available",
    "x0t_bridge_config_decision",
    "x0t_bridge_config_ready",
    "x0t_bridge_address_input_ready",
    "x0t_bridge_configured_bridge_ready",
    "x0t_bridge_missing_inputs_total",
    "x0t_contract_deployment_ready",
    "image_digests_operator_handoff_decision",
    "image_digests_ready_for_completion_rerun",
    "image_digests_missing_inputs_total",
    "image_digests_operator_actions_total",
    "image_digests_operator_commands_total",
    "image_digests_operator_command_entrypoints_missing",
    "image_digests_operator_command_surface_ready",
    "image_digests_operator_commands_with_shell_redirection_placeholders",
    "image_digests_operator_command_shell_surface_ready",
]


@dataclass(frozen=True)
class SourceSpec:
    label: str
    display_path: str
    decision_keys: List[str]
    ready_check: Callable[[Dict[str, Any]], bool]
    expected_decision: str


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


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> Optional[int]:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_decision(data: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _status_ok(data: Dict[str, Any]) -> bool:
    return data.get("status") == "VERIFIED HERE" and data.get("ok") is True


def _input_manifest_ready(data: Dict[str, Any]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and data.get("decision") == "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW"
        and data.get("ready_for_production_closeout_review") is True
        and summary.get("ready_for_production_closeout_review") is True
        and summary.get("external_artifacts_ready") == summary.get("external_artifacts_required")
        and summary.get("raw_files_ready_for_integration") == summary.get("raw_files_required_for_integration")
        and summary.get("raw_files_blocking_for_integration") == 0
        and summary.get("external_artifacts_missing") == 0
    )


def _return_acceptance_ready(data: Dict[str, Any]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and data.get("ready_for_pipeline_install") is True
        and data.get("ready_to_stage") is True
        and summary.get("ready_for_pipeline_install") is True
        and summary.get("ready_to_stage") is True
        and summary.get("external_artifacts_operator_required") == 0
        and summary.get("raw_ready_to_stage") is True
        and summary.get("external_settlement_live_rpc_ready") is True
    )


def _input_pipeline_ready(data: Dict[str, Any]) -> bool:
    summary = _summary(data)
    raw_expected = summary.get("raw_files_expected")
    raw_installed = summary.get("raw_files_installed")
    return (
        _status_ok(data)
        and data.get("pipeline_decision") in {"READY_FOR_PRODUCTION_CLOSEOUT_REVIEW", "INPUT_PIPELINE_READY", "READY"}
        and summary.get("blocking_inputs_total") == 0
        and summary.get("blocking_external_inputs") == 0
        and summary.get("blocking_raw_inputs") == 0
        and summary.get("collector_evidence_blockers") == 0
        and raw_expected is not None
        and raw_expected == raw_installed
        and summary.get("external_settlement_ready") is True
    )


def _rollup_contract_ready(data: Dict[str, Any]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and data.get("decision") == "ROLLUP_APPROVAL_READY"
        and data.get("ready") is True
        and summary.get("source_errors_total") == 0
        and summary.get("evidence_files_total", 0) > 0
        and summary.get("evidence_files_valid") == summary.get("evidence_files_total")
        and summary.get("ready_for_closeout_review") is True
    )


def _required_evidence_consistency_ready(data: Dict[str, Any]) -> bool:
    summary = _summary(data)
    return (
        _status_ok(data)
        and data.get("valid") is True
        and data.get("production_ready") is True
        and data.get("decision") == "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR"
        and summary.get("errors_total") == 0
        and summary.get("required_evidence_files_total", 0) > 0
        and summary.get("required_evidence_files_ready") == summary.get("required_evidence_files_total")
    )


def _current_rollup_ready(data: Dict[str, Any]) -> bool:
    return data.get("goal_can_be_marked_complete") is True and data.get("completion_decision") == "COMPLETE"


def _current_rollup_context(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {key: summary.get(key) for key in CURRENT_ROLLUP_CONTEXT_KEYS}


SOURCE_SPECS = [
    SourceSpec(
        "input_manifest",
        DEFAULT_INPUT_MANIFEST,
        ["decision"],
        _input_manifest_ready,
        "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
    ),
    SourceSpec(
        "return_acceptance",
        DEFAULT_RETURN_ACCEPTANCE,
        ["decision", "acceptance_decision"],
        _return_acceptance_ready,
        "RETURN_ACCEPTANCE_READY",
    ),
    SourceSpec(
        "input_pipeline",
        DEFAULT_INPUT_PIPELINE,
        ["pipeline_decision", "decision"],
        _input_pipeline_ready,
        "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
    ),
    SourceSpec(
        "rollup_contract",
        DEFAULT_ROLLUP_CONTRACT,
        ["decision"],
        _rollup_contract_ready,
        "ROLLUP_APPROVAL_READY",
    ),
    SourceSpec(
        "required_evidence_consistency",
        DEFAULT_REQUIRED_EVIDENCE_CONSISTENCY,
        ["decision"],
        _required_evidence_consistency_ready,
        "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR",
    ),
    SourceSpec(
        "current_rollup",
        DEFAULT_CURRENT_ROLLUP,
        ["completion_decision"],
        _current_rollup_ready,
        "COMPLETE",
    ),
]


def _source_errors(data: Dict[str, Any], spec: SourceSpec, ready: bool, decision: str) -> List[str]:
    if ready:
        return []
    errors: List[str] = []
    if spec.label != "current_rollup" and data.get("status") != "VERIFIED HERE":
        errors.append("source report status must be VERIFIED HERE")
    if spec.label != "current_rollup" and data.get("ok") is not True:
        errors.append("source report ok must be true")
    if decision != spec.expected_decision:
        errors.append(f"decision must be {spec.expected_decision}")
    errors.append("source report is not ready for closeout")
    return errors


def _build_source_report(root: Path, spec: SourceSpec) -> Dict[str, Any]:
    path = root / spec.display_path
    data = _read_json(path)
    if data is None:
        return {
            "label": spec.label,
            "path": spec.display_path,
            "status": "MISSING",
            "ok": False,
            "decision": "",
            "expected_decision": spec.expected_decision,
            "ready": False,
            "source_error": f"missing or unreadable source report: {spec.display_path}",
            "errors": [f"missing or unreadable source report: {spec.display_path}"],
        }
    decision = _source_decision(data, spec.decision_keys)
    ready = spec.ready_check(data)
    return {
        "label": spec.label,
        "path": spec.display_path,
        "schema_version": data.get("schema_version", ""),
        "status": data.get("status", ""),
        "ok": data.get("ok"),
        "decision": decision,
        "expected_decision": spec.expected_decision,
        "ready": ready,
        "errors": _source_errors(data, spec, ready, decision),
    }


def _command_entrypoints_missing(commands: List[Dict[str, Any]]) -> int:
    return sum(1 for item in commands if item.get("entrypoint_exists") is False)


def _commands_with_shell_placeholders(commands: List[Dict[str, Any]]) -> int:
    return sum(1 for item in commands if item.get("shell_redirection_placeholder_detected") is True)


def _action_ids(actions: List[Dict[str, Any]]) -> set[str]:
    return {str(item.get("id")) for item in actions if item.get("id")}


def _command_action_ids(commands: List[Dict[str, Any]]) -> set[str]:
    return {str(item.get("action_id")) for item in commands if item.get("action_id")}


def _action_status_count(actions: List[Dict[str, Any]], status: str) -> int:
    return sum(1 for item in actions if item.get("status") == status)


def _command_surface_ready(commands: List[Dict[str, Any]]) -> bool:
    return bool(commands) and _command_entrypoints_missing(commands) == 0


def _command_shell_surface_ready(commands: List[Dict[str, Any]]) -> bool:
    return _commands_with_shell_placeholders(commands) == 0


def _governance_sequence_ready(handoff: Dict[str, Any]) -> bool:
    actions = _action_ids(_dicts(handoff.get("operator_next_actions")))
    commands = _command_action_ids(_dicts(handoff.get("operator_command_checks")))
    required = {"refresh_readiness", "execute_with_operator_approval", "rerun_completion_and_gap"}
    return required.issubset(actions) and required.issubset(commands)


def _external_sequence_ready(handoff: Dict[str, Any]) -> bool:
    actions = _action_ids(_dicts(handoff.get("operator_next_actions")))
    commands = _command_action_ids(_dicts(handoff.get("operator_command_checks")))
    required = {"preflight_capture_inputs", "verify_live_base_rpc"}
    return required.issubset(actions) and required.issubset(commands)


def _x0t_contract_sequence_ready(handoff: Dict[str, Any]) -> bool:
    actions = _action_ids(_dicts(handoff.get("operator_next_actions")))
    commands = _command_action_ids(_dicts(handoff.get("operator_command_checks")))
    required_actions = {
        "provide_bridge_address",
        "validate_bridge_address",
        "apply_bridge_address_with_operator_approval",
        "rerun_contract_readiness",
    }
    required_commands = {
        "validate_bridge_address",
        "apply_bridge_address_with_operator_approval",
        "rerun_contract_readiness",
    }
    return required_actions.issubset(actions) and required_commands.issubset(commands)


def _live_rollout_sequence_ready(handoff: Dict[str, Any]) -> bool:
    actions = _action_ids(_dicts(handoff.get("operator_next_actions")))
    commands = _command_action_ids(_dicts(handoff.get("operator_command_checks")))
    required_actions = {
        "render_template_pack",
        "return_digest_pinned_evidence",
        "verify_live_rollout_evidence_gate",
        "rerun_rollout_provenance",
        "rerun_current_evidence_rollup",
    }
    required_commands = {
        "render_template_pack",
        "verify_live_rollout_evidence_gate",
        "rerun_rollout_provenance",
        "rerun_current_evidence_rollup",
    }
    return required_actions.issubset(actions) and required_commands.issubset(commands)


def _copy_handoff(value: Any, *, source_artifact: str) -> Dict[str, Any]:
    handoff = _mapping(value)
    if not handoff:
        return {
            "available": False,
            "source_artifact": source_artifact,
            "missing_inputs": [],
            "operator_next_actions": [],
            "operator_command_checks": [],
        }
    copied = dict(handoff)
    copied["available"] = handoff.get("available") is True
    copied["source_artifact"] = source_artifact
    copied["missing_inputs"] = _dicts(handoff.get("missing_inputs"))
    copied["operator_next_actions"] = _dicts(handoff.get("operator_next_actions"))
    copied["operator_command_checks"] = _dicts(handoff.get("operator_command_checks"))
    return copied


def _build_operator_handoffs(root: Path) -> Dict[str, Any]:
    current_rollup = _read_json(root / DEFAULT_CURRENT_ROLLUP)
    current_handoffs = _mapping((current_rollup or {}).get("operator_handoffs"))
    gap_index = _read_json(root / DEFAULT_PRODUCTION_GAP_INDEX)
    if current_handoffs:
        live_rollout = current_handoffs.get("live_rollout_image_digests")
        live_rollout_source = DEFAULT_CURRENT_ROLLUP
        if not _mapping(live_rollout):
            live_rollout = (gap_index or {}).get("live_rollout_operator_handoff")
            live_rollout_source = DEFAULT_PRODUCTION_GAP_INDEX
        return {
            "source_artifact": DEFAULT_CURRENT_ROLLUP,
            "source_available": True,
            "source_error": "",
            "x0t_governance_execute": _copy_handoff(
                current_handoffs.get("x0t_governance_execute"),
                source_artifact=DEFAULT_CURRENT_ROLLUP,
            ),
            "external_settlement": _copy_handoff(
                current_handoffs.get("external_settlement"),
                source_artifact=DEFAULT_CURRENT_ROLLUP,
            ),
            "x0t_contract_deployment": _copy_handoff(
                (gap_index or {}).get("x0t_contract_operator_handoff"),
                source_artifact=DEFAULT_PRODUCTION_GAP_INDEX,
            ),
            "live_rollout_image_digests": _copy_handoff(
                live_rollout,
                source_artifact=live_rollout_source,
            ),
        }

    if gap_index is None:
        return {
            "source_artifact": DEFAULT_PRODUCTION_GAP_INDEX,
            "source_available": False,
            "source_error": f"missing or unreadable source report: {DEFAULT_PRODUCTION_GAP_INDEX}",
            "x0t_governance_execute": _copy_handoff({}, source_artifact=DEFAULT_PRODUCTION_GAP_INDEX),
            "external_settlement": _copy_handoff({}, source_artifact=DEFAULT_PRODUCTION_GAP_INDEX),
            "x0t_contract_deployment": _copy_handoff({}, source_artifact=DEFAULT_PRODUCTION_GAP_INDEX),
            "live_rollout_image_digests": _copy_handoff({}, source_artifact=DEFAULT_PRODUCTION_GAP_INDEX),
        }
    return {
        "source_artifact": DEFAULT_PRODUCTION_GAP_INDEX,
        "source_available": True,
        "source_error": "",
        "x0t_governance_execute": _copy_handoff(
            gap_index.get("x0t_governance_operator_handoff"),
            source_artifact=DEFAULT_PRODUCTION_GAP_INDEX,
        ),
        "external_settlement": _copy_handoff(
            gap_index.get("external_settlement_operator_handoff"),
            source_artifact=DEFAULT_PRODUCTION_GAP_INDEX,
        ),
        "x0t_contract_deployment": _copy_handoff(
            gap_index.get("x0t_contract_operator_handoff"),
            source_artifact=DEFAULT_PRODUCTION_GAP_INDEX,
        ),
        "live_rollout_image_digests": _copy_handoff(
            gap_index.get("live_rollout_operator_handoff"),
            source_artifact=DEFAULT_PRODUCTION_GAP_INDEX,
        ),
    }


def _operator_handoff_summary(operator_handoffs: Dict[str, Any]) -> Dict[str, Any]:
    governance = _mapping(operator_handoffs.get("x0t_governance_execute"))
    external = _mapping(operator_handoffs.get("external_settlement"))
    x0t_contract = _mapping(operator_handoffs.get("x0t_contract_deployment"))
    live_rollout = _mapping(operator_handoffs.get("live_rollout_image_digests"))
    governance_actions = _dicts(governance.get("operator_next_actions"))
    external_actions = _dicts(external.get("operator_next_actions"))
    x0t_contract_actions = _dicts(x0t_contract.get("operator_next_actions"))
    live_rollout_actions = _dicts(live_rollout.get("operator_next_actions"))
    governance_commands = _dicts(governance.get("operator_command_checks"))
    external_commands = _dicts(external.get("operator_command_checks"))
    x0t_contract_commands = _dicts(x0t_contract.get("operator_command_checks"))
    live_rollout_commands = _dicts(live_rollout.get("operator_command_checks"))
    return {
        "operator_handoff_source_available": operator_handoffs.get("source_available") is True,
        "operator_handoff_source_errors_total": 0 if operator_handoffs.get("source_available") is True else 1,
        "x0t_governance_handoff_available": governance.get("available") is True,
        "x0t_governance_handoff_actionable": governance.get("actionable") is True,
        "x0t_governance_handoff_ready_for_operator_execute": governance.get("ready_for_operator_execute") is True,
        "x0t_governance_handoff_approval_value_required": governance.get("approval_value_required", ""),
        "x0t_governance_handoff_missing_inputs_total": len(_dicts(governance.get("missing_inputs"))),
        "x0t_governance_handoff_operator_actions_total": len(governance_actions),
        "x0t_governance_handoff_operator_approval_required_actions_total": _action_status_count(
            governance_actions,
            "OPERATOR_APPROVAL_REQUIRED",
        ),
        "x0t_governance_handoff_operator_commands_total": len(governance_commands),
        "x0t_governance_handoff_operator_command_entrypoints_missing": _command_entrypoints_missing(governance_commands),
        "x0t_governance_handoff_operator_command_surface_ready": _command_surface_ready(governance_commands),
        "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": _commands_with_shell_placeholders(governance_commands),
        "x0t_governance_handoff_operator_command_shell_surface_ready": _command_shell_surface_ready(governance_commands),
        "x0t_governance_handoff_operator_sequence_ready": _governance_sequence_ready(governance),
        "external_settlement_handoff_available": external.get("available") is True,
        "external_settlement_handoff_ready_for_completion_rerun": external.get("ready_for_completion_rerun") is True,
        "external_settlement_capture_preflight_decision": external.get("capture_preflight_decision", ""),
        "external_settlement_capture_inputs_ready": external.get("capture_inputs_ready") is True,
        "external_settlement_handoff_missing_inputs_total": len(_dicts(external.get("missing_inputs"))),
        "external_settlement_handoff_operator_actions_total": len(external_actions),
        "external_settlement_handoff_operator_input_required_actions_total": _action_status_count(
            external_actions,
            "OPERATOR_INPUT_REQUIRED",
        ),
        "external_settlement_handoff_operator_commands_total": len(external_commands),
        "external_settlement_handoff_operator_command_entrypoints_missing": _command_entrypoints_missing(external_commands),
        "external_settlement_handoff_operator_command_surface_ready": _command_surface_ready(external_commands),
        "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": _commands_with_shell_placeholders(external_commands),
        "external_settlement_handoff_operator_command_shell_surface_ready": _command_shell_surface_ready(external_commands),
        "external_settlement_handoff_operator_sequence_ready": _external_sequence_ready(external),
        "x0t_contract_handoff_available": x0t_contract.get("available") is True,
        "x0t_contract_handoff_decision": x0t_contract.get("decision", ""),
        "x0t_contract_handoff_deployment_ready": x0t_contract.get("deployment_ready") is True,
        "x0t_contract_handoff_approval_value_required": x0t_contract.get("approval_value_required", ""),
        "x0t_contract_handoff_missing_inputs_total": len(_dicts(x0t_contract.get("missing_inputs"))),
        "x0t_contract_handoff_operator_actions_total": len(x0t_contract_actions),
        "x0t_contract_handoff_operator_approval_required_actions_total": _action_status_count(
            x0t_contract_actions,
            "OPERATOR_APPROVAL_REQUIRED",
        ),
        "x0t_contract_handoff_operator_commands_total": len(x0t_contract_commands),
        "x0t_contract_handoff_operator_command_entrypoints_missing": _command_entrypoints_missing(
            x0t_contract_commands
        ),
        "x0t_contract_handoff_operator_command_surface_ready": _command_surface_ready(x0t_contract_commands),
        "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": _commands_with_shell_placeholders(
            x0t_contract_commands
        ),
        "x0t_contract_handoff_operator_command_shell_surface_ready": _command_shell_surface_ready(
            x0t_contract_commands
        ),
        "x0t_contract_handoff_operator_sequence_ready": _x0t_contract_sequence_ready(x0t_contract),
        "live_rollout_handoff_available": live_rollout.get("available") is True,
        "live_rollout_handoff_decision": live_rollout.get("decision", ""),
        "live_rollout_handoff_ready_for_completion_rerun": live_rollout.get("ready_for_completion_rerun") is True,
        "live_rollout_handoff_can_close_image_digests_blocker": live_rollout.get(
            "can_close_image_digests_blocker"
        )
        is True,
        "live_rollout_handoff_missing_inputs_total": len(_dicts(live_rollout.get("missing_inputs"))),
        "live_rollout_handoff_operator_actions_total": len(live_rollout_actions),
        "live_rollout_handoff_operator_input_required_actions_total": _action_status_count(
            live_rollout_actions,
            "OPERATOR_INPUT_REQUIRED",
        ),
        "live_rollout_handoff_operator_commands_total": len(live_rollout_commands),
        "live_rollout_handoff_operator_command_entrypoints_missing": _command_entrypoints_missing(
            live_rollout_commands
        ),
        "live_rollout_handoff_operator_command_surface_ready": _command_surface_ready(live_rollout_commands),
        "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": _commands_with_shell_placeholders(
            live_rollout_commands
        ),
        "live_rollout_handoff_operator_command_shell_surface_ready": _command_shell_surface_ready(
            live_rollout_commands
        ),
        "live_rollout_handoff_operator_sequence_ready": _live_rollout_sequence_ready(live_rollout),
    }


def build_report(root: Path) -> Dict[str, Any]:
    source_reports = [_build_source_report(root, spec) for spec in SOURCE_SPECS]
    source_errors = [
        str(report["source_error"])
        for report in source_reports
        if report.get("source_error")
    ]
    sources_ready = sum(1 for report in source_reports if report.get("ready") is True)
    sources_total = len(source_reports)

    pipeline = _read_json(root / DEFAULT_INPUT_PIPELINE) or {}
    pipeline_summary = _summary(pipeline)
    return_acceptance = _read_json(root / DEFAULT_RETURN_ACCEPTANCE) or {}
    return_summary = _summary(return_acceptance)
    consistency = _read_json(root / DEFAULT_REQUIRED_EVIDENCE_CONSISTENCY) or {}
    consistency_summary = _summary(consistency)
    rollup = _read_json(root / DEFAULT_ROLLUP_CONTRACT) or {}
    rollup_summary = _summary(rollup)
    current_rollup = _read_json(root / DEFAULT_CURRENT_ROLLUP) or {}
    current_rollup_summary = _summary(current_rollup)
    operator_handoffs = _build_operator_handoffs(root)
    operator_summary = _operator_handoff_summary(operator_handoffs)
    blocking_inputs = _dicts(pipeline.get("blocking_inputs"))
    ready = not source_errors and sources_ready == sources_total
    raw_files_expected = _int_value(return_summary, "raw_files_expected")
    if raw_files_expected is None:
        raw_files_expected = _int_value(pipeline_summary, "raw_files_expected") or 0
    raw_files_installed = _int_value(return_summary, "raw_files_staged")
    raw_install_claim_source = "return_acceptance"
    if raw_files_installed is None:
        raw_files_installed = _int_value(pipeline_summary, "raw_files_installed") or 0
        raw_install_claim_source = "input_pipeline"
    raw_files_pipeline_reported_installed = _int_value(pipeline_summary, "raw_files_installed") or 0
    raw_files_existing_or_retained = _int_value(return_summary, "raw_files_destination_existing") or raw_files_pipeline_reported_installed

    return {
        "schema_version": "x0tta6bl4-integration-spine-production-closeout-v4",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "ready": ready,
        "decision": "CLOSEOUT_REVIEW_READY"
        if ready
        else "CLOSEOUT_REVIEW_INVALID_SOURCE_ARTIFACTS"
        if source_errors
        else "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only production closeout review. It summarizes current local "
            "reports and refuses closeout until upstream production evidence "
            "gates are ready. It does not collect evidence, contact live systems, "
            "submit transactions, mutate runtime, or close /goal."
        ),
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_artifacts": [spec.display_path for spec in SOURCE_SPECS] + [operator_handoffs.get("source_artifact", "")],
        "source_errors": source_errors,
        "source_reports": source_reports,
        "operator_handoffs": operator_handoffs,
        "blocking_inputs": blocking_inputs,
        "not_verified_yet": []
        if ready
        else [
            "external settlement live RPC gate returns READY_TO_PROMOTE",
            "collector/evidence-gate semantic readiness reaches READY_FOR_PROMOTION_REVIEW",
            "rollup approval contract and required evidence consistency are ready",
            "integration-spine current rollup returns COMPLETE",
        ],
        "summary": {
            "ready": ready,
            "sources_total": sources_total,
            "sources_ready": sources_ready,
            "sources_blocking": sources_total - sources_ready,
            "source_errors_total": len(source_errors),
            "blocking_inputs_total": pipeline_summary.get("blocking_inputs_total", len(blocking_inputs)),
            "blocking_external_inputs": pipeline_summary.get("blocking_external_inputs", 0),
            "blocking_raw_inputs": pipeline_summary.get("blocking_raw_inputs", 0),
            "collector_evidence_blockers": pipeline_summary.get("collector_evidence_blockers", 0),
            "raw_files_expected": raw_files_expected,
            "raw_files_installed": raw_files_installed,
            "raw_files_install_claim_source": raw_install_claim_source,
            "raw_files_pipeline_reported_installed": raw_files_pipeline_reported_installed,
            "raw_files_existing_or_retained": raw_files_existing_or_retained,
            "raw_files_ready_to_stage": return_summary.get("raw_files_ready_to_stage", 0),
            "raw_files_local_observation": return_summary.get("raw_files_local_observation", 0),
            "raw_ready_to_stage": return_summary.get("raw_ready_to_stage", False),
            "required_evidence_files_total": consistency_summary.get("required_evidence_files_total", 0),
            "required_evidence_files_ready": consistency_summary.get("required_evidence_files_ready", 0),
            "rollup_evidence_files_total": rollup_summary.get("evidence_files_total", 0),
            "rollup_evidence_files_valid": rollup_summary.get("evidence_files_valid", 0),
            "rollup_evidence_files_missing": rollup_summary.get("evidence_files_missing", 0),
            "rollup_evidence_files_invalid": rollup_summary.get("evidence_files_invalid", 0),
            "rollup_evidence_files_operator_input_required": rollup_summary.get(
                "evidence_files_operator_input_required",
                0,
            ),
            "rollup_ready_for_closeout_review": rollup_summary.get("ready_for_closeout_review", False),
            **_current_rollup_context(current_rollup_summary),
            **operator_summary,
        },
    }


def _closure_summary(closeout_report: Dict[str, Any]) -> Dict[str, Any]:
    summary = _summary(closeout_report)
    return {
        "ready": closeout_report.get("ready") is True,
        "sources_total": summary.get("sources_total", 0),
        "sources_ready": summary.get("sources_ready", 0),
        "sources_blocking": summary.get("sources_blocking", 0),
        "source_errors_total": summary.get("source_errors_total", 0),
        "blocking_inputs_total": summary.get("blocking_inputs_total", 0),
        "blocking_external_inputs": summary.get("blocking_external_inputs", 0),
        "blocking_raw_inputs": summary.get("blocking_raw_inputs", 0),
        "collector_evidence_blockers": summary.get("collector_evidence_blockers", 0),
        "raw_files_expected": summary.get("raw_files_expected", 0),
        "raw_files_installed": summary.get("raw_files_installed", 0),
        "raw_files_install_claim_source": summary.get("raw_files_install_claim_source", ""),
        "raw_files_pipeline_reported_installed": summary.get("raw_files_pipeline_reported_installed", 0),
        "raw_files_existing_or_retained": summary.get("raw_files_existing_or_retained", 0),
        "raw_files_ready_to_stage": summary.get("raw_files_ready_to_stage", 0),
        "raw_files_local_observation": summary.get("raw_files_local_observation", 0),
        "raw_ready_to_stage": summary.get("raw_ready_to_stage", False),
        "required_evidence_files_total": summary.get("required_evidence_files_total", 0),
        "required_evidence_files_ready": summary.get("required_evidence_files_ready", 0),
        "rollup_evidence_files_total": summary.get("rollup_evidence_files_total", 0),
        "rollup_evidence_files_valid": summary.get("rollup_evidence_files_valid", 0),
        "rollup_evidence_files_missing": summary.get("rollup_evidence_files_missing", 0),
        "rollup_evidence_files_invalid": summary.get("rollup_evidence_files_invalid", 0),
        "rollup_evidence_files_operator_input_required": summary.get(
            "rollup_evidence_files_operator_input_required",
            0,
        ),
        "rollup_ready_for_closeout_review": summary.get("rollup_ready_for_closeout_review", False),
        **_current_rollup_context(summary),
        "operator_handoff_source_available": summary.get("operator_handoff_source_available", False),
        "operator_handoff_source_errors_total": summary.get("operator_handoff_source_errors_total", 0),
        "x0t_governance_handoff_available": summary.get("x0t_governance_handoff_available", False),
        "x0t_governance_handoff_actionable": summary.get("x0t_governance_handoff_actionable", False),
        "x0t_governance_handoff_ready_for_operator_execute": summary.get(
            "x0t_governance_handoff_ready_for_operator_execute",
            False,
        ),
        "x0t_governance_handoff_approval_value_required": summary.get(
            "x0t_governance_handoff_approval_value_required",
            "",
        ),
        "x0t_governance_handoff_missing_inputs_total": summary.get(
            "x0t_governance_handoff_missing_inputs_total",
            0,
        ),
        "x0t_governance_handoff_operator_actions_total": summary.get(
            "x0t_governance_handoff_operator_actions_total",
            0,
        ),
        "x0t_governance_handoff_operator_approval_required_actions_total": summary.get(
            "x0t_governance_handoff_operator_approval_required_actions_total",
            0,
        ),
        "x0t_governance_handoff_operator_commands_total": summary.get(
            "x0t_governance_handoff_operator_commands_total",
            0,
        ),
        "x0t_governance_handoff_operator_command_entrypoints_missing": summary.get(
            "x0t_governance_handoff_operator_command_entrypoints_missing",
            0,
        ),
        "x0t_governance_handoff_operator_command_surface_ready": summary.get(
            "x0t_governance_handoff_operator_command_surface_ready",
            False,
        ),
        "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders": summary.get(
            "x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "x0t_governance_handoff_operator_command_shell_surface_ready": summary.get(
            "x0t_governance_handoff_operator_command_shell_surface_ready",
            False,
        ),
        "x0t_governance_handoff_operator_sequence_ready": summary.get(
            "x0t_governance_handoff_operator_sequence_ready",
            False,
        ),
        "external_settlement_handoff_available": summary.get("external_settlement_handoff_available", False),
        "external_settlement_handoff_ready_for_completion_rerun": summary.get(
            "external_settlement_handoff_ready_for_completion_rerun",
            False,
        ),
        "external_settlement_capture_preflight_decision": summary.get(
            "external_settlement_capture_preflight_decision",
            "",
        ),
        "external_settlement_capture_inputs_ready": summary.get("external_settlement_capture_inputs_ready", False),
        "external_settlement_handoff_missing_inputs_total": summary.get(
            "external_settlement_handoff_missing_inputs_total",
            0,
        ),
        "external_settlement_handoff_operator_actions_total": summary.get(
            "external_settlement_handoff_operator_actions_total",
            0,
        ),
        "external_settlement_handoff_operator_input_required_actions_total": summary.get(
            "external_settlement_handoff_operator_input_required_actions_total",
            0,
        ),
        "external_settlement_handoff_operator_commands_total": summary.get(
            "external_settlement_handoff_operator_commands_total",
            0,
        ),
        "external_settlement_handoff_operator_command_entrypoints_missing": summary.get(
            "external_settlement_handoff_operator_command_entrypoints_missing",
            0,
        ),
        "external_settlement_handoff_operator_command_surface_ready": summary.get(
            "external_settlement_handoff_operator_command_surface_ready",
            False,
        ),
        "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders": summary.get(
            "external_settlement_handoff_operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "external_settlement_handoff_operator_command_shell_surface_ready": summary.get(
            "external_settlement_handoff_operator_command_shell_surface_ready",
            False,
        ),
        "external_settlement_handoff_operator_sequence_ready": summary.get(
            "external_settlement_handoff_operator_sequence_ready",
            False,
        ),
        "x0t_contract_handoff_available": summary.get("x0t_contract_handoff_available", False),
        "x0t_contract_handoff_decision": summary.get("x0t_contract_handoff_decision", ""),
        "x0t_contract_handoff_deployment_ready": summary.get("x0t_contract_handoff_deployment_ready", False),
        "x0t_contract_handoff_approval_value_required": summary.get(
            "x0t_contract_handoff_approval_value_required",
            "",
        ),
        "x0t_contract_handoff_missing_inputs_total": summary.get(
            "x0t_contract_handoff_missing_inputs_total",
            0,
        ),
        "x0t_contract_handoff_operator_actions_total": summary.get(
            "x0t_contract_handoff_operator_actions_total",
            0,
        ),
        "x0t_contract_handoff_operator_approval_required_actions_total": summary.get(
            "x0t_contract_handoff_operator_approval_required_actions_total",
            0,
        ),
        "x0t_contract_handoff_operator_commands_total": summary.get(
            "x0t_contract_handoff_operator_commands_total",
            0,
        ),
        "x0t_contract_handoff_operator_command_entrypoints_missing": summary.get(
            "x0t_contract_handoff_operator_command_entrypoints_missing",
            0,
        ),
        "x0t_contract_handoff_operator_command_surface_ready": summary.get(
            "x0t_contract_handoff_operator_command_surface_ready",
            False,
        ),
        "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders": summary.get(
            "x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "x0t_contract_handoff_operator_command_shell_surface_ready": summary.get(
            "x0t_contract_handoff_operator_command_shell_surface_ready",
            False,
        ),
        "x0t_contract_handoff_operator_sequence_ready": summary.get(
            "x0t_contract_handoff_operator_sequence_ready",
            False,
        ),
        "live_rollout_handoff_available": summary.get("live_rollout_handoff_available", False),
        "live_rollout_handoff_decision": summary.get("live_rollout_handoff_decision", ""),
        "live_rollout_handoff_ready_for_completion_rerun": summary.get(
            "live_rollout_handoff_ready_for_completion_rerun",
            False,
        ),
        "live_rollout_handoff_can_close_image_digests_blocker": summary.get(
            "live_rollout_handoff_can_close_image_digests_blocker",
            False,
        ),
        "live_rollout_handoff_missing_inputs_total": summary.get(
            "live_rollout_handoff_missing_inputs_total",
            0,
        ),
        "live_rollout_handoff_operator_actions_total": summary.get(
            "live_rollout_handoff_operator_actions_total",
            0,
        ),
        "live_rollout_handoff_operator_input_required_actions_total": summary.get(
            "live_rollout_handoff_operator_input_required_actions_total",
            0,
        ),
        "live_rollout_handoff_operator_commands_total": summary.get(
            "live_rollout_handoff_operator_commands_total",
            0,
        ),
        "live_rollout_handoff_operator_command_entrypoints_missing": summary.get(
            "live_rollout_handoff_operator_command_entrypoints_missing",
            0,
        ),
        "live_rollout_handoff_operator_command_surface_ready": summary.get(
            "live_rollout_handoff_operator_command_surface_ready",
            False,
        ),
        "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders": summary.get(
            "live_rollout_handoff_operator_commands_with_shell_redirection_placeholders",
            0,
        ),
        "live_rollout_handoff_operator_command_shell_surface_ready": summary.get(
            "live_rollout_handoff_operator_command_shell_surface_ready",
            False,
        ),
        "live_rollout_handoff_operator_sequence_ready": summary.get(
            "live_rollout_handoff_operator_sequence_ready",
            False,
        ),
    }


def _closure_base(closeout_report: Dict[str, Any], *, schema_version: str, decision: str) -> Dict[str, Any]:
    return {
        "schema_version": schema_version,
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "ready": closeout_report.get("ready") is True,
        "decision": decision,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only closure review derived from production_closeout_review. "
            "It preserves the return-acceptance raw install source and does not collect evidence, "
            "contact live systems, submit transactions, mutate runtime, or close /goal."
        ),
        "source_artifacts": [DEFAULT_OUTPUT],
        "blocking_inputs": closeout_report.get("blocking_inputs", []),
        "source_reports": closeout_report.get("source_reports", []),
        "operator_handoffs": closeout_report.get("operator_handoffs", {}),
        "not_verified_yet": closeout_report.get("not_verified_yet", []),
        "summary": _closure_summary(closeout_report),
    }


def build_closure_preflight_report(closeout_report: Dict[str, Any]) -> Dict[str, Any]:
    ready = closeout_report.get("ready") is True
    return _closure_base(
        closeout_report,
        schema_version="x0tta6bl4-integration-spine-production-preflight-v4-repo-generated",
        decision="PREFLIGHT_READY_FOR_FINAL_REVIEW" if ready else "PREFLIGHT_BLOCKED_ON_OPERATOR_EVIDENCE",
    )


def build_final_review_report(closeout_report: Dict[str, Any]) -> Dict[str, Any]:
    ready = closeout_report.get("ready") is True
    return _closure_base(
        closeout_report,
        schema_version="x0tta6bl4-integration-spine-production-final-v4-repo-generated",
        decision="FINAL_REVIEW_READY" if ready else "FINAL_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
    )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production closeout review")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output-closure-preflight-json", default="")
    parser.add_argument("--output-final-review-json", default="")
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless closeout review is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
    write_json(root / args.output_json, report)
    if args.output_closure_preflight_json:
        write_json(root / args.output_closure_preflight_json, build_closure_preflight_report(report))
    if args.output_final_review_json:
        write_json(root / args.output_final_review_json, build_final_review_report(report))
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "ready": report["ready"],
                "goal_can_be_marked_complete": False,
                "summary": report["summary"],
                "closure_preflight_written": bool(args.output_closure_preflight_json),
                "final_review_written": bool(args.output_final_review_json),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
