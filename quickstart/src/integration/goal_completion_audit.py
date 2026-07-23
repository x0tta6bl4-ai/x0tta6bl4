"""Compatibility generator for the integration-spine goal completion audit.

The legacy ``integration-spine-goal-completion-audit-current.json`` shard is now
an alias of the repo-generated objective coverage audit. This keeps old
handoffs from reading a stale manually retained JSON shape while preserving the
same fail-closed completion boundary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.integration.objective_coverage_audit import build_report as build_coverage_report


DEFAULT_OUTPUT = ".tmp/validation-shards/integration-spine-goal-completion-audit-current.json"
SCHEMA_VERSION = "x0tta6bl4-integration-spine-goal-completion-audit-v2-repo-generated"


def build_report(root: Path) -> Dict[str, Any]:
    report = dict(build_coverage_report(root))
    report["source_schema_version"] = report.get("schema_version")
    report["schema_version"] = SCHEMA_VERSION
    report["compatibility_alias_for"] = "integration-spine-objective-coverage-audit-current"
    report["claim_boundary"] = (
        "Compatibility shard generated from src.integration.objective_coverage_audit. "
        "It is read-only and keeps the same fail-closed goal-completion boundary; "
        "it does not collect evidence, contact live systems, mutate runtime, submit transactions, or close /goal."
    )
    return report


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build integration-spine goal completion audit compatibility shard")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    output = Path(args.output_json)
    report = build_report(root)
    write_json(output if output.is_absolute() else root / output, report)
    print(
        json.dumps(
            {
                "completion_decision": report.get("completion_decision"),
                "goal_can_be_marked_complete": report.get("goal_can_be_marked_complete"),
                "summary": report.get("summary", {}),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    if args.require_complete and report.get("completion_decision") != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
