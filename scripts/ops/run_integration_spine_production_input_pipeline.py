#!/usr/bin/env python3
"""Compatibility wrapper for the repo-backed production input pipeline report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.production_input_pipeline import (  # noqa: E402
    DEFAULT_INPUT_MANIFEST,
    DEFAULT_OUTPUT,
    DEFAULT_RETURN_ACCEPTANCE,
    build_report,
    write_json,
)


def _render_text(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "Integration Spine Production Input Pipeline",
        f"pipeline_decision: {report.get('pipeline_decision')}",
        f"ready: {report.get('ready')}",
        f"raw_files_installed: {summary.get('raw_files_installed')}",
        f"raw_files_install_claim_source: {summary.get('raw_files_install_claim_source')}",
        f"raw_files_local_observation: {summary.get('raw_files_local_observation')}",
        f"blocking_inputs_total: {summary.get('blocking_inputs_total')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run integration-spine production input pipeline report")
    parser.add_argument("--root", default=".")
    parser.add_argument("--return-acceptance", default=DEFAULT_RETURN_ACCEPTANCE)
    parser.add_argument("--input-manifest", default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--stage-ready", action="store_true", help="compatibility no-op; this wrapper is read-only")
    parser.add_argument("--install-raw", action="store_true", help="compatibility no-op; this wrapper is read-only")
    parser.add_argument("--overwrite", action="store_true", help="compatibility no-op; this wrapper is read-only")
    parser.add_argument("--run-collectors", action="store_true", help="compatibility no-op; this wrapper is read-only")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    return_input = Path(args.return_acceptance)
    manifest_input = Path(args.input_manifest)
    report = build_report(
        root,
        return_input if return_input.is_absolute() else root / return_input,
        manifest_input if manifest_input.is_absolute() else root / manifest_input,
    )
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
