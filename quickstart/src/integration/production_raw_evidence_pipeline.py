"""Read-only pipeline plan for production raw-evidence collectors.

The pipeline report is intentionally non-executing. It derives current raw
readiness from the same classifier as the readiness gate, builds the collector
execution plan, and fails closed while retained/local evidence is not replaced
with operator production evidence.
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
)


DEFAULT_OUTPUT = ".tmp/validation-shards/production-raw-evidence-pipeline-current.json"
DEFAULT_SEMANTIC_READINESS = ".tmp/validation-shards/production-raw-evidence-semantics-current.json"


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


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _collector_gate_script(collector_id: str) -> str:
    return f"scripts/ops/verify_{collector_id.replace('-', '_')}_evidence_gate.py"


def _append_require_ready(command: str) -> str:
    return command if "--require-ready" in command.split() else f"{command} --require-ready"


def _manifest_collectors(manifest: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    collectors: Dict[str, Dict[str, Any]] = {}
    for collector in _dicts((manifest or {}).get("collectors")):
        collector_id = str(collector.get("collector_id", ""))
        if collector_id:
            collectors[collector_id] = collector
    return collectors


def _planned_steps(
    root: Path,
    readiness: Dict[str, Any],
    manifest: Optional[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], int]:
    manifest_by_collector = _manifest_collectors(manifest)
    steps: List[Dict[str, Any]] = []
    missing_entrypoints = 0
    for collector in _dicts(readiness.get("collectors")):
        collector_id = str(collector.get("collector_id", ""))
        manifest_collector = manifest_by_collector.get(collector_id, {})
        collector_script = str(
            manifest_collector.get("collector_script")
            or collector.get("collector_script")
            or f"scripts/ops/collect_{collector_id.replace('-', '_')}_evidence_bundle.py"
        )
        collector_command = str(
            manifest_collector.get("collector_command")
            or f"python3 {collector_script} --raw-root {manifest_collector.get('raw_root', '')}".strip()
        )
        gate_script = _collector_gate_script(collector_id)
        collector_exists = (root / collector_script).exists()
        gate_exists = (root / gate_script).exists()
        if not collector_exists or not gate_exists:
            missing_entrypoints += 1
        steps.append(
            {
                "collector_id": collector_id,
                "collector_ready": collector.get("collector_ready") is True,
                "collector_script": collector_script,
                "collector_script_exists": collector_exists,
                "collector_command": _append_require_ready(collector_command),
                "evidence_gate_script": gate_script,
                "evidence_gate_script_exists": gate_exists,
                "evidence_gate_command": f"python3 {gate_script} --require-ready",
                "raw_root": str(manifest_collector.get("raw_root", "")),
                "raw_files_total": collector.get("raw_files_total", 0),
                "raw_files_ready": collector.get("raw_files_ready", 0),
                "raw_files_local_observation": collector.get("raw_files_local_observation", 0),
            }
        )
    return steps, missing_entrypoints


def _semantic_ready(semantic: Optional[Dict[str, Any]], require_semantic: bool) -> bool:
    if not require_semantic:
        return True
    if not semantic:
        return False
    summary = semantic.get("summary", {})
    return (
        semantic.get("semantic_readiness_decision") in {"READY_FOR_PIPELINE_EXECUTION", "READY"}
        or (
            isinstance(summary, dict)
            and summary.get("collectors_ready") == summary.get("collectors_total")
            and summary.get("collectors_total", 0) > 0
        )
    )


def build_report(
    root: Path,
    intake_manifest_path: Path = Path(DEFAULT_INTAKE_MANIFEST),
    semantic_readiness_path: Path = Path(DEFAULT_SEMANTIC_READINESS),
    *,
    require_semantic_readiness: bool = True,
) -> Dict[str, Any]:
    readiness = build_readiness_report(root, intake_manifest_path)
    manifest, manifest_error = _read_json(intake_manifest_path)
    semantic, semantic_error = _read_json(semantic_readiness_path)
    readiness_summary = dict(readiness.get("summary", {}))
    steps, missing_entrypoints = _planned_steps(root, readiness, manifest)
    source_errors = list(readiness.get("source_errors", []))
    if manifest_error:
        source_errors.append(f"{intake_manifest_path}: {manifest_error}")
    if require_semantic_readiness and semantic_error:
        source_errors.append(f"{semantic_readiness_path}: {semantic_error}")

    raw_ready = readiness.get("ready_for_collectors") is True
    semantic_ok = _semantic_ready(semantic, require_semantic_readiness)
    entrypoints_ok = missing_entrypoints == 0
    ready = bool(raw_ready and semantic_ok and entrypoints_ok and not source_errors)
    if source_errors:
        decision = "PIPELINE_INVALID_SOURCE_ARTIFACTS"
    elif not raw_ready:
        decision = "BLOCKED_RAW_INPUTS"
    elif not semantic_ok:
        decision = "BLOCKED_SEMANTIC_READINESS"
    elif not entrypoints_ok:
        decision = "BLOCKED_MISSING_ENTRYPOINTS"
    else:
        decision = "READY_FOR_COLLECTOR_EXECUTION"

    semantic_summary = semantic.get("summary", {}) if isinstance(semantic, dict) else {}
    summary = {
        **readiness_summary,
        "planned_steps_total": len(steps),
        "missing_entrypoints": missing_entrypoints,
        "missing_gate_mappings": 0,
        "collectors_run": 0,
        "evidence_gates_run": 0,
        "command_results_total": 0,
        "semantic_collectors_ready": int(semantic_summary.get("semantic_collectors_ready", 0) or 0),
        "semantic_collectors_run": int(semantic_summary.get("semantic_collectors_run", 0) or 0),
        "semantic_collectors_failed": int(semantic_summary.get("semantic_collectors_failed", 0) or 0),
        "semantic_bundle_writes": int(semantic_summary.get("bundle_writes", 0) or 0),
    }

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-pipeline-v2-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only production raw-evidence pipeline plan. It derives readiness from retained raw "
            "evidence and builds collector commands, but it does not run collectors, run evidence gates, "
            "write raw evidence, contact live systems, mutate runtime state, or mark /goal complete."
        ),
        "pipeline_decision": decision,
        "raw_evidence_readiness_decision": readiness.get("raw_evidence_readiness_decision", ""),
        "semantic_readiness_decision": (semantic or {}).get("semantic_readiness_decision", ""),
        "semantic_ready_for_pipeline_execution": semantic_ok,
        "entrypoints_ready_for_pipeline_execution": entrypoints_ok,
        "requires_semantic_readiness": require_semantic_readiness,
        "ready_for_collector_execution": ready,
        "execution_requested": False,
        "execution_performed": False,
        "runs_collectors": False,
        "runs_evidence_gates": False,
        "runs_semantic_collectors": False,
        "writes_report_outputs": False,
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
        "source_artifacts": [str(intake_manifest_path), str(semantic_readiness_path)],
        "source_errors": source_errors,
        "planned_steps": steps,
        "command_results": [],
        "summary": summary,
        "not_verified_yet": [] if ready else [
            "raw evidence readiness must reach READY_FOR_COLLECTORS",
            "semantic raw-evidence readiness must be clear",
            "planned collector and evidence-gate entrypoints must exist",
            "operator must run the listed collectors and evidence gates only after source evidence is production-ready",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build read-only production raw-evidence pipeline plan")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--semantic-readiness", default=DEFAULT_SEMANTIC_READINESS)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--no-require-semantic-readiness", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.intake_manifest)
    semantic_path = Path(args.semantic_readiness)
    output_path = Path(args.output_json)
    report = build_report(
        root,
        manifest_path if manifest_path.is_absolute() else root / manifest_path,
        semantic_path if semantic_path.is_absolute() else root / semantic_path,
        require_semantic_readiness=not args.no_require_semantic_readiness,
    )
    write_json(output_path if output_path.is_absolute() else root / output_path, report)
    print(json.dumps({
        "decision": report["pipeline_decision"],
        "ready_for_collector_execution": report["ready_for_collector_execution"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and not report["ready_for_collector_execution"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
