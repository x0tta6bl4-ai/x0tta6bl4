#!/usr/bin/env python3
"""Compatibility wrapper for the repo-backed closure preflight report.

The source of truth is ``src.integration.production_closeout_review``. This
wrapper keeps the older operator command path alive while preventing a second
closure-review implementation from drifting away from the closeout report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.production_closeout_review import (  # noqa: E402
    DEFAULT_CLOSURE_PREFLIGHT_OUTPUT,
    build_closure_preflight_report,
    build_report as build_closeout_report,
    write_json,
)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "Integration Spine Production Closure Preflight",
        f"decision: {report.get('decision')}",
        f"ready: {report.get('ready')}",
        f"raw_files_installed: {summary.get('raw_files_installed')}",
        f"raw_files_local_observation: {summary.get('raw_files_local_observation')}",
        f"pending_sources: {summary.get('sources_blocking')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run integration-spine production closure preflight")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--output-json", default=DEFAULT_CLOSURE_PREFLIGHT_OUTPUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    closeout_report = build_closeout_report(root)
    report = build_closure_preflight_report(closeout_report)
    write_json(root / args.output_json, report)
    if args.output == "json":
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(_render_text(report))
    if args.require_ready and not report["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
