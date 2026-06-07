#!/usr/bin/env python3
"""Run the paid-task hunter loop: collect, score, and write a short report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.paid_task_collectors import (
    collect_github_algora_bounty_listings,
    collect_github_paid_task_listings,
)
from src.sales.paid_task_selector import score_paid_task_listings


DEFAULT_LISTINGS_JSON = Path(".tmp/paid-task-listings-current.json")
DEFAULT_SELECTION_JSON = Path(".tmp/paid-task-selection.json")
DEFAULT_REPORT_MD = Path(".tmp/paid-task-hunter-report.md")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_fixture(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--fixture-json must contain a JSON object")
    return payload


def _http_json(url: str, *, timeout_seconds: float = 15.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "x0tta6bl4-paid-task-hunter",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _comments_api_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    separator = "&" if urllib.parse.urlparse(raw_url).query else "?"
    return f"{raw_url}{separator}per_page=20"


def _issue_ref_from_url(issue_url: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlparse(issue_url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc != "github.com" or len(parts) < 4 or parts[2] != "issues":
        return None
    return f"{parts[0]}/{parts[1]}", parts[3]


def _fetch_comment_bodies_with_gh(issue_url: str) -> tuple[list[str], str | None]:
    ref = _issue_ref_from_url(issue_url)
    if ref is None:
        return [], "issue_url_unparseable"
    repo, number = ref
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            number,
            "--repo",
            repo,
            "--json",
            "comments",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return [], f"gh_exit_{result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "gh_json_decode_error"
    comments = payload.get("comments", [])
    if not isinstance(comments, list):
        return [], "gh_comments_not_list"
    bodies = [
        str(item.get("body") or "")
        for item in comments
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]
    return bodies, None


def _fetch_comment_bodies(
    comments_url: str,
    *,
    issue_url: str = "",
    expected_comments: int | None = None,
) -> tuple[list[str], str | None]:
    if not comments_url:
        if issue_url:
            return _fetch_comment_bodies_with_gh(issue_url)
        return [], "comments_url_missing"
    try:
        payload = _http_json(_comments_api_url(comments_url))
    except urllib.error.HTTPError as exc:
        if issue_url:
            bodies, gh_error = _fetch_comment_bodies_with_gh(issue_url)
            if bodies:
                return bodies, None
            return [], gh_error or f"http_{exc.code}"
        return [], f"http_{exc.code}"
    except Exception as exc:  # pragma: no cover - defensive network boundary
        if issue_url:
            bodies, gh_error = _fetch_comment_bodies_with_gh(issue_url)
            if bodies:
                return bodies, None
            return [], gh_error or exc.__class__.__name__
        return [], exc.__class__.__name__
    if not isinstance(payload, list):
        return [], "comments_payload_not_list"
    bodies = [
        str(item.get("body") or "")
        for item in payload
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]
    if not bodies and expected_comments and issue_url:
        gh_bodies, gh_error = _fetch_comment_bodies_with_gh(issue_url)
        if gh_bodies:
            return gh_bodies, None
        if gh_error:
            return [], gh_error
    return bodies, None


def _enrich_top_comments(
    collection: dict[str, Any],
    *,
    selection_mode: str,
    top_n: int,
    enrich_limit: int,
) -> dict[str, Any]:
    if enrich_limit <= 0:
        return collection
    preliminary = score_paid_task_listings(collection, top_n=top_n, selection_mode=selection_mode)
    top_url_list = [
        item["url"]
        for item in preliminary["ranked"]
        if item["decision"] != "reject"
    ][:enrich_limit]
    top_urls = set(top_url_list)
    enriched_tasks = []
    enriched_count = 0
    for task in collection.get("tasks", []):
        if not isinstance(task, dict):
            continue
        next_task = dict(task)
        if next_task.get("url") in top_urls:
            bodies, error = _fetch_comment_bodies(
                str(next_task.get("comments_url") or ""),
                issue_url=str(next_task.get("url") or ""),
                expected_comments=int(next_task.get("comments") or 0),
            )
            next_task["comment_bodies"] = bodies
            next_task["comment_fetch_error"] = error
            enriched_count += 1
        enriched_tasks.append(next_task)
    enriched = dict(collection)
    enriched["tasks"] = enriched_tasks
    enriched["comments_enriched_tasks"] = enriched_count
    return enriched


def _risk_count(selection: dict[str, Any], risk: str) -> int:
    return sum(1 for item in selection["ranked"] if risk in item.get("risk_flags", []))


def _render_report(collection: dict[str, Any], selection: dict[str, Any]) -> str:
    selected = selection.get("selected_first_task")
    lines = [
        "# x0tta6bl4 Paid Task Hunter",
        "",
        f"- Status: {selection['status']}",
        f"- Selection mode: {selection['selection_mode']}",
        f"- Public network used: {collection['public_network_used']}",
        f"- GitHub total count: {collection['github_total_count']}",
        f"- Listings checked: {selection['listings_total']}",
        f"- Take first: {selection['take_first_total']}",
        f"- Manual review: {selection['manual_review_total']}",
        f"- Reject: {selection['reject_total']}",
        f"- Prompt/context leak rejects in top list: {_risk_count(selection, 'system prompt')}",
        f"- High effort in top list: {_risk_count(selection, 'high_effort')}",
        f"- Active attempt or claim in top list: {_risk_count(selection, 'active_attempt_or_claim')}",
        f"- Funds received claim allowed: {selection['claim_gate']['funds_received_claim_allowed']}",
        "",
    ]

    if selected:
        lines.extend(
            [
                "## First Target",
                "",
                f"- Title: {selected['title']}",
                f"- URL: {selected['url']}",
                f"- Payout USD estimate: {selected['payout_usd_estimate']}",
                f"- Score: {selected['score']}",
                f"- Token ROI score: {selected['token_roi_score']}",
                f"- Estimated token cost: {selected['estimated_token_cost']}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## First Target",
                "",
                "No safe automatic first target found.",
                "Use manual_review tasks only after reading comments, claims, and platform rules.",
                "",
            ]
        )

    lines.extend(["## Top Tasks", ""])
    for item in selection["ranked"][:20]:
        risks = ", ".join(item["risk_flags"]) if item["risk_flags"] else "none"
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- Decision: {item['decision']}",
                f"- URL: {item['url']}",
                f"- Payout USD estimate: {item['payout_usd_estimate']}",
                f"- Score: {item['score']}",
                f"- Token ROI score: {item['token_roi_score']}",
                f"- Estimated token cost: {item['estimated_token_cost']}",
                f"- Risk flags: {risks}",
                "",
            ]
        )

    lines.extend(["## Claim Gate", "", selection["claim_gate"]["claim_boundary"], ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--per-query", type=int, default=50)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--mode", choices=["conservative", "token_roi"], default="token_roi")
    parser.add_argument("--source-mode", choices=["algora", "broad"], default="broad")
    parser.add_argument("--enrich-comments", type=int, default=60)
    parser.add_argument("--fixture-json", type=Path)
    parser.add_argument("--write-listings-json", type=Path, default=DEFAULT_LISTINGS_JSON)
    parser.add_argument("--write-selection-json", type=Path, default=DEFAULT_SELECTION_JSON)
    parser.add_argument("--write-report-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source_mode == "broad":
        collection = collect_github_paid_task_listings(
            max_results=args.max_results,
            per_query=args.per_query,
            fixture_payload=_load_fixture(args.fixture_json),
        )
    else:
        collection = collect_github_algora_bounty_listings(
            max_results=args.max_results,
            fixture_payload=_load_fixture(args.fixture_json),
        )
    collection = _enrich_top_comments(
        collection,
        selection_mode=args.mode,
        top_n=args.top,
        enrich_limit=args.enrich_comments,
    )
    selection = score_paid_task_listings(collection, top_n=args.top, selection_mode=args.mode)

    _write_json(args.write_listings_json, collection)
    _write_json(args.write_selection_json, selection)
    args.write_report_md.parent.mkdir(parents=True, exist_ok=True)
    args.write_report_md.write_text(_render_report(collection, selection), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": selection["status"],
                "selection_mode": selection["selection_mode"],
                "github_total_count": collection["github_total_count"],
                "tasks_total": collection["tasks_total"],
                "comments_enriched_tasks": collection.get("comments_enriched_tasks", 0),
                "take_first_total": selection["take_first_total"],
                "manual_review_total": selection["manual_review_total"],
                "reject_total": selection["reject_total"],
                "selected_first_task": selection["selected_first_task"],
                "written": {
                    "listings_json": str(args.write_listings_json),
                    "selection_json": str(args.write_selection_json),
                    "report_md": str(args.write_report_md),
                },
                "funds_received_claim_allowed": selection["claim_gate"]["funds_received_claim_allowed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
