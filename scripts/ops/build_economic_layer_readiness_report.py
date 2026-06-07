#!/usr/bin/env python3
"""Build the x0tta6bl4 economic-layer readiness report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sales.economic_layer_readiness import (
    SCHEMA,
    build_economic_layer_readiness,
)


DEFAULT_OUTPUT_MD = "docs/commercial/ECONOMIC_LAYER_READINESS.md"
DEFAULT_OUTPUT_JSON = "docs/commercial/economic_layer_readiness.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_report(root: Path | str = ".", *, generated_at_utc: str | None = None) -> dict[str, Any]:
    report = build_economic_layer_readiness(root)
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "report": report,
    }


def render_markdown(envelope: dict[str, Any]) -> str:
    report = envelope["report"]
    summary = report["summary"]
    lines = [
        "# x0tta6bl4 Economic Layer Readiness",
        "",
        f"Generated: {envelope['generated_at_utc']}",
        "",
        "## Summary",
        "",
        f"- Status: {report['status']}",
        f"- Wallet: {report['wallet']['address']}",
        f"- Paths total: {summary['paths_total']}",
        f"- Local verified paths: {summary['local_verified_total']}",
        f"- Local blocked paths: {summary['local_blocked_total']}",
        f"- X0T chain submission code path present: {summary['x0t_chain_submission_code_path_present']}",
        f"- Live revenue ready: {summary['live_revenue_ready']}",
        f"- Funds received claim allowed: {summary['funds_received_claim_allowed']}",
        "",
        "## Paths",
        "",
    ]
    for path in report["paths"]:
        lines.extend(
            [
                f"### {path['name']}",
                "",
                f"- Path ID: {path['path_id']}",
                f"- Readiness: {path['readiness']}",
                f"- Mode: {path['monetization_mode']}",
                f"- Current state: {path['current_state']}",
                f"- Finding: {path['verified_finding']}",
                f"- Funds received claim allowed: {path['claim_gate']['funds_received_claim_allowed']}",
                "",
                "Next evidence needed:",
                "",
                *[f"- {item}" for item in path["next_evidence_needed"]],
                "",
                "Files:",
                "",
                *[
                    (
                        f"- {file_check['path']}: exists={file_check['exists']}, "
                        f"complete={file_check['complete']}"
                    )
                    for file_check in path["files"]
                ],
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Boundary",
            "",
            report["claim_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    envelope: dict[str, Any],
    *,
    markdown_path: Path | None,
    json_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(envelope), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write-md", type=Path, default=Path(DEFAULT_OUTPUT_MD))
    parser.add_argument("--write-json", type=Path, default=Path(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--no-md", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    envelope = build_report(args.root)
    written = write_report(
        envelope,
        markdown_path=None if args.no_md else args.write_md,
        json_path=None if args.no_json else args.write_json,
    )
    report = envelope["report"]
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "written": written,
                "status": report["status"],
                "paths_total": report["summary"]["paths_total"],
                "local_verified_total": report["summary"]["local_verified_total"],
                "live_revenue_ready": report["summary"]["live_revenue_ready"],
                "funds_received_claim_allowed": report["summary"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
