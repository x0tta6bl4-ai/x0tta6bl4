#!/usr/bin/env python3
"""Watch paid-task listings and alert only when a clean target appears."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.ops.run_paid_task_hunter import _enrich_top_comments, _load_fixture
from src.sales.paid_task_collectors import (
    collect_github_algora_bounty_listings,
    collect_github_paid_task_listings,
)
from src.sales.paid_task_selector import score_paid_task_listings


DEFAULT_CURRENT_JSON = Path(".tmp/paid-task-watch-current.json")
DEFAULT_HISTORY_JSONL = Path(".tmp/paid-task-watch-history.jsonl")
DEFAULT_ALERTS_MD = Path(".tmp/paid-task-watch-alerts.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _render_alerts(snapshot: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4 Paid Task Watch",
        "",
        f"- Checked at UTC: {snapshot['checked_at_utc']}",
        f"- Status: {snapshot['status']}",
        f"- Cycle: {snapshot['cycle']}",
        f"- Source mode: {snapshot['source_mode']}",
        f"- Listings checked: {snapshot['tasks_total']}",
        f"- Take first: {snapshot['take_first_total']}",
        f"- Manual review: {snapshot['manual_review_total']}",
        f"- Reject: {snapshot['reject_total']}",
        f"- Action: {snapshot['action']}",
        f"- Funds received claim allowed: {snapshot['funds_received_claim_allowed']}",
        "",
    ]
    target = snapshot.get("selected_first_task")
    if target:
        lines.extend(
            [
                "## Clean Target",
                "",
                f"- Title: {target['title']}",
                f"- URL: {target['url']}",
                f"- Payout USD estimate: {target['payout_usd_estimate']}",
                f"- Token ROI score: {target['token_roi_score']}",
                f"- Estimated token cost: {target['estimated_token_cost']}",
                "",
            ]
        )
    else:
        lines.extend(["## Clean Target", "", "No clean automatic target found.", ""])

    near = snapshot.get("top_manual_review", [])
    if near:
        lines.extend(["## Manual Review", ""])
        for item in near:
            risks = ", ".join(item["risk_flags"]) if item["risk_flags"] else "none"
            lines.extend(
                [
                    f"### {item['title']}",
                    "",
                    f"- URL: {item['url']}",
                    f"- Payout USD estimate: {item['payout_usd_estimate']}",
                    f"- Token ROI score: {item['token_roi_score']}",
                    f"- Risk flags: {risks}",
                    "",
                ]
            )
    return "\n".join(lines)


def _collect(args: argparse.Namespace) -> dict[str, Any]:
    fixture = _load_fixture(args.fixture_json)
    if args.source_mode == "broad":
        return collect_github_paid_task_listings(
            max_results=args.max_results,
            per_query=args.per_query,
            fixture_payload=fixture,
        )
    return collect_github_algora_bounty_listings(
        max_results=args.max_results,
        fixture_payload=fixture,
    )


def run_watch_cycle(args: argparse.Namespace, *, cycle: int) -> dict[str, Any]:
    collection = _collect(args)
    collection = _enrich_top_comments(
        collection,
        selection_mode=args.mode,
        top_n=args.top,
        enrich_limit=args.enrich_comments,
    )
    selection = score_paid_task_listings(collection, top_n=args.top, selection_mode=args.mode)
    selected = selection.get("selected_first_task")
    manual_review = [
        item for item in selection["ranked"]
        if item["decision"] == "manual_review"
    ][:5]
    snapshot = {
        "checked_at_utc": _utc_now(),
        "cycle": cycle,
        "status": selection["status"],
        "source_mode": args.source_mode,
        "selection_mode": selection["selection_mode"],
        "github_total_count": collection.get("github_total_count"),
        "tasks_total": collection.get("tasks_total"),
        "comments_enriched_tasks": collection.get("comments_enriched_tasks", 0),
        "take_first_total": selection["take_first_total"],
        "manual_review_total": selection["manual_review_total"],
        "reject_total": selection["reject_total"],
        "selected_first_task": selected,
        "top_manual_review": manual_review,
        "action": "start_work" if selected else "wait",
        "funds_received_claim_allowed": selection["claim_gate"]["funds_received_claim_allowed"],
    }
    _write_json(args.write_current_json, snapshot)
    _append_jsonl(args.write_history_jsonl, snapshot)
    args.write_alerts_md.parent.mkdir(parents=True, exist_ok=True)
    args.write_alerts_md.write_text(_render_alerts(snapshot), encoding="utf-8")
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1, help="0 means run forever")
    parser.add_argument("--interval-seconds", type=float, default=600.0)
    parser.add_argument("--source-mode", choices=["algora", "broad"], default="broad")
    parser.add_argument("--max-results", type=int, default=200)
    parser.add_argument("--per-query", type=int, default=80)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--mode", choices=["conservative", "token_roi"], default="token_roi")
    parser.add_argument("--enrich-comments", type=int, default=60)
    parser.add_argument("--fixture-json", type=Path)
    parser.add_argument("--write-current-json", type=Path, default=DEFAULT_CURRENT_JSON)
    parser.add_argument("--write-history-jsonl", type=Path, default=DEFAULT_HISTORY_JSONL)
    parser.add_argument("--write-alerts-md", type=Path, default=DEFAULT_ALERTS_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle = 0
    last_snapshot: dict[str, Any] | None = None
    while args.cycles == 0 or cycle < args.cycles:
        cycle += 1
        last_snapshot = run_watch_cycle(args, cycle=cycle)
        print(json.dumps(last_snapshot, indent=2, sort_keys=True))
        if args.cycles != 0 and cycle >= args.cycles:
            break
        time.sleep(max(0.0, args.interval_seconds))
    return 0 if last_snapshot is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
