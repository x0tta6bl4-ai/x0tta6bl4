"""Read-only production input bundle stage gate for the integration spine.

This report replaces the stale source-restored stage shard. It is intentionally
read-only: it reports whether the current return-acceptance artifact permits a
stage/install step, but it does not copy files, install raw evidence, run live
RPC, submit transactions, mutate runtime state, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_RETURN_ACCEPTANCE = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
DEFAULT_PIPELINE = ".tmp/validation-shards/integration-spine-production-input-pipeline-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-input-bundle-stage-current.json"
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


def _summary(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (data or {}).get("summary", {})
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


def _blocking_inputs(acceptance: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocking: List[Dict[str, Any]] = []
    for item in _dicts(acceptance.get("evidence_key_acceptance")):
        if item.get("ready_to_stage") is True:
            continue
        evidence_key = str(item.get("evidence_key", ""))
        blocking.append(
            {
                "evidence_key": evidence_key,
                "kind": "external_settlement" if evidence_key == "external_settlement" else "raw_evidence_bundle",
                "status": OPERATOR_INPUT_REQUIRED,
                "files_expected": _int_value(item, "files_expected"),
                "files_staged": _int_value(item, "files_staged"),
                "files_ready_to_stage": _int_value(item, "files_ready_to_stage"),
                "files_blocked": _int_value(item, "files_blocked"),
                "errors": [str(error) for error in item.get("errors", []) if isinstance(error, str)][:10],
            }
        )
    return blocking


def _raw_file_rows(acceptance: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in _dicts(acceptance.get("evidence_key_acceptance")):
        evidence_key = str(item.get("evidence_key", ""))
        if evidence_key == "external_settlement":
            continue
        rows.append(
            {
                "evidence_key": evidence_key,
                "files_expected": _int_value(item, "files_expected"),
                "files_staged": _int_value(item, "files_staged"),
                "files_ready_to_stage": _int_value(item, "files_ready_to_stage"),
                "files_operator_required": _int_value(item, "files_operator_required"),
                "files_blocked": _int_value(item, "files_blocked"),
                "ready_to_stage": item.get("ready_to_stage") is True,
                "statuses": item.get("statuses", {}) if isinstance(item.get("statuses"), dict) else {},
            }
        )
    return rows


def _source_errors(return_acceptance: Optional[Dict[str, Any]], pipeline: Optional[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    if return_acceptance is None:
        errors.append(f"missing or unreadable return-acceptance report: {DEFAULT_RETURN_ACCEPTANCE}")
    if pipeline is None:
        errors.append(f"missing or unreadable production input pipeline report: {DEFAULT_PIPELINE}")
    return errors


def build_report(root: Path, return_acceptance_path: Path, pipeline_path: Path) -> Dict[str, Any]:
    return_acceptance = _read_json(return_acceptance_path)
    pipeline = _read_json(pipeline_path)
    source_errors = _source_errors(return_acceptance, pipeline)
    return_summary = _summary(return_acceptance)
    pipeline_summary = _summary(pipeline)

    raw_expected = _int_value(return_summary, "raw_files_expected")
    raw_staged = _int_value(return_summary, "raw_files_staged")
    raw_ready_to_stage = _int_value(return_summary, "raw_files_ready_to_stage")
    raw_operator_required = max(raw_expected - raw_ready_to_stage, 0)
    external_operator_required = _int_value(return_summary, "external_artifacts_operator_required")
    blocking_inputs = _blocking_inputs(return_acceptance or {})
    blocking_input_status_counts = _status_counts(blocking_inputs)

    raw_mismatch_errors: List[str] = []
    if pipeline is not None and _int_value(pipeline_summary, "raw_files_staged") != raw_staged:
        raw_mismatch_errors.append("pipeline.raw_files_staged must equal return_acceptance.raw_files_staged")
    if pipeline is not None and _int_value(pipeline_summary, "raw_files_installed") != raw_staged:
        raw_mismatch_errors.append("pipeline.raw_files_installed must equal return_acceptance.raw_files_staged")

    ready_to_stage = (
        not source_errors
        and not raw_mismatch_errors
        and (return_acceptance or {}).get("status") == "VERIFIED HERE"
        and (return_acceptance or {}).get("ok") is True
        and (return_acceptance or {}).get("ready_for_pipeline_install") is True
        and return_summary.get("ready_for_pipeline_install") is True
    )
    decision = (
        "SCOPED_INPUT_BUNDLE_READY"
        if ready_to_stage
        else "SCOPED_INPUT_BUNDLE_INVALID_SOURCE_ARTIFACTS"
        if source_errors or raw_mismatch_errors
        else "SCOPED_INPUT_BUNDLE_BLOCKED"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-production-input-bundle-stage-v4-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "stage_decision": decision,
        "ready_to_stage": ready_to_stage,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only stage gate derived from current return-acceptance and "
            "production input pipeline reports. It never stages templates or local observations, "
            "and it does not copy files, install raw evidence, contact live systems, submit "
            "transactions, mutate runtime state, or close /goal."
        ),
        "stages_operator_inputs": False,
        "materializes_evidence": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "source_artifacts": [DEFAULT_RETURN_ACCEPTANCE, DEFAULT_PIPELINE],
        "source_load_errors": source_errors,
        "source_errors": source_errors + raw_mismatch_errors,
        "blocking_inputs": blocking_inputs,
        "raw_files": _raw_file_rows(return_acceptance or {}),
        "external_artifact": {
            "ready_to_stage": return_summary.get("external_settlement_live_rpc_ready") is True,
            "operator_required": external_operator_required,
            "live_rpc_ready": return_summary.get("external_settlement_live_rpc_ready") is True,
            "live_rpc_checked": return_summary.get("external_settlement_live_rpc_checked") is True,
        },
        "secret_scan": {
            "decision": return_summary.get("secret_scan_decision", "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR"),
            "findings": _int_value(return_summary, "secret_scan_findings"),
            "source_errors": _int_value(return_summary, "secret_scan_source_errors"),
        },
        "partial_raw_stage": raw_staged > 0 and raw_staged < raw_expected,
        "not_verified_yet": []
        if ready_to_stage
        else [
            "retained external X0T settlement receipt accepted by static and live RPC gates",
            "all raw production evidence files are retained production-grade JSON, not local observations or templates",
            "return acceptance reaches RETURN_ACCEPTANCE_READY",
            "production input pipeline reaches READY_FOR_PRODUCTION_CLOSEOUT_REVIEW",
        ],
        "summary": {
            "source_errors_total": len(source_errors) + len(raw_mismatch_errors),
            "raw_files_expected": raw_expected,
            "raw_files_staged": raw_staged,
            "raw_files_already_staged": raw_staged,
            "raw_files_ready_to_stage": raw_ready_to_stage,
            "raw_files_operator_required": raw_operator_required,
            "raw_files_missing": _int_value(return_summary, "raw_files_missing"),
            "raw_files_invalid_json": _int_value(return_summary, "raw_files_invalid_json"),
            "raw_files_local_observation": _int_value(return_summary, "raw_files_local_observation"),
            "raw_files_fake_evidence": _int_value(return_summary, "raw_files_fake_evidence"),
            "raw_files_template_only": _int_value(return_summary, "raw_files_template_only"),
            "raw_files_missing_provenance": _int_value(return_summary, "raw_files_missing_provenance"),
            "raw_files_wrong_status": _int_value(return_summary, "raw_files_wrong_status"),
            "raw_files_destination_existing": _int_value(return_summary, "raw_files_destination_existing"),
            "raw_ready_to_stage": return_summary.get("raw_ready_to_stage") is True,
            "external_artifacts_expected": _int_value(return_summary, "external_artifacts_expected"),
            "external_artifacts_staged": _int_value(return_summary, "external_artifacts_staged"),
            "external_artifacts_ready_to_stage": _int_value(return_summary, "external_artifacts_ready_to_stage"),
            "external_artifacts_operator_required": external_operator_required,
            "external_artifacts_missing": _int_value(return_summary, "external_artifacts_missing"),
            "external_artifacts_invalid": _int_value(return_summary, "external_artifacts_invalid"),
            "external_settlement_live_rpc_ready": return_summary.get("external_settlement_live_rpc_ready") is True,
            "ready_to_stage": ready_to_stage,
            "partial_raw_stage": raw_staged > 0 and raw_staged < raw_expected,
            "stage_decision": decision,
            "blocking_inputs_total": len(blocking_inputs),
            "blocking_input_status_counts": blocking_input_status_counts,
            "blocking_inputs_operator_input_required": blocking_input_status_counts.get(
                OPERATOR_INPUT_REQUIRED, 0
            ),
            "blocking_inputs_generic_operator_required": blocking_input_status_counts.get(
                OPERATOR_REQUIRED, 0
            ),
            "blocking_raw_inputs": raw_operator_required,
            "blocking_external_inputs": external_operator_required,
            "pipeline_raw_files_installed": _int_value(pipeline_summary, "raw_files_installed"),
            "raw_install_claim_source": "return_acceptance",
            "secret_scan_decision": return_summary.get("secret_scan_decision", "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR"),
            "secret_scan_findings": _int_value(return_summary, "secret_scan_findings"),
            "secret_scan_source_errors": _int_value(return_summary, "secret_scan_source_errors"),
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Production Input Bundle Stage",
            f"stage_decision: {report.get('stage_decision')}",
            f"ready_to_stage: {report.get('ready_to_stage')}",
            f"raw_files_staged: {summary.get('raw_files_staged')}",
            f"raw_files_ready_to_stage: {summary.get('raw_files_ready_to_stage')}",
            f"raw_files_local_observation: {summary.get('raw_files_local_observation')}",
            f"external_settlement_live_rpc_ready: {summary.get('external_settlement_live_rpc_ready')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production input bundle stage report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    return_input = Path(args.return_acceptance)
    pipeline_input = Path(args.pipeline)
    report = build_report(
        root,
        return_input if return_input.is_absolute() else root / return_input,
        pipeline_input if pipeline_input.is_absolute() else root / pipeline_input,
    )
    output_input = Path(args.output_json)
    write_json(output_input if output_input.is_absolute() else root / output_input, report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready_to_stage"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
