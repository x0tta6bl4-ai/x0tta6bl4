#!/usr/bin/env python3
"""Score paid-task listings and pick the safest first target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.sales.paid_task_selector import SCHEMA, score_paid_task_listings


DEFAULT_OUTPUT_JSON = ".tmp/paid-task-selection.json"
DEFAULT_OUTPUT_MD = ".tmp/paid-task-selection.md"


def load_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def render_markdown(selection: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4 Paid Task Selection",
        "",
        f"- Status: {selection['status']}",
        f"- Selection mode: {selection['selection_mode']}",
        f"- Listings total: {selection['listings_total']}",
        f"- Take first: {selection['take_first_total']}",
        f"- Manual review: {selection['manual_review_total']}",
        f"- Reject: {selection['reject_total']}",
        f"- Funds received claim allowed: {selection['claim_gate']['funds_received_claim_allowed']}",
        "",
    ]
    selected = selection.get("selected_first_task")
    if selected:
        lines.extend(
            [
                "## First Task",
                "",
                f"- Title: {selected['title']}",
                f"- Source: {selected['source_id']}",
                f"- Score: {selected['score']}",
                f"- Token ROI score: {selected['token_roi_score']}",
                f"- Estimated token cost: {selected['estimated_token_cost']}",
                f"- URL: {selected['url']}",
                f"- Decision: {selected['decision']}",
                "",
            ]
        )
    lines.extend(["## Ranked Tasks", ""])
    for item in selection["ranked"]:
        lines.extend(
            [
                f"### {item['title'] or 'Untitled task'}",
                "",
                f"- Source: {item['source_id']}",
                f"- Score: {item['score']}",
                f"- Token ROI score: {item['token_roi_score']}",
                f"- Estimated token cost: {item['estimated_token_cost']}",
                f"- Decision: {item['decision']}",
                f"- URL: {item['url']}",
                f"- Risk flags: {', '.join(item['risk_flags']) if item['risk_flags'] else 'none'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Gate",
            "",
            selection["claim_gate"]["claim_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_selection(
    selection: dict[str, Any],
    *,
    json_path: Path | None,
    markdown_path: Path | None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(selection), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--mode", choices=["conservative", "token_roi"], default="conservative")
    parser.add_argument("--write-json", type=Path, default=Path(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--write-md", type=Path, default=Path(DEFAULT_OUTPUT_MD))
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-md", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selection = score_paid_task_listings(load_payload(args.input), top_n=args.top, selection_mode=args.mode)
    written = write_selection(
        selection,
        json_path=None if args.no_json else args.write_json,
        markdown_path=None if args.no_md else args.write_md,
    )
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": selection["status"],
                "selected_first_task": selection["selected_first_task"],
                "written": written,
                "funds_received_claim_allowed": selection["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
