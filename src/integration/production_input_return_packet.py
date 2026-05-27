"""Build the integration-spine production input return packet.

The packet is an operator handoff surface derived from current pipeline and
completion-gate artifacts. It is read-only: it does not stage evidence, mutate
files, call live RPC, submit transactions, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_COMPLETION_GATE = ".tmp/validation-shards/integration-spine-completion-gate-runner-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-input-return-packet-current.json"

BLOCKING = "BLOCKING"
OPERATOR_INPUT_REQUIRED = "OPERATOR_INPUT_REQUIRED"
OPERATOR_REQUIRED = "OPERATOR_REQUIRED"


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


def _strings(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _operator_status(source_errors: List[str]) -> str:
    return BLOCKING if source_errors else OPERATOR_INPUT_REQUIRED


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _operator_bundle_path(raw_id: str) -> str:
    return f".tmp/production-raw-evidence-operator-bundle/{raw_id}" if raw_id else ""


def _raw_replacement_contract(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_id = str(item.get("raw_id") or "")
    return {
        "current_blocker_status": item.get("current_status") or item.get("status") or "",
        "accepted_only_if": [
            "status or evidence_status is exactly VERIFIED HERE",
            "collected_at is an RFC3339 UTC timestamp from the retained production run",
            "collected_by is a non-placeholder operator or automation identity",
            "source_commands lists the exact production command, query, API call, CI job, or operator procedure",
            "JSON body contains no TEMPLATE_ONLY, REPLACE_WITH, placeholder, mock, simulated, or local-observation residue",
            "collector-specific semantic gate can normalize the raw file into a production evidence bundle",
        ],
        "rejected_if_any": [
            "_template_only or _not_evidence markers are present",
            "status or evidence_status is TEMPLATE_ONLY, NOT VERIFIED YET, SIMULATED, or any non-VERIFIED HERE value",
            "mock, simulated, template_only, placeholder, planned_only, or not_evidence is true",
            "observation_scope says current local verification environment",
            "production_ready=false, production_claim=false, or production_blocker is present",
            "source_commands contains collect <raw_id>, TODO, placeholder, REPLACE_WITH, {{...}}, or unresolved <...> tokens",
            "JSON body contains REPLACE_WITH, CHANGEME, example.invalid, {{...}}, or scaffold-only fields like operator_notes",
        ],
        "local_acceptance_gate": "python3 scripts/ops/import_production_raw_evidence_bundle.py --bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready",
        "hash_binding_gate": "python3 scripts/ops/sync_integration_spine_production_evidence.py --require-complete",
    }


def _raw_blocking_inputs(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in _dicts(pipeline.get("raw_install_results")):
        if item.get("ready_to_stage") is True:
            continue
        raw_id = str(item.get("raw_id") or "")
        destination_path = str(item.get("destination_path") or "")
        status = str(item.get("status") or OPERATOR_INPUT_REQUIRED)
        items.append(
            {
                "kind": "raw_evidence",
                "collector_id": item.get("collector_id", ""),
                "evidence_key": item.get("evidence_key", ""),
                "raw_id": raw_id,
                "source_path": item.get("source_path", destination_path),
                "destination_path": destination_path,
                "collector_raw_destination_path": destination_path,
                "operator_bundle_destination_path": _operator_bundle_path(raw_id),
                "status": status,
                "errors": _strings(item.get("errors")),
                "required_action": (
                    "replace the local-observation JSON with retained production/live operator JSON; "
                    "remove observation_scope, production_ready=false, production_claim=false, and production_blocker"
                ),
                "required_statuses": ["VERIFIED HERE"],
                "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
                "required_hash_binding_fields": ["evidence_root", "evidence_files[].name", "evidence_files[].path", "evidence_files[].sha256"],
                "hash_binding_enforced_by": ["python3 scripts/ops/sync_integration_spine_production_evidence.py --require-complete"],
                "validation_commands": [
                    "python3 scripts/ops/import_production_raw_evidence_bundle.py --bundle-root .tmp/production-raw-evidence-operator-bundle --require-ready"
                ],
                "evidence_replacement_contract": _raw_replacement_contract(item),
            }
        )
    return items


def _external_blocking_inputs(pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in _dicts(pipeline.get("blocking_inputs")):
        if item.get("kind") != "external_settlement" and item.get("evidence_key") != "external_settlement":
            continue
        destination = str(item.get("destination_path") or ".tmp/external-settlement-evidence/settlement-submit.json")
        items.append(
            {
                "kind": "external_settlement",
                "collector_id": "",
                "evidence_key": "external_settlement",
                "source_path": ".tmp/integration-spine-production-input-bundle-scaffold/external-settlement/settlement-submit.template.json",
                "destination_path": destination,
                "operator_bundle_destination_path": destination,
                "status": str(item.get("status") or OPERATOR_INPUT_REQUIRED),
                "errors": _strings(item.get("errors")),
                "required_action": item.get("required_action")
                or "replace external settlement template with a submitted X0T transaction receipt and live RPC verification",
                "required_statuses": ["VERIFIED HERE"],
                "required_operator_provenance_fields": [
                    "status",
                    "evidence_status",
                    "settlement_submitted",
                    "token_symbol",
                    "destination_chain",
                    "settlement_id",
                    "transaction_hash",
                    "transaction_receipt_status",
                    "block_number",
                    "block_hash",
                    "from_address",
                    "to_address",
                    "explorer_url",
                    "source_commands",
                ],
                "required_hash_binding_fields": [],
                "hash_binding_enforced_by": [],
                "validation_commands": [
                    "python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready",
                    "python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready",
                ],
            }
        )
    return items


def _blocking_input_groups(blocking_inputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for item in blocking_inputs:
        key = (str(item.get("kind", "")), str(item.get("evidence_key", "")), str(item.get("collector_id", "")))
        group = groups.setdefault(
            key,
            {
                "kind": item.get("kind", ""),
                "evidence_key": item.get("evidence_key", ""),
                "collector_id": item.get("collector_id", ""),
                "blocking_inputs": 0,
                "statuses": [],
                "source_paths": [],
                "destination_paths": [],
                "operator_bundle_destination_paths": [],
                "required_statuses": item.get("required_statuses", []),
                "required_operator_provenance_fields": item.get("required_operator_provenance_fields", []),
                "required_hash_binding_fields": item.get("required_hash_binding_fields", []),
                "hash_binding_enforced_by": item.get("hash_binding_enforced_by", []),
                "validation_commands": item.get("validation_commands", []),
            },
        )
        group["blocking_inputs"] += 1
        for field, value in (
            ("statuses", item.get("status")),
            ("source_paths", item.get("source_path")),
            ("destination_paths", item.get("destination_path")),
            ("operator_bundle_destination_paths", item.get("operator_bundle_destination_path")),
        ):
            if value and value not in group[field]:
                group[field].append(value)
    return sorted(groups.values(), key=lambda row: (str(row.get("kind", "")), str(row.get("collector_id", "")), str(row.get("evidence_key", ""))))


def _operator_next_actions(
    pipeline_summary: Dict[str, Any],
    blocking_inputs: List[Dict[str, Any]],
    source_errors: List[str],
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    raw_blocking = [item for item in blocking_inputs if item.get("kind") == "raw_evidence"]
    external_blocking = [item for item in blocking_inputs if item.get("kind") == "external_settlement"]
    raw_expected = _int_value(pipeline_summary, "raw_files_expected")
    raw_ready = _int_value(pipeline_summary, "raw_files_ready_to_stage") + _int_value(pipeline_summary, "raw_files_installed")
    raw_missing = _int_value(pipeline_summary, "raw_files_missing")
    raw_local = _int_value(pipeline_summary, "raw_files_local_observation")
    raw_blocked_total = max(len(raw_blocking), raw_expected - raw_ready, raw_missing + raw_local, 0)
    status = _operator_status(source_errors)
    if raw_blocked_total > 0:
        actions.append(
            {
                "id": "replace_raw_local_observation_evidence",
                "status": status,
                "blocked_inputs": raw_blocked_total,
                "description": (
                    "Replace every listed local-observation or missing raw file with retained production/live "
                    "operator JSON, then run the scaffold verifier. Local smoke observations must not be "
                    "installed as production evidence."
                ),
                "command": "bash .tmp/integration-spine-production-input-bundle-scaffold/verify-filled-bundle.sh",
            }
        )
    external_required = max(
        len(external_blocking),
        _int_value(pipeline_summary, "external_artifacts_operator_required"),
        _int_value(pipeline_summary, "blocking_external_inputs"),
    )
    if external_required > 0:
        actions.append(
            {
                "id": "replace_external_settlement_template",
                "status": status,
                "blocked_inputs": external_required,
                "description": (
                    "Replace the external settlement template with a submitted X0T transaction receipt accepted "
                    "by verify_x0t_external_settlement_evidence.py and verify_x0t_external_settlement_live_rpc.py."
                ),
                "command": "bash .tmp/integration-spine-production-input-bundle-scaffold/verify-filled-bundle.sh",
            }
        )
    path_safety_blocked = _int_value(pipeline_summary, "blocking_path_safety_inputs")
    if path_safety_blocked > 0:
        actions.append(
            {
                "id": "fix_operator_bundle_path_safety",
                "status": status,
                "blocked_inputs": path_safety_blocked,
                "description": "Fix path-safety violations before secret scan, staging, or raw evidence install.",
                "command": "python3 scripts/ops/stage_integration_spine_production_input_bundle.py --output text",
            }
        )
    return actions


def build_report(root: Path, pipeline_path: Path, completion_gate_path: Path) -> Dict[str, Any]:
    pipeline = _read_json(pipeline_path)
    completion_gate = _read_json(completion_gate_path)
    source_errors: List[str] = []
    if pipeline is None:
        source_errors.append(f"missing or unreadable production input pipeline: {DEFAULT_PIPELINE}")
        pipeline = {}
    if completion_gate is None:
        source_errors.append(f"missing or unreadable completion gate runner: {DEFAULT_COMPLETION_GATE}")
        completion_gate = {}

    pipeline_summary = _summary(pipeline)
    completion_summary = _summary(completion_gate)
    blocking_inputs = _raw_blocking_inputs(pipeline) + _external_blocking_inputs(pipeline)
    operator_next_actions = _operator_next_actions(pipeline_summary, blocking_inputs, source_errors)
    blocking_input_statuses = _status_counts(blocking_inputs)
    action_statuses: Dict[str, int] = {}
    for action in operator_next_actions:
        action_status = str(action.get("status", ""))
        action_statuses[action_status] = action_statuses.get(action_status, 0) + 1

    ready = (
        not source_errors
        and not operator_next_actions
        and (pipeline or {}).get("ready") is True
        and (completion_gate or {}).get("completion_decision") == "COMPLETE"
    )
    decision = (
        "RETURN_PACKET_READY"
        if ready
        else "RETURN_PACKET_INVALID_SOURCE_ARTIFACTS"
        if source_errors
        else "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-production-input-return-packet-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated operator return packet derived from retained current pipeline and completion-gate "
            "artifacts. It describes required operator inputs and local validation commands only."
        ),
        "mutates_files": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_of_truth": {
            "pipeline_json": DEFAULT_PIPELINE,
            "completion_gate_json": DEFAULT_COMPLETION_GATE,
        },
        "source_errors": source_errors,
        "current_state": {
            "pipeline_decision": (pipeline or {}).get("pipeline_decision"),
            "runner_decision": (completion_gate or {}).get("completion_decision"),
            "stage_decision": pipeline_summary.get("stage_decision"),
            "blocking_inputs_total": len(blocking_inputs),
            "blocking_input_status_counts": blocking_input_statuses,
            "blocking_inputs_operator_input_required": blocking_input_statuses.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "blocking_inputs_generic_operator_required": blocking_input_statuses.get(
                OPERATOR_REQUIRED, 0
            ),
            "blocking_raw_inputs": sum(1 for item in blocking_inputs if item.get("kind") == "raw_evidence"),
            "blocking_external_inputs": sum(1 for item in blocking_inputs if item.get("kind") == "external_settlement"),
            "blocking_path_safety_inputs": _int_value(pipeline_summary, "blocking_path_safety_inputs"),
            "raw_files_expected": pipeline_summary.get("raw_files_expected", 0),
            "raw_files_installed": pipeline_summary.get("raw_files_installed", 0),
            "operator_next_actions_total": len(operator_next_actions),
            "operator_next_action_ids": [str(item.get("id", "")) for item in operator_next_actions if item.get("id")],
            "steps_failed_unexpected": completion_summary.get("steps_failed_unexpected", 0),
        },
        "blocking_inputs": blocking_inputs,
        "blocking_input_groups": _blocking_input_groups(blocking_inputs),
        "required_raw_return_file_count": pipeline_summary.get("raw_files_expected", 0),
        "required_external_return_file_count": pipeline_summary.get("external_artifacts_operator_required", 0),
        "required_path_safety_fix_count": pipeline_summary.get("blocking_path_safety_inputs", 0),
        "required_return_file_count": pipeline_summary.get("raw_files_expected", 0)
        + pipeline_summary.get("external_artifacts_operator_required", 0),
        "operator_next_actions": operator_next_actions,
        "operator_sequence": [
            "Replace every listed raw scaffold file with retained production JSON from real operator runs.",
            "Replace the external settlement template with a submitted X0T transaction receipt.",
            "Run the scaffold verifier and path-safety dry-run; fix any PATH_SAFETY_BLOCKED result before secret scan or staging.",
            "Run the secret scan and dry-run acceptance; keep them red until every template marker and secret-like value is gone.",
            "Stage and install only after the verifier and secret scan accept the filled return bundle.",
            "Run collectors/evidence gates and then the outer completion gate.",
            "Run the final production review, then the top-level closeout review; close /goal only if closeout permits it.",
        ],
        "commands": {
            "verify_filled_bundle": "bash .tmp/integration-spine-production-input-bundle-scaffold/verify-filled-bundle.sh",
            "path_safety_before_stage": "python3 scripts/ops/stage_integration_spine_production_input_bundle.py --output text",
            "secret_scan_before_stage": (
                "python3 -m src.integration.operator_bundle_secret_scan "
                "--return-packet-json .tmp/validation-shards/integration-spine-production-input-return-packet-current.json --output text"
            ),
            "dry_run_return_acceptance": "python3 -m src.integration.production_input_return_acceptance --root . --output text",
            "stage_and_install_after_verify_ready": (
                "python3 scripts/ops/run_integration_spine_production_input_pipeline.py "
                "--stage-ready --install-raw --overwrite --require-ready"
            ),
            "run_collectors_after_install_ready": (
                "python3 scripts/ops/run_integration_spine_production_input_pipeline.py "
                "--stage-ready --install-raw --overwrite --run-collectors --require-ready"
            ),
            "completion_gate_after_collectors": "python3 scripts/ops/run_integration_spine_completion_gate.py",
            "production_final_review": "python3 scripts/ops/run_integration_spine_production_final_review.py --output text",
            "production_closeout_review": "python3 scripts/ops/run_integration_spine_production_closeout_review.py --output text",
        },
        "not_verified_yet": []
        if ready
        else [
            "operator-returned raw production evidence is not fully accepted",
            "external settlement receipt and live RPC evidence are not fully accepted",
            "completion gate is not complete",
        ],
        "summary": {
            "source_errors_total": len(source_errors),
            "blocking_inputs_total": len(blocking_inputs),
            "blocking_input_status_counts": blocking_input_statuses,
            "blocking_inputs_operator_input_required": blocking_input_statuses.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "blocking_inputs_generic_operator_required": blocking_input_statuses.get(
                OPERATOR_REQUIRED, 0
            ),
            "blocking_raw_inputs": sum(1 for item in blocking_inputs if item.get("kind") == "raw_evidence"),
            "blocking_external_inputs": sum(1 for item in blocking_inputs if item.get("kind") == "external_settlement"),
            "operator_next_actions_total": len(operator_next_actions),
            "operator_next_actions_operator_input_required": action_statuses.get(OPERATOR_INPUT_REQUIRED, 0),
            "operator_next_actions_generic_blocking": action_statuses.get(BLOCKING, 0),
            "raw_files_expected": pipeline_summary.get("raw_files_expected", 0),
            "raw_files_missing": pipeline_summary.get("raw_files_missing", 0),
            "raw_files_local_observation": pipeline_summary.get("raw_files_local_observation", 0),
            "external_artifacts_operator_required": pipeline_summary.get("external_artifacts_operator_required", 0),
            "external_settlement_live_rpc_ready": pipeline_summary.get("external_settlement_live_rpc_ready", False),
            "completion_decision": (completion_gate or {}).get("completion_decision"),
            "steps_failed_unexpected": completion_summary.get("steps_failed_unexpected", 0),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production input return packet")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--completion-gate", default=DEFAULT_COMPLETION_GATE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless the return packet is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root, _resolve(root, args.pipeline), _resolve(root, args.completion_gate))
    write_json(_resolve(root, args.output_json), report)
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "goal_can_be_marked_complete": report["goal_can_be_marked_complete"],
                "summary": report["summary"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_ready and report["decision"] != "RETURN_PACKET_READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
