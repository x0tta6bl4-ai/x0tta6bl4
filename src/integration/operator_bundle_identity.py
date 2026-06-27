"""Read-only manifest identity plan for operator evidence bundles.

The report helps operators line up production bundle JSON files with the
machine-readable intake manifest. It never writes evidence files and does not
upgrade production readiness by itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.evidence_source_candidates import (
    COLLECTOR_BY_KEY,
    DEFAULT_INTAKE_MANIFEST,
    DEFAULT_OPERATOR_BUNDLE_ROOT,
    utc_now,
)


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-operator-bundle-identity-current.json"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    if not path.exists():
        return None, "artifact missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"artifact unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "artifact root must be a JSON object"
    return data, ""


def _collector_entries(manifest: Optional[Dict[str, Any]], collector_id: str) -> List[Dict[str, Any]]:
    if not manifest:
        return []
    collectors = manifest.get("collectors", [])
    if not isinstance(collectors, list):
        return []
    for collector in collectors:
        if isinstance(collector, dict) and collector.get("collector_id") == collector_id:
            raw_files = collector.get("raw_files", [])
            return [item for item in raw_files if isinstance(item, dict)]
    return []


def _collector_ids(evidence_key: str) -> List[str]:
    if evidence_key:
        if evidence_key not in COLLECTOR_BY_KEY:
            raise ValueError(f"unsupported evidence_key: {evidence_key}")
        return [COLLECTOR_BY_KEY[evidence_key]]
    return sorted(set(COLLECTOR_BY_KEY.values()))


def _file_report(
    *,
    root: Path,
    operator_bundle_root: Path,
    operator_bundle_root_display: str,
    collector_id: str,
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    raw_id = str(entry.get("raw_id", ""))
    file_name = str(entry.get("file_name", raw_id.split("/")[-1]))
    bundle_path = operator_bundle_root / collector_id / file_name
    display_path = f"{operator_bundle_root_display}/{collector_id}/{file_name}"
    data, read_error = _read_json(bundle_path if bundle_path.is_absolute() else root / bundle_path)
    expected = {
        "collector_id": collector_id,
        "raw_id": raw_id,
        "file_name": file_name,
    }
    actual = {
        "collector_id": data.get("collector_id") if data else None,
        "raw_id": data.get("raw_id") if data else None,
        "file_name": data.get("file_name") if data else None,
    }
    mismatches = [
        field
        for field, expected_value in expected.items()
        if data is not None and actual[field] != expected_value
    ]
    json_patch_operations = [
        {"op": "add" if actual[field] is None else "replace", "path": f"/{field}", "value": expected[field]}
        for field in mismatches
    ]
    return {
        "path": display_path,
        "available": data is not None,
        "read_error": read_error,
        "manifest_collector_id": collector_id,
        "manifest_raw_id": raw_id,
        "manifest_file_name": file_name,
        "evidence_collector_id": actual["collector_id"],
        "evidence_raw_id": actual["raw_id"],
        "evidence_file_name": actual["file_name"],
        "suggested_fields": expected,
        "json_merge_patch": expected if mismatches else {},
        "json_patch_operations": json_patch_operations,
        "identity_mismatch_fields": mismatches,
        "needs_identity_update": bool(mismatches),
        "clean": data is not None and not mismatches,
    }


def _identity_update_entry(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": report.get("path", ""),
        "available": report.get("available"),
        "suggested_fields": report.get("suggested_fields", {}),
        "current_fields": {
            "collector_id": report.get("evidence_collector_id"),
            "raw_id": report.get("evidence_raw_id"),
            "file_name": report.get("evidence_file_name"),
        },
        "identity_mismatch_fields": report.get("identity_mismatch_fields", []),
        "json_merge_patch": report.get("json_merge_patch", {}),
        "json_patch_operations": report.get("json_patch_operations", []),
    }


def build_report(
    *,
    root: Path,
    evidence_key: str = "",
    intake_manifest: str = DEFAULT_INTAKE_MANIFEST,
    operator_bundle_root: str = DEFAULT_OPERATOR_BUNDLE_ROOT,
) -> Dict[str, Any]:
    manifest_path = _resolve(root, intake_manifest)
    bundle_root_path = _resolve(root, operator_bundle_root)
    manifest, manifest_error = _read_json(manifest_path)
    collectors = _collector_ids(evidence_key)
    file_reports: List[Dict[str, Any]] = []
    collector_reports: List[Dict[str, Any]] = []

    for collector_id in collectors:
        entries = _collector_entries(manifest, collector_id)
        reports = [
            _file_report(
                root=root,
                operator_bundle_root=bundle_root_path,
                operator_bundle_root_display=str(Path(operator_bundle_root)),
                collector_id=collector_id,
                entry=entry,
            )
            for entry in entries
        ]
        file_reports.extend(reports)
        collector_reports.append(
            {
                "collector_id": collector_id,
                "raw_files_total": len(entries),
                "files_available": sum(1 for report in reports if report["available"]),
                "files_clean": sum(1 for report in reports if report["clean"]),
                "files_needing_identity_update": sum(1 for report in reports if report["needs_identity_update"]),
            }
        )

    files_total = len(file_reports)
    missing_or_unreadable = [report for report in file_reports if not report["available"]]
    identity_updates = [report for report in file_reports if report["needs_identity_update"]]
    identity_update_plan = [_identity_update_entry(report) for report in identity_updates]
    ready = not manifest_error and files_total > 0 and not missing_or_unreadable and not identity_updates

    summary = {
        "collectors_total": len(collectors),
        "files_total": files_total,
        "files_available": sum(1 for report in file_reports if report["available"]),
        "files_missing_or_unreadable": len(missing_or_unreadable),
        "files_clean": sum(1 for report in file_reports if report["clean"]),
        "files_needing_identity_update": len(identity_updates),
        "manifest_identity_mismatches_total": sum(len(report["identity_mismatch_fields"]) for report in identity_updates),
        "collector_id_mismatches": sum(1 for report in identity_updates if "collector_id" in report["identity_mismatch_fields"]),
        "raw_id_mismatches": sum(1 for report in identity_updates if "raw_id" in report["identity_mismatch_fields"]),
        "file_name_mismatches": sum(1 for report in identity_updates if "file_name" in report["identity_mismatch_fields"]),
        "identity_patch_entries_total": len(identity_update_plan),
        "identity_patch_operations_total": sum(len(entry["json_patch_operations"]) for entry in identity_update_plan),
        "clean": ready,
    }

    return {
        "schema_version": "x0tta6bl4-integration-spine-operator-bundle-identity-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only manifest identity plan for operator-supplied evidence bundles. "
            "It reports expected collector_id/raw_id/file_name values from the intake manifest, "
            "but does not create, edit, promote, or validate production evidence."
        ),
        "decision": "OPERATOR_BUNDLE_IDENTITY_CLEAN" if ready else "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED",
        "goal_can_be_marked_complete": False,
        "evidence_key": evidence_key,
        "collector_ids": collectors,
        "source_artifacts": [str(Path(intake_manifest)), str(Path(operator_bundle_root))],
        "manifest_error": manifest_error,
        "summary": summary,
        "collector_reports": collector_reports,
        "file_reports": file_reports,
        "identity_update_plan": identity_update_plan,
        "operator_safe_patch_note": (
            "The json_merge_patch/json_patch_operations entries only bind manifest identity fields. "
            "Applying them does not make local, simulated, or incomplete files production evidence."
        ),
        "required_next_evidence": [] if ready else [
            "add collector_id/raw_id/file_name fields that exactly match the intake manifest to every operator bundle JSON file",
            "rerun the domain collector, source-candidate audit, production intake, and production gap index",
        ],
        "not_verified_yet": [] if ready else [
            "operator bundle files carry manifest identity metadata for every required raw file",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only operator bundle manifest identity plan")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--evidence-key", default="", help="optional required evidence key to scope the report")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        evidence_key=args.evidence_key,
        intake_manifest=args.intake_manifest,
        operator_bundle_root=args.operator_bundle_root,
    )
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["decision"],
        "evidence_key": report["evidence_key"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_clean and report["decision"] != "OPERATOR_BUNDLE_IDENTITY_CLEAN":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
