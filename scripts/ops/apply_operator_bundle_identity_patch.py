#!/usr/bin/env python3
"""Apply only manifest identity fields to operator raw-evidence bundle files.

The command is intentionally narrow. It can add/replace collector_id, raw_id,
and file_name under the operator bundle root. It never promotes production
readiness, changes evidence status, installs retained evidence, contacts live
systems, or mutates runtime state.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.evidence_source_candidates import DEFAULT_OPERATOR_BUNDLE_ROOT
from src.integration.operator_bundle_identity import DEFAULT_OUTPUT as DEFAULT_IDENTITY_REPORT


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-operator-bundle-identity-patch-current.json"
ALLOWED_FIELDS = {"collector_id", "raw_id", "file_name"}
ALLOWED_OPS = {"add", "replace"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _field_from_json_pointer(pointer: Any) -> str:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return ""
    field = pointer.strip("/")
    return field if "/" not in field else ""


def _validated_operations(entry: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    operations: List[Dict[str, Any]] = []
    raw_ops = entry.get("json_patch_operations", [])
    if not isinstance(raw_ops, list):
        return [], ["json_patch_operations must be a list"]
    for idx, op in enumerate(raw_ops):
        if not isinstance(op, dict):
            errors.append(f"json_patch_operations[{idx}] must be an object")
            continue
        action = str(op.get("op", ""))
        field = _field_from_json_pointer(op.get("path"))
        value = op.get("value")
        if action not in ALLOWED_OPS:
            errors.append(f"{field or op.get('path')} uses unsupported op {action}")
            continue
        if field not in ALLOWED_FIELDS:
            errors.append(f"{op.get('path')} is not an allowed identity field")
            continue
        if not isinstance(value, str) or not value:
            errors.append(f"{field} value must be a non-empty string")
            continue
        operations.append({"op": action, "field": field, "path": f"/{field}", "value": value})
    return operations, errors


def build_patch_report(
    *,
    root: Path,
    identity_report_path: Path,
    operator_bundle_root: Path,
    apply: bool = False,
    identity_report_display: str = DEFAULT_IDENTITY_REPORT,
    operator_bundle_root_display: str = DEFAULT_OPERATOR_BUNDLE_ROOT,
) -> Dict[str, Any]:
    identity_report, read_error = _read_json(identity_report_path)
    plan = (identity_report or {}).get("identity_update_plan", [])
    errors: List[str] = []
    file_results: List[Dict[str, Any]] = []
    operations_total = 0
    operations_pending = 0
    operations_applied = 0
    would_update_files = 0
    updated_files = 0
    unsafe_operations = 0

    if read_error:
        errors.append(f"identity report is missing or unreadable: {identity_report_display}: {read_error}")
        plan = []
    if not isinstance(plan, list):
        errors.append("identity_update_plan must be a list")
        plan = []

    bundle_root_resolved = operator_bundle_root.resolve()

    for entry in plan:
        if not isinstance(entry, dict):
            errors.append("identity_update_plan entry must be an object")
            continue
        display_path = str(entry.get("path", ""))
        target_path = _resolve(root, display_path)
        entry_errors: List[str] = []
        if not display_path:
            entry_errors.append("path is required")
        if display_path and not _is_under(target_path, bundle_root_resolved):
            entry_errors.append("path is outside operator bundle root")

        operations, operation_errors = _validated_operations(entry)
        entry_errors.extend(operation_errors)
        operations_total += len(operations)
        unsafe_operations += len(operation_errors)

        data, file_error = _read_json(target_path)
        if file_error:
            entry_errors.append(file_error)
        pending_ops: List[Dict[str, Any]] = []
        applied_ops: List[Dict[str, Any]] = []

        if data is not None and not entry_errors:
            for op in operations:
                current = data.get(op["field"])
                op_result = dict(op)
                op_result["current_value"] = current
                op_result["pending"] = current != op["value"]
                if current != op["value"]:
                    pending_ops.append(op_result)
                    if apply:
                        data[op["field"]] = op["value"]
                        applied_ops.append(op_result)
                else:
                    op_result["pending"] = False

        operations_pending += len(pending_ops)
        operations_applied += len(applied_ops)
        if pending_ops:
            would_update_files += 1
        if applied_ops:
            updated_files += 1

        if apply and applied_ops and data is not None and not entry_errors:
            _write_json(target_path, data)

        if entry_errors:
            errors.extend(f"{display_path}: {error}" for error in entry_errors)

        file_results.append(
            {
                "path": display_path,
                "available": data is not None,
                "safe_path": display_path != "" and _is_under(target_path, bundle_root_resolved),
                "errors": entry_errors,
                "operations_total": len(operations),
                "operations_pending": len(pending_ops),
                "operations_applied": len(applied_ops),
                "would_update": bool(pending_ops),
                "updated": bool(applied_ops),
                "pending_operations": pending_ops,
            }
        )

    if errors:
        decision = "IDENTITY_PATCH_BLOCKED"
    elif apply:
        decision = "IDENTITY_PATCH_APPLIED" if updated_files else "IDENTITY_PATCH_NOT_NEEDED"
    else:
        decision = "IDENTITY_PATCH_DRY_RUN_READY" if would_update_files else "IDENTITY_PATCH_NOT_NEEDED"

    return {
        "schema_version": "x0tta6bl4-operator-bundle-identity-patch-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": decision,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Safe identity-only operator bundle patch report. The command only permits collector_id, "
            "raw_id, and file_name changes under the operator bundle root. It does not make evidence "
            "production-ready, change evidence status, install retained files, call live systems, or "
            "mutate NL/SPB/VPN runtime."
        ),
        "source_artifacts": [identity_report_display, operator_bundle_root_display],
        "allowed_fields": sorted(ALLOWED_FIELDS),
        "apply_requested": apply,
        "mutates_files": apply and updated_files > 0,
        "mutates_files_outside_operator_bundle": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "materializes_evidence": False,
        "installs_raw_evidence": False,
        "promotes_production_ready": False,
        "changes_evidence_status": False,
        "errors": errors,
        "file_results": file_results,
        "summary": {
            "plan_entries_total": len(plan),
            "files_checked": len(file_results),
            "blocked_files": sum(1 for item in file_results if item.get("errors")),
            "would_update_files": would_update_files,
            "updated_files": updated_files,
            "operations_total": operations_total,
            "operations_pending": operations_pending,
            "operations_applied": operations_applied,
            "unsafe_operations_total": unsafe_operations,
        },
        "not_verified_yet": []
        if decision == "IDENTITY_PATCH_NOT_NEEDED"
        else [
            "identity-only operator bundle patch has not made evidence production-ready",
            "production_ready, evidence status, live settlement, and semantic blockers still need separate proof",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safely apply operator bundle manifest identity fields")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--identity-report", default=DEFAULT_IDENTITY_REPORT)
    parser.add_argument("--operator-bundle-root", default=DEFAULT_OPERATOR_BUNDLE_ROOT)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--apply", action="store_true", help="write identity fields to operator bundle files")
    parser.add_argument("--require-applied", action="store_true", help="return 2 unless --apply changed at least one file")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_patch_report(
        root=root,
        identity_report_path=_resolve(root, args.identity_report),
        operator_bundle_root=_resolve(root, args.operator_bundle_root),
        apply=args.apply,
        identity_report_display=str(Path(args.identity_report)),
        operator_bundle_root_display=str(Path(args.operator_bundle_root)),
    )
    _write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "apply_requested": report["apply_requested"],
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if report["decision"] == "IDENTITY_PATCH_BLOCKED":
        return 2
    if args.require_applied and report["decision"] != "IDENTITY_PATCH_APPLIED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
