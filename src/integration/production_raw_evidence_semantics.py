"""Read-only semantic preflight for production raw-evidence collectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.integration.production_raw_evidence_collector_gate import build_report as build_collector_report
from src.integration.production_raw_evidence_readiness import (
    DEFAULT_INTAKE_MANIFEST,
    build_report as build_readiness_report,
    utc_now,
    write_json,
)


DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-semantics-current.json"


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _semantic_summary(readiness: Dict[str, Any]) -> Dict[str, int]:
    summary = dict(readiness.get("summary", {}))
    summary.setdefault("bundle_writes", 0)
    summary.setdefault("semantic_collectors_ready", 0)
    summary.setdefault("semantic_collectors_run", 0)
    summary.setdefault("semantic_collectors_failed", 0)
    return summary


def _semantic_preflight_results(
    root: Path,
    collectors: List[Dict[str, Any]],
    intake_manifest: Path,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for collector in collectors:
        collector_id = str(collector.get("collector_id", ""))
        if not collector_id:
            continue
        report = build_collector_report(
            root=root,
            collector_id=collector_id,
            intake_manifest=intake_manifest,
            role="semantic-preflight",
        )
        results.append({
            "collector_id": collector_id,
            "decision": report.get("decision", "BLOCKED"),
            "ready": report.get("ready") is True,
            "raw_files_total": report.get("summary", {}).get("raw_files_total", 0),
            "raw_files_ready": report.get("summary", {}).get("raw_files_ready", 0),
            "raw_files_local_observation": report.get("summary", {}).get("raw_files_local_observation", 0),
            "source_errors": report.get("source_errors", []),
        })
    return results


def build_report(
    root: Path,
    intake_manifest: Path = Path(DEFAULT_INTAKE_MANIFEST),
) -> Dict[str, Any]:
    readiness = build_readiness_report(root, intake_manifest)
    collectors = _dicts(readiness.get("collectors"))
    source_errors = list(readiness.get("source_errors", []))
    raw_ready = readiness.get("ready_for_collectors") is True
    semantic_results: List[Dict[str, Any]] = []
    summary = _semantic_summary(readiness)

    if source_errors:
        decision = "INVALID_SOURCE_ARTIFACTS"
    elif not raw_ready:
        decision = "BLOCKED_RAW_INPUTS"
    else:
        semantic_results = _semantic_preflight_results(root, collectors, intake_manifest)
        semantic_ready = sum(1 for item in semantic_results if item.get("ready") is True)
        semantic_failed = sum(1 for item in semantic_results if item.get("ready") is not True)
        summary["semantic_collectors_run"] = len(semantic_results)
        summary["semantic_collectors_ready"] = semantic_ready
        summary["semantic_collectors_failed"] = semantic_failed
        decision = "READY_FOR_PIPELINE_EXECUTION" if semantic_failed == 0 and semantic_results else "BLOCKED_SEMANTIC_READINESS"

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-semantics-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only semantic raw evidence preflight. It uses the current intake manifest and "
            "raw readiness report as source of truth, runs semantic collector dry-runs only after "
            "all raw files are production-ready, and never writes evidence bundles, contacts live "
            "systems, mutates runtime state, or promotes /goal completion."
        ),
        "raw_evidence_readiness_decision": readiness.get("raw_evidence_readiness_decision", ""),
        "semantic_readiness_decision": decision,
        "runs_semantic_collectors": bool(raw_ready and not source_errors),
        "writes_report_outputs": True,
        "bundle_writes": 0,
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
        "source_artifacts": [str(intake_manifest)],
        "source_errors": source_errors,
        "semantic_results": semantic_results,
        "summary": summary,
        "not_verified_yet": [] if decision == "READY_FOR_PIPELINE_EXECUTION" else [
            "all retained raw production evidence files READY_FOR_COLLECTOR",
            "semantic collector dry-run READY for every collector",
            "materializing pipeline execution",
            "production-grade /goal completion",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only production raw-evidence semantic preflight")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.intake_manifest)
    output_path = Path(args.output_json)
    report = build_report(root, manifest_path if manifest_path.is_absolute() else root / manifest_path)
    write_json(output_path if output_path.is_absolute() else root / output_path, report)
    print(json.dumps({
        "decision": report["semantic_readiness_decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["semantic_readiness_decision"] != "READY_FOR_PIPELINE_EXECUTION":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
