"""Collectors for public paid-task listings."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


SCHEMA = "x0tta6bl4.paid_task_collection.v1"
GITHUB_ALGORA_BOUNTY_QUERY = 'label:"\U0001f48e Bounty" type:issue state:open'
GITHUB_PAID_ISSUE_QUERIES = (
    ("github_algora_bounty_search", GITHUB_ALGORA_BOUNTY_QUERY),
    ("github_bounty_label_search", "label:bounty type:issue state:open"),
    ("github_bounty_text_search", '"/bounty $" type:issue state:open'),
    ("github_good_first_bounty_text_search", '"bounty $" "good first issue" type:issue state:open'),
)
GITHUB_SEARCH_ISSUES_URL = "https://api.github.com/search/issues"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_json(url: str, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "x0tta6bl4-paid-task-collector",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed: {exc.code} {body[:300]}") from exc


def _github_search_url(*, query: str, per_page: int) -> str:
    return GITHUB_SEARCH_ISSUES_URL + "?" + urllib.parse.urlencode(
        {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": max(1, min(per_page, 100)),
        }
    )


def _label_names(issue: dict[str, Any]) -> list[str]:
    return [
        str(label.get("name", "")).strip()
        for label in issue.get("labels", [])
        if isinstance(label, dict) and str(label.get("name", "")).strip()
    ]


def _repo_from_api_url(repository_url: str) -> str:
    prefix = "https://api.github.com/repos/"
    if repository_url.startswith(prefix):
        return repository_url.removeprefix(prefix)
    return repository_url


def extract_usd_bounty_amount(*, labels: list[str], text: str) -> float | None:
    candidates: list[float] = []
    haystack = " ".join(labels) + "\n" + text
    for match in re.finditer(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)(\s*[kK])?", haystack):
        raw_amount = match.group(1).replace(",", "")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue
        if match.group(2):
            amount *= 1000
        candidates.append(amount)
    return max(candidates) if candidates else None


def github_issue_to_paid_task_listing(
    issue: dict[str, Any],
    *,
    source_id: str = "algora",
    source_kind: str = "github_issue_search",
) -> dict[str, Any]:
    labels = _label_names(issue)
    body = str(issue.get("body") or "")
    payout = extract_usd_bounty_amount(labels=labels, text=body)
    repo = _repo_from_api_url(str(issue.get("repository_url", "")))
    title = str(issue.get("title") or "").strip()
    number = issue.get("number")
    description = body[:4000]
    return {
        "source_id": source_id,
        "source_kind": source_kind,
        "title": title,
        "url": str(issue.get("html_url") or ""),
        "comments_url": str(issue.get("comments_url") or ""),
        "description": description,
        "requirements": description,
        "labels": labels,
        "repository": repo,
        "issue_number": number,
        "state": str(issue.get("state") or ""),
        "comments": issue.get("comments"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "payout_amount": payout,
        "payout_usd": payout,
        "payout_asset": "USD" if payout is not None else "",
        "collection_notes": [
            "Collected from public GitHub issue search.",
            "Payout amount is parsed from labels and issue text; verify platform rules before work.",
        ],
    }


def collect_github_algora_bounty_listings(
    *,
    max_results: int = 25,
    fixture_payload: dict[str, Any] | None = None,
    collected_at_utc: str | None = None,
) -> dict[str, Any]:
    max_results = max(1, min(max_results, 100))
    url = _github_search_url(query=GITHUB_ALGORA_BOUNTY_QUERY, per_page=max_results)
    payload = fixture_payload if fixture_payload is not None else _http_json(url)
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    issues = [item for item in raw_items if isinstance(item, dict)]
    tasks = [github_issue_to_paid_task_listing(issue) for issue in issues]
    return {
        "schema": SCHEMA,
        "status": "collection_ready" if tasks else "collection_empty",
        "collected_at_utc": collected_at_utc or _utc_now(),
        "source_id": "github_algora_bounty_search",
        "source_url": url,
        "query": GITHUB_ALGORA_BOUNTY_QUERY,
        "public_network_used": fixture_payload is None,
        "max_results": max_results,
        "github_total_count": payload.get("total_count") if isinstance(payload, dict) else None,
        "tasks_total": len(tasks),
        "tasks": tasks,
        "claim_gate": {
            "collection_claim_allowed": True,
            "accepted_task_claim_allowed": False,
            "funds_received_claim_allowed": False,
            "claim_boundary": (
                "This collection proves public listing discovery only. It does not prove "
                "that a task is still available, assigned, accepted, submitted, merged, "
                "approved, or paid."
            ),
        },
    }


def collect_github_paid_task_listings(
    *,
    max_results: int = 100,
    per_query: int = 50,
    fixture_payload: dict[str, Any] | None = None,
    collected_at_utc: str | None = None,
) -> dict[str, Any]:
    max_results = max(1, min(max_results, 300))
    per_query = max(1, min(per_query, 100))

    if fixture_payload is not None:
        payloads = [("fixture", "fixture", fixture_payload)]
        public_network_used = False
    else:
        payloads = [
            (query_id, query, _http_json(_github_search_url(query=query, per_page=per_query)))
            for query_id, query in GITHUB_PAID_ISSUE_QUERIES
        ]
        public_network_used = True

    tasks_by_url: dict[str, dict[str, Any]] = {}
    total_count = 0
    query_results: list[dict[str, Any]] = []
    for query_id, query, payload in payloads:
        raw_items = payload.get("items", []) if isinstance(payload, dict) else []
        issues = [item for item in raw_items if isinstance(item, dict)]
        total = payload.get("total_count") if isinstance(payload, dict) else None
        total_count += int(total or 0)
        query_results.append({"query_id": query_id, "query": query, "total_count": total, "items": len(issues)})
        for issue in issues:
            labels = _label_names(issue)
            task_source_id = "algora" if "\U0001f48e Bounty" in labels else "github_paid_issue"
            task = github_issue_to_paid_task_listing(
                issue,
                source_id=task_source_id,
                source_kind=query_id,
            )
            url = task["url"]
            if url and url not in tasks_by_url:
                tasks_by_url[url] = task
            if len(tasks_by_url) >= max_results:
                break
        if len(tasks_by_url) >= max_results:
            break

    tasks = list(tasks_by_url.values())[:max_results]
    return {
        "schema": SCHEMA,
        "status": "collection_ready" if tasks else "collection_empty",
        "collected_at_utc": collected_at_utc or _utc_now(),
        "source_id": "github_paid_issue_search",
        "source_url": GITHUB_SEARCH_ISSUES_URL,
        "query": " | ".join(query for _, query in GITHUB_PAID_ISSUE_QUERIES),
        "query_results": query_results,
        "public_network_used": public_network_used,
        "max_results": max_results,
        "github_total_count": total_count,
        "tasks_total": len(tasks),
        "tasks": tasks,
        "claim_gate": {
            "collection_claim_allowed": True,
            "accepted_task_claim_allowed": False,
            "funds_received_claim_allowed": False,
            "claim_boundary": (
                "This collection proves public listing discovery only. It does not prove "
                "that a task is still available, assigned, accepted, submitted, merged, "
                "approved, or paid."
            ),
        },
    }
