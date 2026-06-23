#!/usr/bin/env python3
"""Collect and rank non-bounty paid agent tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.non_bounty_task_scout import (
    SOURCE_URLS,
    collect_non_bounty_tasks,
    rank_non_bounty_tasks,
)


DEFAULT_COLLECTION_JSON = Path(".tmp/non-bounty/non_bounty_task_collection.json")
DEFAULT_RANKING_JSON = Path(".tmp/non-bounty/non_bounty_task_ranking.json")
DEFAULT_REPORT_MD = Path(".tmp/non-bounty/non_bounty_task_report.md")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_report(collection: dict[str, Any], ranking: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4 Non-Bounty Task Scout",
        "",
        f"- Collected at: {collection['collected_at_utc']}",
        f"- Sources checked: {len(collection['source_statuses'])}",
        f"- Tasks collected: {collection['tasks_total']}",
        f"- Account-gate first: {ranking['account_gate_first_total']}",
        f"- Manual review: {ranking['manual_review_total']}",
        f"- Watch only: {ranking['watch_only_total']}",
        f"- Reject: {ranking['reject_total']}",
        f"- Funds received claim allowed: {ranking['claim_gate']['funds_received_claim_allowed']}",
        "",
        "## Sources",
        "",
    ]
    for status in collection["source_statuses"]:
        lines.append(
            f"- {status['source_id']}: ok={status['ok']}, items={status['items']}, error={status.get('error')}"
        )
    lines.extend(["", "## First Targets", ""])
    if not ranking["selected_first"]:
        lines.extend(["No non-bounty target is safe to act on automatically right now.", ""])
    for item in ranking["selected_first"]:
        risks = ", ".join(item["risk_flags"]) if item["risk_flags"] else "none"
        reasons = ", ".join(item["reasons"]) if item["reasons"] else "none"
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Source: {item['source_id']}",
                f"- URL: {item['url']}",
                f"- Decision: {item['decision']}",
                f"- Payout USD estimate: {item['payout_usd_estimate']}",
                f"- Score: {item['score']}",
                f"- Token ROI score: {item['token_roi_score']}",
                f"- Action gate: {item['action_gate']}",
                f"- Risks: {risks}",
                f"- Reasons: {reasons}",
                f"- Next: {item['next_machine_step']}",
                "",
            ]
        )
    lines.extend(["## Top Ranked", ""])
    for item in ranking["ranked"][:20]:
        risks = ", ".join(item["risk_flags"]) if item["risk_flags"] else "none"
        lines.extend(
            [
                f"- {item['decision']} | {item['source_id']} | {item['payout_usd_estimate']} USD | "
                f"{item['title']} | risks: {risks}",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(SOURCE_URLS),
        default=[
            "workprotocol",
            "opentask",
            "moltjobs",
            "sporeagent",
            "clustly",
            "riner",
            "agiotage",
            "clawdgigs",
            "chesto",
        ],
    )
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--write-collection-json", type=Path, default=DEFAULT_COLLECTION_JSON)
    parser.add_argument("--write-ranking-json", type=Path, default=DEFAULT_RANKING_JSON)
    parser.add_argument("--write-report-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    collection = collect_non_bounty_tasks(source_ids=tuple(args.sources))
    ranking = rank_non_bounty_tasks(collection, top_n=args.top)
    _write_json(args.write_collection_json, collection)
    _write_json(args.write_ranking_json, ranking)
    args.write_report_md.parent.mkdir(parents=True, exist_ok=True)
    args.write_report_md.write_text(_render_report(collection, ranking), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": ranking["status"],
                "tasks_total": ranking["tasks_total"],
                "account_gate_first_total": ranking["account_gate_first_total"],
                "manual_review_total": ranking["manual_review_total"],
                "watch_only_total": ranking["watch_only_total"],
                "reject_total": ranking["reject_total"],
                "selected_first": ranking["selected_first"],
                "written": {
                    "collection_json": str(args.write_collection_json),
                    "ranking_json": str(args.write_ranking_json),
                    "report_md": str(args.write_report_md),
                },
                "funds_received_claim_allowed": ranking["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
