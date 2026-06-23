#!/usr/bin/env python3
"""Export the x0tta6bl4 product idea portfolio as sales-ready artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sales.pilot_package import build_pilot_package
from src.sales.product_ideas import build_product_idea_portfolio


SCHEMA = "x0tta6bl4.product_ideas.export.v1"
DEFAULT_OUTPUT_MD = "docs/commercial/PRODUCT_IDEA_PORTFOLIO.md"
DEFAULT_OUTPUT_JSON = "docs/commercial/product_idea_portfolio.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_export(root: Path | str = ".", *, generated_at_utc: str | None = None) -> dict[str, Any]:
    root_path = Path(root)
    portfolio = build_product_idea_portfolio(root_path)
    pilot_package = build_pilot_package(root_path)
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or _utc_now(),
        "root": str(root_path.resolve()),
        "portfolio": portfolio,
        "pilot_package": pilot_package,
        "commercial_decision": (
            "Sell one narrow self-hosted secure mesh MVP first; keep the other "
            "ideas as proof-bounded upsells."
        ),
        "claim_boundary": portfolio["claim_boundary"],
    }


def _status(value: bool) -> str:
    return "ready" if value else "missing"


def render_markdown(export: dict[str, Any]) -> str:
    portfolio = export["portfolio"]
    pilot_package = export["pilot_package"]
    pilot_claim_gate = pilot_package["claim_gate"]
    lines = [
        "# x0tta6bl4 Product Idea Portfolio",
        "",
        f"Generated: {export['generated_at_utc']}",
        "",
        "## Summary",
        "",
        f"- Status: {portfolio['status']}",
        f"- First paid offer: {portfolio['first_offer']}",
        f"- Monetization rule: {portfolio['monetization_rule']}",
        f"- Ideas total: {portfolio['ideas_total']}",
        f"- Repo scaffold ready: {portfolio['repo_scaffold_ready']}",
        f"- Repo scaffold blocked: {portfolio['repo_scaffold_blocked']}",
        "",
        "## Claim Boundary",
        "",
        portfolio["claim_boundary"],
        "",
        "## First Paid Pilot",
        "",
        f"- Offer: {pilot_package['offer_name']}",
        f"- Status: {pilot_package['status']}",
        f"- Target idea: {pilot_package['target_idea_id']}",
        f"- Buyer: {pilot_package['buyer']}",
        f"- Plain offer: {pilot_package['plain_offer']}",
        f"- Production readiness claim allowed: {pilot_claim_gate['production_readiness_claim_allowed']}",
        f"- Customer traffic claim allowed: {pilot_claim_gate['customer_traffic_claim_allowed']}",
        "",
        "Paid scope:",
        "",
        *[f"- {item}" for item in pilot_package["paid_scope"]],
        "",
        "Demo steps:",
        "",
        *[
            (
                f"- {step['step_id']}: {step['operator_action']} "
                f"Proof: {step['proof']} Action: {step['desktop_action_id']}"
            )
            for step in pilot_package["demo_steps"]
        ],
        "",
        "## Ideas",
        "",
    ]

    for index, idea in enumerate(portfolio["ideas"], start=1):
        claim_gate = idea["claim_gate"]
        assets = idea["existing_repo_assets"]
        demo_scenario = idea["demo_scenario"]
        lines.extend(
            [
                f"### {index}. {idea['title']}",
                "",
                f"- Idea ID: {idea['idea_id']}",
                f"- Plain pitch: {idea['simple_pitch']}",
                f"- Buyer: {idea['buyer']}",
                f"- Paid offer: {idea['paid_offer']}",
                f"- First MVP: {idea['first_mvp']}",
                f"- Implementation status: {idea['implementation_status']}",
                f"- Production readiness claim allowed: {claim_gate['production_readiness_claim_allowed']}",
                f"- Customer traffic claim allowed: {claim_gate['customer_traffic_claim_allowed']}",
                f"- Settlement finality claim allowed: {claim_gate['settlement_finality_claim_allowed']}",
                f"- Desktop actions: {', '.join(idea['desktop_action_ids']) or 'none'}",
                f"- Proof focus: {', '.join(idea['proof_focus'])}",
                f"- Demo scenario: {demo_scenario['scenario_id']}",
                "",
                "Repo assets:",
            ]
        )
        for asset in assets:
            lines.append(f"- {_status(asset['exists'])}: {asset['path']}")
        lines.extend(
            [
                "",
                "Demo steps:",
            ]
        )
        for step in demo_scenario["steps"]:
            lines.append(
                f"- {step['step_id']}: {step['operator_action']} "
                f"Proof: {step['proof']} Action: {step['desktop_action_id']}"
            )
        lines.extend(
            [
                "",
                f"Blocked claims: {', '.join(claim_gate['blocked_claim_ids'])}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def write_export(
    export: dict[str, Any],
    *,
    markdown_path: Path | None,
    json_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(export), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    export = build_export(args.root)
    written = write_export(
        export,
        markdown_path=None if args.no_md else args.write_md,
        json_path=None if args.no_json else args.write_json,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "written": written,
                "ideas_total": export["portfolio"]["ideas_total"],
                "status": export["portfolio"]["status"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
