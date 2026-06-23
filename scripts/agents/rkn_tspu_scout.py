#!/usr/bin/env python3
"""Periodic scouting for Roskomnadzor/TSPU signals relevant to x0tta6bl4."""

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
OUTPUT_ROOT = ROOT / ".tmp" / "rkn_tspu_scout"

DEFAULT_INTERVAL_SEC = 2700
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SEC = 15
USER_AGENT = "x0tta6bl4-rkn-tspu-scout/1.0 (+https://github.com/x0tta6bl4-ai/x0tta6bl4)"

DOMAIN_QUERIES = {
    "rkn_actions": [
        "РКН ТСПУ 2026 блокировки DPI",
        "Роскомнадзор ТСПУ Telegram замедление 2026",
        "РКН ТСПУ провайдеры штрафы обход 2026",
        "Роскомнадзор DNS DPI Telegram YouTube 2026",
    ],
    "tspu_operators": [
        "ТСПУ операторы связи bypass перегрузка 2026",
        "ТСПУ сбой провайдеры обход блокировок 2026",
        "РКН операторы пускали трафик в обход ТСПУ",
        "ТСПУ перегрузка bypass март 2026",
    ],
    "anti_censorship": [
        "обход ТСПУ DPI VPN 2026",
        "блокировка VPN ТСПУ 2026 протоколы",
        "Telegram блокировка 2026 обход DPI",
        "vless reality xray DPI detection Russia 2026",
    ],
    "regulation": [
        "Роскомнадзор закон ТСПУ 2026",
        "суверенный интернет ТСПУ 2026 изменения",
        "РКН искусственный интеллект блокировка трафика 2026",
        "Роскомнадзор бюджет ТСПУ 2026",
    ],
    "field_reports": [
        "РКН ТСПУ field report 2026 Telegram",
        "ТСПУ YouTube Telegram жалобы 2026",
        "РКН замедление Telegram сценарий YouTube 2026",
        "Роскомсвобода ТСПУ DPI 2026",
    ],
}

STOPWORDS = {
    "job",
    "jobs",
    "career",
    "careers",
    "course",
    "вакан",
    "wiki",
    "wikipedia",
}


@dataclass(frozen=True)
class SearchResult:
    query: str
    title: str
    url: str
    snippet: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Periodic scout for RKN/TSPU signals relevant to x0tta6bl4.")
    parser.add_argument("--once", action="store_true", help="Run a single scouting cycle and exit.")
    parser.add_argument("--daemon", action="store_true", help="Run in a repeating loop until terminated.")
    parser.add_argument("--interval-sec", type=int, default=DEFAULT_INTERVAL_SEC)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
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
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
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
    markers = [
        "ркн",
        "роскомнадзор",
        "тспу",
        "dpi",
        "dns",
        "telegram",
        "youtube",
        "vpn",
        "обход",
        "блокиров",
        "замедлен",
        "штраф",
        "провайдер",
        "оператор",
        "bypass",
        "xray",
        "vless",
        "reality",
        "field",
        "жалоб",
        "ai",
        "ии",
    ]
    for marker in markers:
        if marker in haystack:
            score += 2
    if "2026" in haystack:
        score += 1
    if len(result.snippet) > 120:
        score += 1
    for marker in STOPWORDS:
        if marker in haystack:
            score -= 2
    return score


def infer_candidate_name(bucket: str, result: SearchResult) -> str:
    base_names = {
        "rkn_actions": "RKN Restriction Pattern",
        "tspu_operators": "TSPU Operator Stress Signal",
        "anti_censorship": "Anti-Censorship Opportunity",
        "regulation": "RKN/TSPU Regulatory Shift",
        "field_reports": "Field Blocking Report",
    }
    base = base_names.get(bucket, bucket.replace("_", " ").title())
    text = f"{result.title} {result.snippet}".lower()
    if "telegram" in text:
        return f"{base}: Telegram Pressure"
    if "vpn" in text or "xray" in text or "vless" in text:
        return f"{base}: VPN/DPI Pressure"
    if "оператор" in text or "provider" in text or "провайдер" in text:
        return f"{base}: Operator Constraint"
    return base


def x0tta6bl4_implication(bucket: str) -> str:
    mapping = {
        "rkn_actions": "Directly affects Ghost Access delivery reliability, Telegram channel availability, and routing fallback strategy.",
        "tspu_operators": "Signals whether provider-side quality issues can create openings for resilient routing or emergency failover products.",
        "anti_censorship": "Directly maps to VPN runtime, xray transport selection, anti-block positioning, and client import guidance.",
        "regulation": "Useful for roadmap, threat modeling, and deciding what should be productized versus kept experimental.",
        "field_reports": "Useful for operational observability and for matching real-user symptoms against product mitigations.",
    }
    return mapping[bucket]


def summarize_candidate(bucket: str, results: Iterable[SearchResult]) -> dict[str, object] | None:
    scored = sorted(
        ({"score": score_result(item), "result": item} for item in results),
        key=lambda item: item["score"],
        reverse=True,
    )
    if not scored:
        return None
    top = scored[0]
    if top["score"] < 4:
        return None
    top_result: SearchResult = top["result"]
    return {
        "bucket": bucket,
        "candidate_name": infer_candidate_name(bucket, top_result),
        "score": top["score"],
        "query": top_result.query,
        "implication": x0tta6bl4_implication(bucket),
        "evidence": [
            {
                "title": item["result"].title,
                "url": item["result"].url,
                "snippet": item["result"].snippet,
                "score": item["score"],
            }
            for item in scored[:4]
        ],
    }


def selected_queries(args: argparse.Namespace) -> dict[str, list[str]]:
    buckets = args.bucket or list(DOMAIN_QUERIES)
    selected: dict[str, list[str]] = {}
    for bucket in buckets:
        queries = DOMAIN_QUERIES[bucket]
        if args.queries_per_bucket > 0:
            queries = queries[: args.queries_per_bucket]
        selected[bucket] = queries
    return selected


def render_markdown(cycle: dict[str, object]) -> str:
    lines = ["# RKN / TSPU Scout Report", ""]
    lines.append(f"- Generated at: `{cycle['generated_at']}`")
    lines.append(f"- Candidates: `{cycle['candidate_count']}`")
    lines.append("")
    for candidate in cycle["candidates"]:
        lines.append(f"## {candidate['candidate_name']}")
        lines.append("")
        lines.append(f"- Bucket: `{candidate['bucket']}`")
        lines.append(f"- Score: `{candidate['score']}`")
        lines.append(f"- Seed query: `{candidate['query']}`")
        lines.append(f"- x0tta6bl4 implication: {candidate['implication']}")
        lines.append("- Evidence:")
        for item in candidate["evidence"]:
            lines.append(f"  - `{item['score']}` [{item['title']}]({item['url']}) — {item['snippet']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def run_cycle(output_root: Path, timeout_sec: int, max_results: int, query_map: dict[str, list[str]]) -> dict[str, object]:
    jsonl_path = output_root / "findings.jsonl"
    latest_md_path = output_root / "latest_report.md"
    bucket_results: dict[str, list[SearchResult]] = {}
    for bucket, queries in query_map.items():
        current: list[SearchResult] = []
        for query in queries:
            try:
                current.extend(fetch_duckduckgo_results(query, timeout_sec, max_results))
            except Exception as exc:  # pragma: no cover
                current.append(SearchResult(query=query, title=f"[fetch-error] {type(exc).__name__}", url="", snippet=str(exc)))
        bucket_results[bucket] = current

    candidates = []
    for bucket, results in bucket_results.items():
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


def write_pid(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def daemon_loop(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root)
    query_map = selected_queries(args)
    pid_path = output_root / "rkn_tspu_scout.pid"
    log_path = output_root / "rkn_tspu_scout.log"
    latest_md_path = output_root / "latest_report.md"
    write_pid(pid_path)
    with log_path.open("a", encoding="utf-8") as handle:
        while True:
            cycle = run_cycle(output_root, args.timeout_sec, args.max_results, query_map)
            handle.write(f"{cycle['generated_at']} candidate_count={cycle['candidate_count']} report={latest_md_path}\n")
            handle.flush()
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
