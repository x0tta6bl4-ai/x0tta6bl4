"""Fail-closed entrypoints for planned production raw-evidence collectors.

These entrypoints are intentionally read-only. They exist so the raw-evidence
pipeline can point operators at concrete commands while still refusing to run
or materialize anything until retained raw files are replaced with production
operator evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.production_raw_evidence_readiness import (
    DEFAULT_INTAKE_MANIFEST,
    build_report as build_readiness_report,
    utc_now,
    write_json,
)


VALID_MODES = {"collector", "gate"}


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _find_collector(readiness: Dict[str, Any], collector_id: str) -> Optional[Dict[str, Any]]:
    for collector in _dicts(readiness.get("collectors")):
        if collector.get("collector_id") == collector_id:
            return collector
    return None


def _raw_root_mismatch(
    root: Path,
    requested_raw_root: str,
    collector: Optional[Dict[str, Any]],
) -> str:
    if not requested_raw_root or collector is None:
        return ""
    files = _dicts(collector.get("files"))
    if not files:
        return ""

    requested = Path(requested_raw_root)
    requested_abs = requested if requested.is_absolute() else root / requested
    for item in files:
        path_value = str(item.get("path", ""))
        if not path_value:
            continue
        raw_path = Path(path_value)
        raw_abs = raw_path if raw_path.is_absolute() else root / raw_path
        try:
            raw_abs.relative_to(requested_abs)
        except ValueError:
            return (
                f"--raw-root {requested_raw_root} does not contain manifest raw file "
                f"{path_value}"
            )
    return ""


def _decision(mode: str, ready: bool, source_errors: List[str], collector_missing: bool) -> str:
    prefix = f"RAW_EVIDENCE_{mode.upper()}"
    if source_errors:
        return f"{prefix}_INVALID_SOURCE_ARTIFACTS"
    if collector_missing:
        return f"{prefix}_UNKNOWN_COLLECTOR"
    if ready:
        return f"{prefix}_READY"
    return f"{prefix}_BLOCKED"


def build_report(
    root: Path,
    collector_id: str,
    mode: str,
    intake_manifest_path: Path = Path(DEFAULT_INTAKE_MANIFEST),
    *,
    raw_root: str = "",
) -> Dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")

    readiness = build_readiness_report(root, intake_manifest_path)
    collector = _find_collector(readiness, collector_id)
    source_errors = list(readiness.get("source_errors", []))
    mismatch = _raw_root_mismatch(root, raw_root, collector)
    if mismatch:
        source_errors.append(mismatch)

    collector_missing = collector is None
    collector_ready = bool(collector and collector.get("collector_ready") is True)
    ready = bool(collector_ready and not source_errors)
    summary = {
        **dict(readiness.get("summary", {})),
        "selected_collectors_total": 0 if collector_missing else 1,
        "selected_collectors_ready": 1 if ready else 0,
        "selected_collectors_blocked": 0 if ready else 1,
        "selected_raw_files_total": int((collector or {}).get("raw_files_total", 0) or 0),
        "selected_raw_files_ready": int((collector or {}).get("raw_files_ready", 0) or 0),
        "selected_raw_files_local_observation": int(
            (collector or {}).get("raw_files_local_observation", 0) or 0
        ),
    }

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-entrypoint-v1-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "mode": mode,
        "collector_id": collector_id,
        "claim_boundary": (
            "Read-only raw-evidence entrypoint. It checks whether operator raw evidence is ready "
            "for this planned collector/gate and refuses to collect, synthesize, or promote evidence."
        ),
        "entrypoint_decision": _decision(mode, ready, source_errors, collector_missing),
        "raw_evidence_readiness_decision": readiness.get("raw_evidence_readiness_decision", ""),
        "ready_for_entrypoint_execution": ready,
        "collector_ready": collector_ready,
        "execution_requested": False,
        "execution_performed": False,
        "runs_collector": False,
        "runs_evidence_gate": False,
        "writes_report_outputs": True,
        "materializes_evidence": False,
        "mutates_files": False,
        "mutates_files_outside_outputs": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "runs_live_cluster": False,
        "runs_live_customer_path": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "goal_can_be_marked_complete": False,
        "requested_raw_root": raw_root,
        "source_artifacts": [str(intake_manifest_path)],
        "source_errors": source_errors,
        "collector": collector or {},
        "summary": summary,
        "not_verified_yet": [] if ready else [
            "operator-supplied production raw evidence for the selected collector",
            "selected raw files with production_ready=true and empty production_promotion_blockers",
            "production context without local/test/staging/simulation claim boundaries",
        ],
    }


def main_for_collector(
    collector_id: str,
    mode: str,
    default_output: str,
    argv: Optional[List[str]] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=f"Check fail-closed production raw-evidence {mode} entrypoint"
    )
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--raw-root", default="", help="expected raw evidence root")
    parser.add_argument("--output-json", default=default_output)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.intake_manifest)
    output_path = Path(args.output_json)
    report = build_report(
        root,
        collector_id,
        mode,
        manifest_path if manifest_path.is_absolute() else root / manifest_path,
        raw_root=args.raw_root,
    )
    write_json(output_path if output_path.is_absolute() else root / output_path, report)
    print(json.dumps({
        "collector_id": collector_id,
        "decision": report["entrypoint_decision"],
        "ready_for_entrypoint_execution": report["ready_for_entrypoint_execution"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready_for_entrypoint_execution"]:
        return 2
    return 0
