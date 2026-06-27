#!/usr/bin/env python3
"""Scout public paid GitHub tasks without making payout or acceptance claims."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.paid_task_selector import score_paid_task_listings


SCHEMA = "x0tta6bl4.free_liquidity_scout.v1"
DEFAULT_JSON = Path(".tmp/free-liquidity/scavenger.json")
DEFAULT_MD = Path(".tmp/free-liquidity/scavenger.md")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _label_names(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            value = label.get("name")
        else:
            value = label
        text = str(value or "").strip()
        if text:
            names.append(text)
    return names


def _payout_from_labels(labels: list[str]) -> tuple[float | None, str | None]:
    for label in labels:
        match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", label)
        if not match:
            continue
        return float(match.group(1).replace(",", "")), "USD"
    return None, None


def _github_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _normalise_github_search(payload: Any) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for item in _github_items(payload):
        labels = _label_names(item.get("labels"))
        payout_amount, payout_asset = _payout_from_labels(labels)
        url = str(item.get("html_url") or item.get("url") or "").strip()
        tasks.append(
            {
                "source_id": "github_paid_issue",
                "title": str(item.get("title") or "").strip(),
                "description": str(item.get("body") or "").strip(),
                "labels": labels,
                "payout_amount": payout_amount,
                "payout_asset": payout_asset,
                "comments": item.get("comments", 0),
                "state": item.get("state"),
                "url": url,
                "repository_url": item.get("repository_url"),
                "issue_number": item.get("number"),
            }
        )
    return {"tasks": tasks}


def _render_markdown(report: dict[str, Any]) -> str:
    selection = report["selection"]
    lines = [
        "# x0tta6bl4 Free Liquidity Scout",
        "",
        f"- Generated at: {report['generated_at_utc']}",
        f"- Listings total: {selection['listings_total']}",
        f"- Take first: {selection['take_first_total']}",
        f"- Manual review: {selection['manual_review_total']}",
        f"- Reject: {selection['reject_total']}",
        f"- Funds received claim allowed: {selection['claim_gate']['funds_received_claim_allowed']}",
        "",
        "## Ranked",
        "",
    ]
    if not selection["ranked"]:
        lines.append("No candidate listings were available.")
    for item in selection["ranked"]:
        risks = ", ".join(item["risk_flags"]) if item["risk_flags"] else "none"
        lines.extend(
            [
                f"### {item['title'] or '(untitled)'}",
                "",
                f"- Decision: {item['decision']}",
                f"- URL: {item['url']}",
                f"- Payout USD estimate: {item['payout_usd_estimate']}",
                f"- Score: {item['score']}",
                f"- Risks: {risks}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-json", type=Path, required=True)
    parser.add_argument("--write-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--write-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--top", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture = _read_json(args.fixture_json)
    selection = score_paid_task_listings(
        _normalise_github_search(fixture),
        now=datetime.now(timezone.utc),
        top_n=args.top,
        selection_mode="conservative",
    )
    report = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selection": selection,
    }
    _write_json(args.write_json, report)
    args.write_md.parent.mkdir(parents=True, exist_ok=True)
    args.write_md.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": selection["status"],
                "selected_first_task": selection["selected_first_task"],
                "funds_received_claim_allowed": selection["claim_gate"][
                    "funds_received_claim_allowed"
                ],
                "written": {
                    "json": str(args.write_json),
                    "markdown": str(args.write_md),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
