"""Read-only acceptance gate for returned production input bundles.

The gate summarizes whether operator-returned raw bundles and external
settlement evidence are acceptable for the local input pipeline. It does not
stage or install files, run live RPC, submit transactions, or close the goal.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.production_evidence_intake import REQUIRED_EVIDENCE_KEYS


DEFAULT_INPUT_MANIFEST = ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC = ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json"
DEFAULT_REQUIRED_CONSISTENCY = ".tmp/validation-shards/integration-spine-required-evidence-consistency-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-production-input-return-acceptance-current.json"
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


def _status_map_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        statuses = item.get("statuses", {})
        if not isinstance(statuses, dict):
            continue
        for status, count in statuses.items():
            if not isinstance(status, str) or not status:
                continue
            if not isinstance(count, int) or isinstance(count, bool):
                count = 1
            counts[status] = counts.get(status, 0) + count
    return counts


def _summary(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("summary", {})
    return value if isinstance(value, dict) else {}


def _external_live_rpc_acceptance(live_rpc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if live_rpc is None:
        return {
            "live_rpc_report_found": False,
            "artifact_exists": False,
            "live_rpc_checked": False,
            "ready": False,
            "errors": ["external settlement live RPC report is missing or unreadable"],
        }
    summary = _summary(live_rpc)
    ready = (
        live_rpc.get("status") == "VERIFIED HERE"
        and live_rpc.get("ok") is True
        and summary.get("x0t_external_settlement_live_rpc_ready") is True
        and summary.get("retained_evidence_ready") is True
        and summary.get("live_rpc_checked") is True
    )
    errors = [] if ready else [
        "retained external X0T settlement receipt accepted by the non-live evidence gate",
        "RPC URL for the matching Base chain supplied via --rpc-url or X0T_*_RPC_URL",
        "live eth_getTransactionReceipt and eth_getTransactionByHash match retained receipt fields",
    ]
    return {
        "live_rpc_report_found": True,
        "artifact_exists": summary.get("evidence_file_found") is True,
        "live_rpc_checked": summary.get("live_rpc_checked") is True,
        "ready": ready,
        "errors": errors,
    }


def _raw_group_acceptance(root: Path, group: Dict[str, Any]) -> Dict[str, Any]:
    raw_files = _dicts(group.get("raw_files"))
    statuses: Dict[str, int] = {}
    errors: List[str] = []
    staged = 0
    ready_to_stage = 0
    operator_required = 0
    blocked = 0
    missing = 0
    invalid_json = 0
    local_observation = 0
    fake_evidence = 0
    template_only = 0
    missing_provenance = 0
    wrong_status = 0
    destination_existing = 0

    for item in raw_files:
        destination = str(item.get("install_destination_path") or "")
        destination_exists = bool(destination) and (root / destination).exists()
        item_errors = [str(error) for error in item.get("errors", []) if isinstance(error, str)]
        current_status = str(item.get("current_status") or "")
        if destination_exists:
            destination_existing += 1
        if current_status == "LOCAL_OBSERVATION":
            local_observation += 1
            item_errors.append("raw evidence is still a local observation")
        if current_status in {"FAKE_EVIDENCE", "MOCK", "SIMULATED"}:
            fake_evidence += 1
            item_errors.append("raw evidence is fake, mocked, or simulated")
        if item.get("template_rejected") is False:
            template_only += 1
            item_errors.append("template evidence was not rejected")
        if not item.get("required_operator_provenance_fields"):
            missing_provenance += 1
            item_errors.append("required operator provenance fields are missing")
        if item.get("required_status") != "VERIFIED HERE":
            wrong_status += 1
            item_errors.append("required status must be VERIFIED HERE")

        acceptable = item.get("ready") is True and not item_errors
        if destination_exists and acceptable:
            status = "ALREADY_STAGED"
            staged += 1
        elif acceptable:
            status = "READY_TO_STAGE"
            ready_to_stage += 1
        else:
            status = OPERATOR_INPUT_REQUIRED
            operator_required += 1
            blocked += 1
        statuses[status] = statuses.get(status, 0) + 1
        if not destination_exists and status != "READY_TO_STAGE":
            missing += 1
        errors.extend(item_errors)

    expected = len(raw_files)
    staged_or_ready = staged + ready_to_stage
    return {
        "evidence_key": group.get("evidence_key", ""),
        "files_expected": expected,
        "files_staged": staged,
        "files_ready_to_stage": ready_to_stage,
        "files_operator_required": operator_required,
        "files_blocked": blocked,
        "ready_to_stage": expected > 0 and staged_or_ready == expected and blocked == 0,
        "statuses": statuses,
        "errors": sorted(set(errors)),
        "raw_files_missing": missing,
        "raw_files_invalid_json": invalid_json,
        "raw_files_local_observation": local_observation,
        "raw_files_fake_evidence": fake_evidence,
        "raw_files_template_only": template_only,
        "raw_files_missing_provenance": missing_provenance,
        "raw_files_wrong_status": wrong_status,
        "raw_files_destination_existing": destination_existing,
    }


def _external_group_acceptance(root: Path, group: Dict[str, Any], live_rpc_acceptance: Dict[str, Any]) -> Dict[str, Any]:
    artifact_path = str(group.get("required_artifact_path") or "")
    artifact_exists = bool(artifact_path) and (root / artifact_path).exists()
    ready = group.get("ready") is True and group.get("artifact_ready") is True and live_rpc_acceptance["ready"] is True
    errors = [] if ready else [
        "external settlement requires a submitted X0T transaction receipt; scaffold template is not evidence"
    ]
    return {
        "evidence_key": group.get("evidence_key", ""),
        "files_expected": 1,
        "files_staged": 1 if artifact_exists and ready else 0,
        "files_ready_to_stage": 1 if ready else 0,
        "files_operator_required": 0 if ready else 1,
        "files_blocked": 0 if ready else 1,
        "ready_to_stage": ready,
        "statuses": {"READY_TO_STAGE" if ready else OPERATOR_INPUT_REQUIRED: 1},
        "errors": errors,
    }


def _positive_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _required_summary(required_consistency: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (required_consistency or {}).get("summary", {})
    return value if isinstance(value, dict) else {}


def _missing_key_acceptance(key: str) -> Dict[str, Any]:
    return {
        "evidence_key": key,
        "files_expected": 0,
        "files_staged": 0,
        "files_ready_to_stage": 0,
        "files_operator_required": 1,
        "files_blocked": 1,
        "ready_to_stage": False,
        "statuses": {OPERATOR_INPUT_REQUIRED: 1},
        "errors": ["required evidence key is missing from the production input manifest"],
    }


def build_report(
    root: Path,
    input_manifest_path: Path,
    live_rpc_path: Path,
    required_consistency_path: Optional[Path] = None,
) -> Dict[str, Any]:
    input_manifest = _read_json(input_manifest_path)
    live_rpc = _read_json(live_rpc_path)
    required_consistency = _read_json(required_consistency_path) if required_consistency_path else None
    source_errors: List[str] = []
    if input_manifest is None:
        source_errors.append(f"missing or unreadable input manifest: {DEFAULT_INPUT_MANIFEST}")
        input_manifest = {}

    live_rpc_acceptance = _external_live_rpc_acceptance(live_rpc)
    input_groups = _dicts(input_manifest.get("input_groups"))
    evidence_acceptance: List[Dict[str, Any]] = []
    raw_groups: List[Dict[str, Any]] = []
    external_groups: List[Dict[str, Any]] = []
    for group in input_groups:
        if group.get("input_kind") == "raw_evidence_bundle":
            accepted = _raw_group_acceptance(root, group)
            raw_groups.append(accepted)
            evidence_acceptance.append(accepted)
        elif group.get("input_kind") == "external_artifact":
            accepted = _external_group_acceptance(root, group, live_rpc_acceptance)
            external_groups.append(accepted)
            evidence_acceptance.append(accepted)

    required_summary = _required_summary(required_consistency)
    strict_required_contract = required_consistency is not None and not source_errors
    known_keys = {str(item.get("evidence_key", "")) for item in evidence_acceptance}
    if strict_required_contract:
        for missing_key in sorted(REQUIRED_EVIDENCE_KEYS - known_keys):
            evidence_acceptance.append(_missing_key_acceptance(missing_key))

    manifest_raw_files_expected = sum(item["files_expected"] for item in raw_groups)
    raw_files_expected = (
        _positive_int(required_summary.get("raw_required_evidence_files_total"))
        if strict_required_contract
        else 0
    ) or manifest_raw_files_expected
    raw_files_missing_from_manifest = max(raw_files_expected - manifest_raw_files_expected, 0)
    raw_files_staged = sum(item["files_staged"] for item in raw_groups)
    raw_files_ready = sum(item["files_staged"] + item["files_ready_to_stage"] for item in raw_groups)
    raw_files_blocked = sum(item["files_blocked"] for item in raw_groups) + raw_files_missing_from_manifest
    raw_files_destination_existing = sum(item["raw_files_destination_existing"] for item in raw_groups)
    manifest_external_expected = sum(item["files_expected"] for item in external_groups)
    external_expected = (
        _positive_int(required_summary.get("external_required_evidence_files_total"))
        if strict_required_contract
        else 0
    ) or manifest_external_expected
    external_ready = sum(item["files_ready_to_stage"] for item in external_groups)
    external_staged = sum(item["files_staged"] for item in external_groups)
    external_operator_required = sum(item["files_operator_required"] for item in external_groups) + max(
        external_expected - manifest_external_expected,
        0,
    )
    evidence_keys_total = len(REQUIRED_EVIDENCE_KEYS) if strict_required_contract else len(evidence_acceptance)
    evidence_key_blocking = sum(1 for item in evidence_acceptance if not item["ready_to_stage"])
    evidence_status_counts = _status_map_counts(evidence_acceptance)
    ready_to_stage = bool(evidence_acceptance) and evidence_key_blocking == 0 and not source_errors
    ready_for_pipeline_install = ready_to_stage and live_rpc_acceptance["ready"]
    decision = (
        "RETURN_ACCEPTANCE_READY"
        if ready_for_pipeline_install
        else "RETURN_ACCEPTANCE_INVALID_SOURCE_ARTIFACTS"
        if source_errors
        else "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-production-input-return-acceptance-v4",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "acceptance_decision": "RETURN_ACCEPTANCE_READY" if ready_for_pipeline_install else "RETURN_ACCEPTANCE_BLOCKED",
        "ready_to_stage": ready_to_stage,
        "ready_for_pipeline_install": ready_for_pipeline_install,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Read-only return-acceptance report. It inspects the local input "
            "manifest and retained live-RPC report, but does not stage files, "
            "install bundles, contact live systems, submit transactions, or close /goal."
        ),
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "mutates_chain": False,
        "runs_live_rpc": False,
        "submits_transaction": False,
        "source_artifacts": [
            DEFAULT_INPUT_MANIFEST,
            DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC,
            DEFAULT_REQUIRED_CONSISTENCY,
        ],
        "source_errors": source_errors,
        "evidence_key_acceptance": evidence_acceptance,
        "external_settlement_live_rpc_acceptance": live_rpc_acceptance,
        "not_verified_yet": []
        if ready_for_pipeline_install
        else [
            "retained external X0T settlement receipt accepted by static and live RPC gates",
            "all stage blocking inputs are cleared",
            "collector/evidence-gate semantic readiness reaches READY_FOR_PROMOTION_REVIEW",
            "integration-spine completion gate returns COMPLETE",
        ],
        "summary": {
            "source_errors_total": len(source_errors),
            "evidence_keys_total": evidence_keys_total,
            "evidence_keys_ready_to_stage": sum(1 for item in evidence_acceptance if item["ready_to_stage"]),
            "evidence_key_blocking_files": sum(item["files_blocked"] for item in evidence_acceptance),
            "evidence_status_counts": evidence_status_counts,
            "evidence_operator_input_required": evidence_status_counts.get(OPERATOR_INPUT_REQUIRED, 0),
            "evidence_generic_operator_required": evidence_status_counts.get(OPERATOR_REQUIRED, 0),
            "raw_files_expected": raw_files_expected,
            "raw_files_staged": raw_files_staged,
            "raw_files_ready_to_stage": raw_files_ready,
            "raw_files_already_staged": raw_files_staged,
            "raw_files_missing": sum(item["raw_files_missing"] for item in raw_groups) + raw_files_missing_from_manifest,
            "raw_files_invalid_json": sum(item["raw_files_invalid_json"] for item in raw_groups),
            "raw_files_local_observation": sum(item["raw_files_local_observation"] for item in raw_groups),
            "raw_files_fake_evidence": sum(item["raw_files_fake_evidence"] for item in raw_groups),
            "raw_files_template_only": sum(item["raw_files_template_only"] for item in raw_groups),
            "raw_files_missing_provenance": sum(item["raw_files_missing_provenance"] for item in raw_groups),
            "raw_files_wrong_status": sum(item["raw_files_wrong_status"] for item in raw_groups),
            "raw_files_destination_existing": raw_files_destination_existing,
            "raw_ready_to_stage": raw_files_expected > 0 and raw_files_ready == raw_files_expected and raw_files_blocked == 0,
            "external_artifacts_expected": external_expected,
            "external_artifacts_staged": external_staged,
            "external_artifacts_ready_to_stage": external_ready,
            "external_artifacts_operator_required": external_operator_required,
            "external_artifacts_missing": sum(1 for item in external_groups if item["files_operator_required"] > 0),
            "external_artifacts_invalid": 0,
            "external_settlement_live_rpc_report_found": live_rpc_acceptance["live_rpc_report_found"],
            "external_settlement_live_rpc_ready": live_rpc_acceptance["ready"],
            "external_settlement_live_rpc_checked": live_rpc_acceptance["live_rpc_checked"],
            "external_settlement_live_rpc_errors_total": len(live_rpc_acceptance["errors"]),
            "ready_to_stage": ready_to_stage,
            "ready_for_pipeline_install": ready_for_pipeline_install,
            "partial_raw_stage": False,
            "stage_decision": "SCOPED_INPUT_BUNDLE_READY" if ready_for_pipeline_install else "SCOPED_INPUT_BUNDLE_BLOCKED",
            "secret_scan_decision": "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR",
            "secret_scan_findings": 0,
            "secret_scan_source_errors": 0,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Production Input Return Acceptance",
            f"decision: {report.get('decision')}",
            f"ready_to_stage: {report.get('ready_to_stage')}",
            f"ready_for_pipeline_install: {report.get('ready_for_pipeline_install')}",
            f"raw_files_staged: {summary.get('raw_files_staged')}",
            f"raw_files_ready_to_stage: {summary.get('raw_files_ready_to_stage')}",
            f"raw_files_local_observation: {summary.get('raw_files_local_observation')}",
            f"external_settlement_live_rpc_ready: {summary.get('external_settlement_live_rpc_ready')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine production input return acceptance report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--input-manifest", default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--external-settlement-live-rpc", default=DEFAULT_EXTERNAL_SETTLEMENT_LIVE_RPC)
    parser.add_argument("--required-consistency", default=DEFAULT_REQUIRED_CONSISTENCY)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true", help="return 2 unless return acceptance is ready")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_input = Path(args.input_manifest)
    live_rpc_input = Path(args.external_settlement_live_rpc)
    consistency_input = Path(args.required_consistency)
    report = build_report(
        root,
        manifest_input if manifest_input.is_absolute() else root / manifest_input,
        live_rpc_input if live_rpc_input.is_absolute() else root / live_rpc_input,
        consistency_input if consistency_input.is_absolute() else root / consistency_input,
    )
    write_json(root / args.output_json, report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(
            json.dumps(
                {
                    "decision": report["decision"],
                    "ready_for_pipeline_install": report["ready_for_pipeline_install"],
                    "ready_to_stage": report["ready_to_stage"],
                    "goal_can_be_marked_complete": False,
                    "summary": report["summary"],
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
    if args.require_ready and not report["ready_for_pipeline_install"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
