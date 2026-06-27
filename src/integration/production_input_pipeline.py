"""Read-only production input pipeline report for the integration spine.

This gate replaces the old source-restored pipeline shard with a repo-backed
report derived from return-acceptance. It does not stage files, install raw
bundles, run collectors, contact live systems, submit transactions, mutate
runtime state, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_INPUT_MANIFEST = ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
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


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _int_value(data: Dict[str, Any], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status")
        if isinstance(status, str) and status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def _blocking_inputs(return_acceptance: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocking: List[Dict[str, Any]] = []
    for item in _dicts(return_acceptance.get("evidence_key_acceptance")):
        if item.get("ready_to_stage") is True:
            continue
        blocking.append(
            {
                "evidence_key": str(item.get("evidence_key", "")),
                "kind": "external_settlement"
                if str(item.get("evidence_key", "")) == "external_settlement"
                else "raw_evidence_bundle",
                "status": OPERATOR_INPUT_REQUIRED,
                "destination_path": ".tmp/external-settlement-evidence/settlement-submit.json"
                if str(item.get("evidence_key", "")) == "external_settlement"
                else "",
                "required_action": "submit/locate real X0T transaction receipt, retain settlement-submit.json, and verify it against live Base RPC"
                if str(item.get("evidence_key", "")) == "external_settlement"
                else "replace local-observation raw JSON with retained production/live operator JSON",
                "files_expected": item.get("files_expected", 0),
                "files_blocked": item.get("files_blocked", 0),
                "errors": [str(error) for error in item.get("errors", []) if isinstance(error, str)][:10],
            }
        )
    return blocking


def _raw_groups(input_manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        item
        for item in _dicts(input_manifest.get("input_groups"))
        if item.get("input_kind") == "raw_evidence_bundle"
    ]


def _raw_install_results(root: Path, input_manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for group in _raw_groups(input_manifest):
        collector_id = str(group.get("collector_id", ""))
        evidence_key = str(group.get("evidence_key", ""))
        for item in _dicts(group.get("raw_files")):
            destination = str(item.get("install_destination_path") or "")
            destination_exists = bool(destination) and (root / destination).exists()
            ready = item.get("ready") is True
            if ready and destination_exists:
                status = "ALREADY_STAGED"
            elif ready:
                status = "READY_TO_STAGE"
            else:
                status = OPERATOR_INPUT_REQUIRED
            results.append(
                {
                    "collector_id": collector_id,
                    "evidence_key": evidence_key,
                    "file_name": str(item.get("file_name", "")),
                    "raw_id": str(item.get("raw_id", "")),
                    "source_path": str(item.get("source_raw_path") or item.get("bundle_path") or ""),
                    "destination_path": destination,
                    "destination_exists": destination_exists,
                    "status": status,
                    "ready_to_stage": ready,
                    "current_status": str(item.get("current_status", "")),
                    "errors": [str(error) for error in item.get("errors", []) if isinstance(error, str)],
                }
            )
    return results


def _command_results(input_manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    commands: List[Dict[str, Any]] = []
    for group in _raw_groups(input_manifest):
        collector_id = str(group.get("collector_id", ""))
        raw_files = []
        preflight_errors: List[str] = []
        for item in _dicts(group.get("raw_files")):
            file_name = str(item.get("file_name", ""))
            destination = str(item.get("install_destination_path") or "")
            raw_files.append({"name": file_name, "path": destination})
            subject = Path(file_name).stem
            for error in [str(error) for error in item.get("errors", []) if isinstance(error, str)]:
                preflight_errors.append(f"{subject} {error}" if subject else error)
        commands.append(
            {
                "collector_id": collector_id,
                "command": str(group.get("collector_command", "")),
                "returncode": 2 if preflight_errors else 0,
                "preflight_errors": preflight_errors,
                "stdout_json": {"raw_files": raw_files},
            }
        )
    return commands


def build_report(root: Path, return_acceptance_path: Path, input_manifest_path: Path) -> Dict[str, Any]:
    return_acceptance = _read_json(return_acceptance_path)
    input_manifest = _read_json(input_manifest_path)
    source_errors: List[str] = []
    if return_acceptance is None:
        source_errors.append(f"missing or unreadable return-acceptance report: {DEFAULT_RETURN_ACCEPTANCE}")
        return_acceptance = {}
    if input_manifest is None:
        source_errors.append(f"missing or unreadable input manifest: {DEFAULT_INPUT_MANIFEST}")
        input_manifest = {}

    return_summary = _summary(return_acceptance)
    ready = (
        not source_errors
        and return_acceptance.get("status") == "VERIFIED HERE"
        and return_acceptance.get("ok") is True
        and return_acceptance.get("ready_for_pipeline_install") is True
        and return_summary.get("ready_for_pipeline_install") is True
    )
    blocking_inputs = _blocking_inputs(return_acceptance)
    raw_install_results = _raw_install_results(root, input_manifest)
    blocking_input_status_counts = _status_counts(blocking_inputs)
    raw_install_status_counts = _status_counts(raw_install_results)
    command_results = _command_results(input_manifest)
    raw_files_staged = _int_value(return_summary, "raw_files_staged")
    raw_files_expected = _int_value(return_summary, "raw_files_expected")
    raw_files_ready_to_stage = _int_value(return_summary, "raw_files_ready_to_stage")
    external_ready_to_stage = _int_value(return_summary, "external_artifacts_ready_to_stage")
    external_operator_required = _int_value(return_summary, "external_artifacts_operator_required")
    collector_blockers = max(
        _int_value(return_summary, "evidence_keys_total") - _int_value(return_summary, "evidence_keys_ready_to_stage"),
        0,
    )

    decision = (
        "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW"
        if ready
        else "INPUT_PIPELINE_INVALID_SOURCE_ARTIFACTS"
        if source_errors
        else "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-production-input-pipeline-v4-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "pipeline_decision": decision,
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only input pipeline report derived from return-acceptance. "
            "It reports staged/installed raw files from return_acceptance.raw_files_staged, "
            "not from stale pipeline-local observations, and does not stage, install, collect, "
            "contact live systems, mutate runtime, or close /goal."
        ),
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "runs_live_rpc": False,
        "runs_collectors": False,
        "source_artifacts": [str(Path(DEFAULT_RETURN_ACCEPTANCE)), str(Path(DEFAULT_INPUT_MANIFEST))],
        "source_errors": source_errors,
        "blocking_inputs": blocking_inputs,
        "raw_install_results": raw_install_results,
        "command_results": command_results,
        "not_verified_yet": []
        if ready
        else [
            "return acceptance marks every raw file and external artifact ready to stage",
            "external settlement live RPC gate is ready",
            "collector/evidence-gate semantic readiness reaches READY_FOR_PROMOTION_REVIEW",
        ],
        "summary": {
            "source_errors_total": len(source_errors),
            "ready": ready,
            "ready_for_pipeline_install": return_acceptance.get("ready_for_pipeline_install") is True,
            "ready_to_stage": return_acceptance.get("ready_to_stage") is True,
            "blocking_inputs_total": len(blocking_inputs),
            "blocking_input_status_counts": blocking_input_status_counts,
            "blocking_inputs_operator_input_required": blocking_input_status_counts.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "blocking_inputs_generic_operator_required": blocking_input_status_counts.get(
                OPERATOR_REQUIRED, 0
            ),
            "blocking_external_inputs": external_operator_required,
            "blocking_raw_inputs": _int_value(return_summary, "raw_files_operator_required"),
            "blocking_path_safety_inputs": 0,
            "collector_evidence_blockers": collector_blockers,
            "raw_install_status_counts": raw_install_status_counts,
            "raw_install_operator_input_required": raw_install_status_counts.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "raw_install_generic_operator_required": raw_install_status_counts.get(OPERATOR_REQUIRED, 0),
            "raw_files_expected": raw_files_expected,
            "raw_files_installed": raw_files_staged,
            "raw_files_staged": raw_files_staged,
            "raw_files_install_claim_source": "return_acceptance",
            "raw_files_preflight_reported_installed": raw_files_staged,
            "raw_files_ready_to_stage": raw_files_ready_to_stage,
            "raw_files_local_observation": _int_value(return_summary, "raw_files_local_observation"),
            "raw_files_missing": _int_value(return_summary, "raw_files_missing"),
            "raw_files_invalid_json": _int_value(return_summary, "raw_files_invalid_json"),
            "raw_files_fake_evidence": _int_value(return_summary, "raw_files_fake_evidence"),
            "raw_files_template_only": _int_value(return_summary, "raw_files_template_only"),
            "raw_files_missing_provenance": _int_value(return_summary, "raw_files_missing_provenance"),
            "raw_files_wrong_status": _int_value(return_summary, "raw_files_wrong_status"),
            "raw_files_destination_existing": _int_value(return_summary, "raw_files_destination_existing"),
            "raw_ready_to_stage": return_summary.get("raw_ready_to_stage") is True,
            "partial_raw_stage": raw_files_staged > 0 and raw_files_staged < raw_files_expected,
            "external_artifacts_ready_to_stage": external_ready_to_stage,
            "external_artifacts_operator_required": external_operator_required,
            "external_settlement_ready": return_summary.get("external_settlement_live_rpc_ready") is True,
            "external_settlement_live_rpc_ready": return_summary.get("external_settlement_live_rpc_ready") is True,
            "secret_scan_source_errors": _int_value(return_summary, "secret_scan_source_errors"),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production input pipeline report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--input-manifest", default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless input pipeline is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    return_input = Path(args.return_acceptance)
    manifest_input = Path(args.input_manifest)
    report = build_report(
        root,
        return_input if return_input.is_absolute() else root / return_input,
        manifest_input if manifest_input.is_absolute() else root / manifest_input,
    )
    write_json(root / args.output_json, report)
    print(
        json.dumps(
            {
                "pipeline_decision": report["pipeline_decision"],
                "ready": report["ready"],
                "goal_can_be_marked_complete": False,
                "summary": report["summary"],
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
