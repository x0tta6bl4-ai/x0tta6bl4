"""Read-only collector/gate entrypoint for production raw-evidence bundles."""

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


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _collector_from_manifest(readiness: Dict[str, Any], collector_id: str) -> Dict[str, Any]:
    for item in _dicts(readiness.get("collectors")):
        if item.get("collector_id") == collector_id:
            return item
    return {}


def _collector_raw_root(collector: Dict[str, Any], collector_id: str, raw_root: str) -> str:
    if raw_root:
        return raw_root
    files = _dicts(collector.get("files"))
    if files:
        path = str(files[0].get("path", ""))
        suffix = "/" + str(files[0].get("path", "")).split("/")[-1]
        if path.endswith(suffix):
            return path[: -len(suffix)]
    return f".tmp/{collector_id}-raw-evidence"


def build_report(
    *,
    root: Path,
    collector_id: str,
    intake_manifest: Path = Path(DEFAULT_INTAKE_MANIFEST),
    raw_root: str = "",
    role: str = "collector",
) -> Dict[str, Any]:
    readiness = build_readiness_report(root, intake_manifest)
    collector = _collector_from_manifest(readiness, collector_id)
    source_errors = list(readiness.get("source_errors", []))
    if not collector:
        source_errors.append(f"collector_id not declared in intake manifest: {collector_id}")

    ready = bool(collector) and collector.get("collector_ready") is True and not source_errors
    raw_files = _dicts(collector.get("files"))
    summary = {
        "collector_ready": ready,
        "raw_files_total": int(collector.get("raw_files_total", 0) or 0),
        "raw_files_ready": int(collector.get("raw_files_ready", 0) or 0),
        "raw_files_local_observation": int(collector.get("raw_files_local_observation", 0) or 0),
        "raw_files_placeholder_values": int(collector.get("raw_files_placeholder_values", 0) or 0),
        "raw_files_missing_provenance": int(collector.get("raw_files_missing_provenance", 0) or 0),
        "source_errors_total": len(source_errors),
    }

    return {
        "schema_version": "x0tta6bl4-production-raw-evidence-collector-gate-v1",
        "generated_at": utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "claim_boundary": (
            "Read-only production raw-evidence collector/gate entrypoint. It validates retained "
            "raw evidence for one collector through the production readiness classifier, but it "
            "does not collect live evidence, write raw evidence, contact live systems, mutate "
            "runtime state, or mark the objective complete."
        ),
        "role": role,
        "collector_id": collector_id,
        "raw_root": _collector_raw_root(collector, collector_id, raw_root),
        "decision": "READY" if ready else "BLOCKED",
        "ready": ready,
        "goal_can_be_marked_complete": False,
        "materializes_evidence": False,
        "runs_live_cluster": False,
        "runs_live_customer_path": False,
        "runs_live_payment_processor": False,
        "runs_live_registry": False,
        "mutates_files": False,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "source_artifacts": [str(intake_manifest)],
        "source_errors": source_errors,
        "raw_files": raw_files,
        "summary": summary,
        "not_verified_yet": [] if ready else [
            f"{collector_id} raw evidence is not production ready",
            "operator must replace retained/local/component evidence with production-ready JSON",
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(
    argv: Optional[List[str]] = None,
    *,
    default_collector_id: str = "",
    default_output: str = "",
    role: str = "collector",
) -> int:
    parser = argparse.ArgumentParser(description="Validate one production raw-evidence collector bundle")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--collector-id", default=default_collector_id)
    parser.add_argument("--raw-root", default="")
    parser.add_argument("--intake-manifest", default=DEFAULT_INTAKE_MANIFEST)
    parser.add_argument("--output-json", default=default_output)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)

    if not args.collector_id:
        raise SystemExit("--collector-id is required")
    if not args.output_json:
        raise SystemExit("--output-json is required")

    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        collector_id=args.collector_id,
        intake_manifest=_resolve(root, args.intake_manifest),
        raw_root=args.raw_root,
        role=role,
    )
    write_json(_resolve(root, args.output_json), report)
    print(json.dumps({
        "collector_id": report["collector_id"],
        "decision": report["decision"],
        "goal_can_be_marked_complete": False,
        "summary": report["summary"],
    }, ensure_ascii=True, sort_keys=True))
    if args.require_ready and report["ready"] is not True:
        return 2
    return 0


def main_for_collector(
    collector_id: str,
    default_output: str,
    argv: Optional[List[str]] = None,
    *,
    role: str = "collector",
) -> int:
    return main(argv, default_collector_id=collector_id, default_output=default_output, role=role)


if __name__ == "__main__":
    raise SystemExit(main())
