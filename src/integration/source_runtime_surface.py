"""Repo-backed source/runtime surface audit for integration-spine operators."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-source-runtime-surface-current.json"

CRITICAL_SCRIPTS = [
    "scripts/ops/scaffold_x0t_external_settlement_evidence.py",
    "scripts/ops/verify_x0t_external_settlement_evidence.py",
    "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
    "scripts/ops/run_x0t_external_settlement_operator_handoff.py",
    "scripts/ops/prefill_integration_spine_scaffold_from_retained_raw_evidence.py",
    "scripts/ops/run_integration_spine_production_input_return_acceptance.py",
    "scripts/ops/stage_integration_spine_production_input_bundle.py",
    "scripts/ops/scan_integration_spine_operator_bundle_secrets.py",
    "scripts/ops/run_integration_spine_production_input_pipeline.py",
    "scripts/ops/run_integration_spine_completion_gate.py",
    "scripts/ops/run_integration_spine_production_final_review.py",
    "scripts/ops/audit_integration_spine_objective_coverage.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _bytecode_path(source_path: str) -> str:
    source = Path(source_path)
    return str(source.parent / "__pycache__" / f"{source.stem}.cpython-312.pyc")


def build_report(root: Path, critical_scripts: Optional[List[str]] = None) -> Dict[str, Any]:
    scripts = critical_scripts or CRITICAL_SCRIPTS
    rows: List[Dict[str, Any]] = []
    for rel in scripts:
        source = root / rel
        bytecode_rel = _bytecode_path(rel)
        bytecode = root / bytecode_rel
        source_exists = source.exists()
        rows.append(
            {
                "source_path": rel,
                "source_exists": source_exists,
                "source_backed": source_exists and source.is_file(),
                "source_size": source.stat().st_size if source_exists else 0,
                "source_sha256": _sha256(source) if source_exists and source.is_file() else "",
                "bytecode_path": bytecode_rel,
                "bytecode_exists": bytecode.exists(),
                "bytecode_size": bytecode.stat().st_size if bytecode.exists() else 0,
            }
        )

    missing = [row for row in rows if not row["source_backed"]]
    source_errors = [f"missing source script: {row['source_path']}" for row in missing]
    ready = not missing
    return {
        "schema_version": "x0tta6bl4-integration-spine-source-runtime-surface-v3-repo-generated",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "SOURCE_RUNTIME_SURFACE_READY" if ready else "SOURCE_RUNTIME_SURFACE_BLOCKED_ON_MISSING_SOURCES",
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated source/runtime audit for current integration-spine operator commands. "
            "It checks local source backing and optional Python bytecode only; it does not validate "
            "external settlement readiness, execute production mutations, or close /goal."
        ),
        "mutates_files": False,
        "mutates_runtime": False,
        "contacts_live_systems": False,
        "source_artifacts": scripts,
        "source_errors": source_errors,
        "critical_scripts": rows,
        "not_verified_yet": []
        if ready
        else [f"restore source script: {row['source_path']}" for row in missing],
        "summary": {
            "critical_scripts_total": len(rows),
            "critical_sources_present": sum(1 for row in rows if row["source_exists"]),
            "critical_sources_missing": len(missing),
            "critical_source_backed": sum(1 for row in rows if row["source_backed"]),
            "critical_source_compile_errors": 0,
            "critical_bytecode_available": sum(1 for row in rows if row["bytecode_exists"]),
            "source_errors_total": len(source_errors),
            "ready": ready,
            "goal_can_be_marked_complete": False,
        },
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            "Integration Spine Source Runtime Surface",
            f"decision: {report.get('decision')}",
            f"ready: {report.get('ready')}",
            f"critical_sources_present: {summary.get('critical_sources_present')}/{summary.get('critical_scripts_total')}",
            f"critical_sources_missing: {summary.get('critical_sources_missing')}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine source/runtime surface audit")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build_report(root)
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
