#!/usr/bin/env python3
"""Periodic micro-niche scouting for x0tta6bl4 using public web search pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / ".tmp" / "micro_niche_scout"

DEFAULT_INTERVAL_SEC = 1800
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SEC = 20
USER_AGENT = "x0tta6bl4-micro-niche-scout/1.0 (+https://github.com/x0tta6bl4-ai/x0tta6bl4)"

DOMAIN_QUERIES = {
    "telegram_ops": [
        "telegram bot payments problem operators",
        "telegram mini app subscriptions monetization",
        "telegram stars referral affiliate tool",
        "telegram business account automation small business",
    ],
    "vpn_runtime": [
        "xray x-ui subscription management issue",
        "vpn reseller telegram bot payment issue",
        "vless subscription import problem iphone android",
        "xray runtime user sync device tracking",
    ],
    "release_hardening": [
        "sbom cosign small startup release checklist",
        "evidence based release verification devops",
        "lightweight compliance release gate startup",
        "operator validation checklist kubernetes small team",
    ],
    "fiveg_edge": [
        "open5gs integration consulting signaling",
        "open5gs qos monitoring ebpf",
        "ueransim open5gs test harness",
        "private 5g lab integration pain point",
    ],
    "agent_coordination": [
        "multi agent orchestration audit trail",
        "ai agent handoff ownership workflow",
        "developer agent coordination open source",
        "agent session log evidence automation",
    ],
}

STOPWORDS = {
    "login",
    "sign in",
    "github",
    "reddit",
    "youtube",
    "job",
    "jobs",
    "career",
    "careers",
    "pdf",
    "documentation",
}


@dataclass(frozen=True)
class SearchResult:
    query: str
    title: str
    url: str
    snippet: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodic web scout for x0tta6bl4-aligned micro-niches.")
    parser.add_argument("--once", action="store_true", help="Run a single scouting cycle and exit.")
    parser.add_argument("--daemon", action="store_true", help="Run in a repeating loop until terminated.")
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=DEFAULT_INTERVAL_SEC,
        help=f"Delay between cycles in daemon mode (default: {DEFAULT_INTERVAL_SEC}).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help=f"Maximum parsed search results per query (default: {DEFAULT_MAX_RESULTS}).",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SEC}).",
    )
    parser.add_argument(
        "--bucket",
        action="append",
        choices=sorted(DOMAIN_QUERIES),
        help="Limit scouting to one or more named buckets. Can be passed multiple times.",
    )
    parser.add_argument(
        "--queries-per-bucket",
        type=int,
        default=0,
        help="Limit the number of seed queries used from each bucket (default: 0 = all).",
    )
    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_ROOT),
        help=f"Directory for scout artifacts (default: {OUTPUT_ROOT}).",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_url(url: str, timeout_sec: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return response.read().decode("utf-8", errors="ignore")


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def fetch_duckduckgo_results(query: str, timeout_sec: int, max_results: int) -> list[SearchResult]:
    encoded = urllib.parse.quote_plus(query)
    html = fetch_url(f"https://html.duckduckgo.com/html/?q={encoded}", timeout_sec)
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.DOTALL,
    )
    results: list[SearchResult] = []
    for match in pattern.finditer(html):
        title = clean_html(match.group("title"))
        snippet = clean_html(match.group("snippet"))
        url = unescape(match.group("url"))
        if not title or not url:
            continue
        results.append(SearchResult(query=query, title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break
    return results


def score_result(result: SearchResult) -> int:
    haystack = f"{result.title} {result.snippet}".lower()
    score = 0
    positive_markers = [
        "manual",
        "spreadsheet",
        "automation",
        "problem",
        "issue",
        "pain",
        "struggle",
        "small business",
        "operator",
        "reseller",
        "tool",
        "workflow",
        "monitoring",
        "billing",
        "payment",
        "subscription",
        "runtime",
        "mini app",
        "bot",
        "open5gs",
        "xray",
        "devops",
        "compliance",
        "agent",
    ]
    for marker in positive_markers:
        if marker in haystack:
            score += 2
    for marker in STOPWORDS:
        if marker in haystack:
            score -= 2
    if len(result.snippet) > 120:
        score += 1
    return score


def infer_candidate_name(bucket: str, result: SearchResult) -> str:
    bucket_names = {
        "telegram_ops": "Telegram Ops Tooling",
        "vpn_runtime": "VPN Runtime Automation",
        "release_hardening": "Release Hardening Toolkit",
        "fiveg_edge": "Open5GS Edge Validation",
        "agent_coordination": "Agent Coordination Layer",
    }
    base = bucket_names.get(bucket, bucket.replace("_", " ").title())
    snippet = f"{result.title} {result.snippet}".lower()
    if "payment" in snippet or "billing" in snippet:
        return f"{base}: Payment Reliability"
    if "subscription" in snippet:
        return f"{base}: Subscription Flow"
    if "small business" in snippet or "business" in snippet:
        return f"{base}: Small-Business Ops"
    if "monitoring" in snippet or "observability" in snippet:
        return f"{base}: Monitoring"
    if "agent" in snippet or "workflow" in snippet:
        return f"{base}: Workflow Control"
    return base


def summarize_candidate(bucket: str, results: Iterable[SearchResult]) -> dict[str, object] | None:
    scored = sorted(
        (
            {
                "score": score_result(result),
                "result": result,
            }
            for result in results
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    if not scored:
        return None
    top = scored[0]
    if top["score"] < 2:
        return None
    top_result: SearchResult = top["result"]
    return {
        "bucket": bucket,
        "candidate_name": infer_candidate_name(bucket, top_result),
        "score": top["score"],
        "query": top_result.query,
        "evidence": [
            {
                "title": item["result"].title,
                "url": item["result"].url,
                "snippet": item["result"].snippet,
                "score": item["score"],
            }
            for item in scored[:3]
        ],
        "x0tta6bl4_fit": fit_to_repo(bucket),
    }


def fit_to_repo(bucket: str) -> str:
    mapping = {
        "telegram_ops": "Maps to Ghost Access bot UX, payments, and Telegram automation layers.",
        "vpn_runtime": "Maps to Ghost Access runtime/device consistency and x-ui/xray lifecycle.",
        "release_hardening": "Maps to verify-v1.1, SBOM, cosign rehearsal, and operator checklists.",
        "fiveg_edge": "Maps to edge/5g, integration, and Open5GS signaling/QoS verification.",
        "agent_coordination": "Maps to scripts/agent-coord.sh, inbox/state front door, and swarm tooling.",
    }
    return mapping[bucket]


def selected_queries(args: argparse.Namespace) -> dict[str, list[str]]:
    buckets = args.bucket or list(DOMAIN_QUERIES)
    query_map: dict[str, list[str]] = {}
    for bucket in buckets:
        queries = DOMAIN_QUERIES[bucket]
        if args.queries_per_bucket > 0:
            queries = queries[: args.queries_per_bucket]
        query_map[bucket] = queries
    return query_map


def run_cycle(output_root: Path, timeout_sec: int, max_results: int, query_map: dict[str, list[str]]) -> dict[str, object]:
    jsonl_path = output_root / "findings.jsonl"
    latest_md_path = output_root / "latest_report.md"
    cycle_results: dict[str, list[SearchResult]] = {}
    for bucket, queries in query_map.items():
        bucket_results: list[SearchResult] = []
        for query in queries:
            try:
                bucket_results.extend(fetch_duckduckgo_results(query, timeout_sec, max_results))
            except Exception as exc:  # pragma: no cover - network variance
                bucket_results.append(
                    SearchResult(
                        query=query,
                        title=f"[fetch-error] {type(exc).__name__}",
                        url="",
                        snippet=str(exc),
                    )
                )
        cycle_results[bucket] = bucket_results

    candidates = []
    for bucket, results in cycle_results.items():
        candidate = summarize_candidate(bucket, [item for item in results if item.url])
        if candidate:
            candidates.append(candidate)

    cycle = {
        "generated_at": utc_now(),
        "candidate_count": len(candidates),
        "candidates": sorted(candidates, key=lambda item: item["score"], reverse=True),
    }

    output_root.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(cycle, ensure_ascii=False) + "\n")
    latest_md_path.write_text(render_markdown(cycle), encoding="utf-8")
    return cycle


def render_markdown(cycle: dict[str, object]) -> str:
    lines = ["# Micro-Niche Scout Report", ""]
    lines.append(f"- Generated at: `{cycle['generated_at']}`")
    lines.append(f"- Candidates: `{cycle['candidate_count']}`")
    lines.append("")
    for candidate in cycle["candidates"]:
        lines.append(f"## {candidate['candidate_name']}")
        lines.append("")
        lines.append(f"- Bucket: `{candidate['bucket']}`")
        lines.append(f"- Score: `{candidate['score']}`")
        lines.append(f"- Seed query: `{candidate['query']}`")
        lines.append(f"- x0tta6bl4 fit: {candidate['x0tta6bl4_fit']}")
        lines.append("- Evidence:")
        for item in candidate["evidence"]:
            title = item["title"]
            url = item["url"] or "n/a"
            snippet = item["snippet"]
            lines.append(f"  - `{item['score']}` [{title}]({url}) — {snippet}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_pid(pid_path: Path) -> None:
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def daemon_loop(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    latest_md_path = output_root / "latest_report.md"
    query_map = selected_queries(args)
    write_pid(output_root / "micro_niche_scout.pid")
    with (output_root / "micro_niche_scout.log").open("a", encoding="utf-8") as log_handle:
        while True:
            cycle = run_cycle(output_root, args.timeout_sec, args.max_results, query_map)
            log_handle.write(
                f"{cycle['generated_at']} candidate_count={cycle['candidate_count']} report={latest_md_path}\n"
            )
            log_handle.flush()
            time.sleep(args.interval_sec)


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root)
    query_map = selected_queries(args)

    if args.daemon:
        return daemon_loop(args)

    cycle = run_cycle(output_root, args.timeout_sec, args.max_results, query_map)
    print(json.dumps(cycle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
