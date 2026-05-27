"""Read-only retained raw prefill gate for integration-spine scaffolds.

The historical current shard claimed all raw files were already filled even
when they were local observations. This module reports the stricter truth: a
file is filled only when the manifest marks it ready and it is not a template,
mock, simulated, or local-observation artifact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_INPUT_MANIFEST = ".tmp/validation-shards/integration-spine-production-input-bundle-manifest-current.json"
DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-scaffold-retained-raw-prefill-current.json"


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


def _raw_items(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for group in _dicts(manifest.get("input_groups")):
        if group.get("input_kind") != "raw_evidence_bundle":
            continue
        collector_id = str(group.get("collector_id", ""))
        evidence_key = str(group.get("evidence_key", ""))
        for item in _dicts(group.get("raw_files")):
            row = dict(item)
            row["collector_id"] = collector_id
            row["evidence_key"] = evidence_key
            rows.append(row)
    return rows


def _item_errors(item: Dict[str, Any]) -> List[str]:
    errors = [str(error) for error in item.get("errors", []) if isinstance(error, str)]
    current_status = str(item.get("current_status") or "")
    if current_status == "LOCAL_OBSERVATION":
        errors.append("raw evidence is still a local observation")
    if current_status in {"FAKE_EVIDENCE", "MOCK", "SIMULATED"}:
        errors.append("raw evidence is fake, mocked, or simulated")
    if item.get("template_rejected") is False:
        errors.append("template evidence was not rejected")
    if not item.get("required_operator_provenance_fields"):
        errors.append("required operator provenance fields are missing")
    if item.get("required_status") != "VERIFIED HERE":
        errors.append("required status must be VERIFIED HERE")
    if item.get("ready") is not True:
        errors.append("manifest item is not ready")
    return sorted(set(errors))


def build_report(root: Path, input_manifest_path: Path) -> Dict[str, Any]:
    manifest = _read_json(input_manifest_path)
    source_errors: List[str] = []
    if manifest is None:
        source_errors.append(f"missing or unreadable input manifest: {DEFAULT_INPUT_MANIFEST}")
        manifest = {}

    files: List[Dict[str, Any]] = []
    for item in _raw_items(manifest):
        source = str(item.get("source_raw_path") or "")
        destination = str(item.get("install_destination_path") or "")
        source_exists = bool(source) and (root / source).exists()
        destination_exists = bool(destination) and (root / destination).exists()
        errors = _item_errors(item)
        valid_retained_evidence = not errors and source_exists
        files.append(
            {
                "collector_id": item.get("collector_id", ""),
                "evidence_key": item.get("evidence_key", ""),
                "raw_id": str(item.get("raw_id", "")),
                "file_name": str(item.get("file_name", "")),
                "source_path": source,
                "destination_path": destination,
                "source_exists": source_exists,
                "destination_exists": destination_exists,
                "current_status": str(item.get("current_status", "")),
                "valid_retained_evidence": valid_retained_evidence,
                "already_filled": destination_exists and valid_retained_evidence,
                "ready_to_prefill": source_exists and valid_retained_evidence and not destination_exists,
                "errors": errors,
            }
        )

    raw_expected = len(files)
    raw_already_filled = sum(1 for item in files if item["already_filled"])
    raw_ready_to_prefill = sum(1 for item in files if item["ready_to_prefill"])
    raw_prefilled = 0
    blocking_raw_files = raw_expected - raw_already_filled - raw_ready_to_prefill
    ready = raw_expected > 0 and blocking_raw_files == 0 and not source_errors
    decision = (
        "PREFILL_READY"
        if ready
        else "PREFILL_INVALID_SOURCE_ARTIFACTS"
        if source_errors
        else "PREFILL_BLOCKED_ON_RETAINED_RAW_EVIDENCE"
    )

    return {
        "schema_version": "x0tta6bl4-integration-spine-scaffold-retained-raw-prefill-v4-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "prefill_decision": decision,
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only retained raw prefill gate. It distinguishes local "
            "observation files from retained production evidence and does not modify scaffold "
            "templates, raw evidence roots, external settlement files, live systems, or /goal."
        ),
        "mutates_files": False,
        "mutates_chain": False,
        "touches_external_settlement": False,
        "source_artifacts": [DEFAULT_INPUT_MANIFEST],
        "source_errors": source_errors,
        "files": files,
        "not_verified_yet": []
        if ready
        else [
            "all raw JSON files are retained production-grade evidence with VERIFIED HERE provenance",
            "local-observation raw files are replaced by operator-retained production evidence",
            "external X0T settlement receipt is submitted and verified by live RPC",
            "integration-spine completion gate returns COMPLETE",
        ],
        "summary": {
            "source_errors": len(source_errors),
            "raw_files_expected": raw_expected,
            "raw_files_already_filled": raw_already_filled,
            "raw_files_ready_to_prefill": raw_ready_to_prefill,
            "raw_files_prefilled": raw_prefilled,
            "raw_files_destination_exists": sum(1 for item in files if item["destination_exists"]),
            "raw_files_source_exists": sum(1 for item in files if item["source_exists"]),
            "raw_files_invalid_evidence": sum(1 for item in files if not item["valid_retained_evidence"]),
            "raw_files_invalid_json": 0,
            "raw_files_missing_source": sum(1 for item in files if not item["source_exists"]),
            "raw_files_local_observation": sum(1 for item in files if item["current_status"] == "LOCAL_OBSERVATION"),
            "raw_files_template_only": sum(1 for item in files if "template evidence was not rejected" in item["errors"]),
            "raw_files_wrong_status": sum(1 for item in files if "required status must be VERIFIED HERE" in item["errors"]),
            "blocking_raw_files": blocking_raw_files,
            "external_settlement_touched": False,
            "ready": ready,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Scaffold Retained Raw Prefill",
            f"prefill_decision: {report.get('prefill_decision')}",
            f"ready: {report.get('ready')}",
            f"raw_files_already_filled: {summary.get('raw_files_already_filled')}",
            f"raw_files_ready_to_prefill: {summary.get('raw_files_ready_to_prefill')}",
            f"raw_files_local_observation: {summary.get('raw_files_local_observation')}",
            f"blocking_raw_files: {summary.get('blocking_raw_files')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine scaffold retained raw prefill report")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--input-manifest", default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_input = Path(args.input_manifest)
    report = build_report(root, manifest_input if manifest_input.is_absolute() else root / manifest_input)
    output_input = Path(args.output_json)
    write_json(output_input if output_input.is_absolute() else root / output_input, report)
    if args.output == "text":
        print(_render_text(report))
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
