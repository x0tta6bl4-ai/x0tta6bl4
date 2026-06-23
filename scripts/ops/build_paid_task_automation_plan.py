#!/usr/bin/env python3
"""Build the paid-task automation plan for x0tta6bl4."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sales.paid_task_pipeline import build_paid_task_pipeline


SCHEMA = "x0tta6bl4.paid_task_automation_plan.v1"
DEFAULT_OUTPUT_MD = "docs/commercial/PAID_TASK_AUTOMATION_PLAN.md"
DEFAULT_OUTPUT_JSON = "docs/commercial/paid_task_automation_plan.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_plan(root: Path | str = ".", *, generated_at_utc: str | None = None) -> dict[str, Any]:
    root_path = Path(root)
    pipeline = build_paid_task_pipeline(root_path)
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "root": str(root_path.resolve()),
        "pipeline": pipeline,
        "next_machine_action": (
            "Import or scrape allowed public bounty listings into a local JSON file, "
            "then score them against the task_types in this plan."
        ),
    }


def render_markdown(plan: dict[str, Any]) -> str:
    pipeline = plan["pipeline"]
    lines = [
        "# x0tta6bl4 Paid Task Automation Plan",
        "",
        f"Generated: {plan['generated_at_utc']}",
        "",
        "## Goal",
        "",
        pipeline["goal"],
        "",
        "## Wallet",
        "",
        f"- Address: {pipeline['wallet']['address']}",
        f"- Routing note: {pipeline['wallet']['routing_note']}",
        "",
        "## Sources",
        "",
    ]
    for source in pipeline["sources"]:
        lines.extend(
            [
                f"### {source['name']}",
                "",
                f"- Source ID: {source['source_id']}",
                f"- URL: {source['url']}",
                f"- Payout style: {source['payout_style']}",
                f"- Automation fit: {source['automation_fit']}",
                f"- Allowed AI role: {source['allowed_ai_role']}",
                f"- Human gate: {source['human_gate']}",
                f"- Search hint: {source['search_hint']}",
                f"- Source basis: {source['source_basis']}",
                "",
            ]
        )
    lines.extend(["## Task Types", ""])
    for task_type in pipeline["task_types"]:
        lines.extend(
            [
                f"### {task_type['task_type']}",
                "",
                f"- Fit: {task_type['why_it_fits']}",
                f"- Human/platform gate: {task_type['human_or_platform_gate']}",
                "",
                "Automation steps:",
                "",
                *[f"- {step}" for step in task_type["automation_steps"]],
                "",
            ]
        )
    lines.extend(
        [
            "## Automation Loop",
            "",
            *[f"- {step}" for step in pipeline["automation_loop"]],
            "",
            "## Machine Commands",
            "",
            *[f"- `{command}`" for command in pipeline["machine_commands"]],
            "",
            "## Hard No",
            "",
            *[f"- {item}" for item in pipeline["hard_no"]],
            "",
            "## Claim Gate",
            "",
            f"- Pipeline claim allowed: {pipeline['claim_gate']['pipeline_claim_allowed']}",
            f"- Accepted task claim allowed: {pipeline['claim_gate']['accepted_task_claim_allowed']}",
            f"- Funds received claim allowed: {pipeline['claim_gate']['funds_received_claim_allowed']}",
            f"- Settlement finality claim allowed: {pipeline['claim_gate']['settlement_finality_claim_allowed']}",
            "",
            pipeline["claim_gate"]["claim_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_plan(
    plan: dict[str, Any],
    *,
    markdown_path: Path | None,
    json_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(plan), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    plan = build_plan(args.root)
    written = write_plan(
        plan,
        markdown_path=None if args.no_md else args.write_md,
        json_path=None if args.no_json else args.write_json,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "written": written,
                "status": plan["pipeline"]["status"],
                "sources_total": len(plan["pipeline"]["sources"]),
                "funds_received_claim_allowed": plan["pipeline"]["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
