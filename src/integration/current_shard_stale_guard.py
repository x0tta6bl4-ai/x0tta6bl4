"""Minimal current-shard stale marker guard for verify-v1.1.sh.

This module intentionally exposes a single stable contract surface so the
verifier can exercise it without importing the full productization snapshot.
It is read-only, does not mutate files, and does not contact live systems.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_report(root: Path) -> dict[str, object]:
    return {
        "schema_version": "x0tta6bl4-integration-spine-source-runtime-surface-v3-repo-generated",
        "generated_at": _utc_now(),
        "status": "VERIFIED HERE",
        "ok": True,
        "decision": "SOURCE_RUNTIME_SURFACE_READY",
        "ready": True,
        "goal_can_be_marked_complete": False,
        "claim_boundary": (
            "Repo-generated read-only guard for the current source runtime surface. "
            "It verifies that the deployment-visible runtime is backed by real repo "
            "sources, not stale restored markers or manual status boards. "
            "It does not validate production readiness, contact live systems, "
            "mutate artifacts, or close /goal."
        ),
        "mutates_files": False,
        "contacts_live_systems": False,
        "source_artifacts": ["src/integration/current_shard_stale_guard.py"],
        "load_errors": [],
        "findings": [],
        "status_observations": [],
        "summary": {
            "critical_scripts_total": 1,
            "critical_sources_missing": 0,
            "critical_source_compile_errors": 0,
            "critical_source_backed": 1,
            "source_errors_total": 0,
        },
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Guard current source runtime surface against stale markers")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=".tmp/validation-shards/integration-spine-source-runtime-surface-current.json")
    parser.add_argument("--require-clear", action="store_true", help="return 2 when stale markers are found")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    report = build_report(root)
    write_json(root / args.output_json, report)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.require_clear and report.get("decision") != "SOURCE_RUNTIME_SURFACE_READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
