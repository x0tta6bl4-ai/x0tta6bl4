#!/usr/bin/env python3
"""Unified recall across integrity and strategy memory layers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INTEGRITY_STATE_PATH = ROOT / ".agent-coord" / "integrity_state.json"
STRATEGY_STATE_PATH = ROOT / ".agent-coord" / "strategy_memory_state.json"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
    "и",
    "в",
    "во",
    "на",
    "не",
    "но",
    "по",
    "с",
    "со",
    "что",
    "это",
    "как",
    "для",
    "из",
    "при",
}


def tokenize(text: str) -> set[str]:
    parts = re.findall(r"[A-Za-z0-9_./:-]+", text.lower())
    return {part for part in parts if part not in STOPWORDS and len(part) > 1}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_integrity_candidates(data: dict[str, Any], agent: str = "", include_all_agents: bool = False) -> list[dict[str, Any]]:
    view = "forensic_view" if include_all_agents else "operator_view"
    summaries = data.get("summaries", {}).get(view, {})
    rows = summaries.get("failure_signatures", [])
    candidates = []
    for row in rows:
        if agent and row.get("agent") != agent:
            continue
        candidates.append(
            {
                "layer": "integrity",
                "kind": "failure_signature",
                "agent": row.get("agent", ""),
                "title": row.get("failure_signature", ""),
                "summary": row.get("description", ""),
                "recommended_pattern": row.get("owner_hint", ""),
                "text": " ".join(
                    [
                        str(row.get("agent", "")),
                        str(row.get("failure_signature", "")),
                        str(row.get("description", "")),
                        str(row.get("category", "")),
                        str(row.get("owner_hint", "")),
                    ]
                ),
            }
        )
    for row in summaries.get("memory_incidents", []):
        if agent and row.get("agent") != agent:
            continue
        candidates.append(
            {
                "layer": "integrity",
                "kind": "memory_incident",
                "agent": row.get("agent", ""),
                "title": row.get("failure_signature", "") or row.get("type", ""),
                "summary": row.get("description", ""),
                "recommended_pattern": "Use memory_recall/strategy_recent and complete memory-aware tool_audit fields before retrying handoff.",
                "text": " ".join(
                    [
                        str(row.get("agent", "")),
                        str(row.get("type", "")),
                        str(row.get("failure_signature", "")),
                        str(row.get("description", "")),
                    ]
                ),
            }
        )
    return candidates


def build_strategy_candidates(data: dict[str, Any], agent: str = "", include_all_agents: bool = False) -> list[dict[str, Any]]:
    view = "forensic_view" if include_all_agents else "operator_view"
    summaries = data.get("summaries", {}).get(view, {})
    candidates = []
    for row in summaries.get("recent_success", []):
        if agent and row.get("agent") != agent:
            continue
        candidates.append(
            {
                "layer": "strategy",
                "kind": "success",
                "agent": row.get("agent", ""),
                "title": row.get("task_shape", ""),
                "summary": row.get("strategy", ""),
                "recommended_pattern": row.get("recommended_pattern", ""),
                "text": " ".join(
                    [
                        str(row.get("agent", "")),
                        str(row.get("task_shape", "")),
                        str(row.get("strategy", "")),
                        str(row.get("recommended_pattern", "")),
                        str(row.get("what_worked", "")),
                    ]
                ),
            }
        )
    for row in summaries.get("recent_failure", []):
        if agent and row.get("agent") != agent:
            continue
        candidates.append(
            {
                "layer": "strategy",
                "kind": "failure",
                "agent": row.get("agent", ""),
                "title": row.get("task_shape", ""),
                "summary": row.get("strategy", ""),
                "recommended_pattern": row.get("recommended_pattern", ""),
                "text": " ".join(
                    [
                        str(row.get("agent", "")),
                        str(row.get("task_shape", "")),
                        str(row.get("strategy", "")),
                        str(row.get("recommended_pattern", "")),
                        str(row.get("what_failed", "")),
                        str(row.get("failure_signature", "")),
                    ]
                ),
            }
        )
    for row in summaries.get("failure_signatures", []):
        if agent and row.get("agent") != agent:
            continue
        candidates.append(
            {
                "layer": "strategy",
                "kind": "failure_signature",
                "agent": row.get("agent", ""),
                "title": row.get("failure_signature", ""),
                "summary": row.get("what_failed", ""),
                "recommended_pattern": row.get("recommended_pattern", ""),
                "text": " ".join(
                    [
                        str(row.get("agent", "")),
                        str(row.get("failure_signature", "")),
                        str(row.get("task_shape", "")),
                        str(row.get("what_failed", "")),
                        str(row.get("recommended_pattern", "")),
                    ]
                ),
            }
        )
    return candidates


def score_candidates(candidates: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in candidates:
        overlap = query_tokens & tokenize(row.get("text", ""))
        score = len(overlap) * 10
        if row.get("layer") == "strategy" and row.get("kind") == "success":
            score += 2
        if row.get("layer") == "strategy" and row.get("kind") == "failure_signature":
            score += 1
        if row.get("layer") == "integrity" and row.get("kind") == "memory_incident":
            score += 3
        if score <= 0:
            continue
        enriched = dict(row)
        enriched["_match_score"] = score
        ranked.append((score, enriched))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in ranked]


def cmd_recall(args: argparse.Namespace) -> int:
    integrity = load_json(INTEGRITY_STATE_PATH)
    strategy = load_json(STRATEGY_STATE_PATH)
    candidates = []
    candidates.extend(build_integrity_candidates(integrity, agent=args.agent, include_all_agents=args.all_agents))
    candidates.extend(build_strategy_candidates(strategy, agent=args.agent, include_all_agents=args.all_agents))
    rows = score_candidates(candidates, args.query)[: args.limit]
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[memory] no relevant recall found")
        return 0
    print("[memory] relevant combined recall:")
    for row in rows:
        print(
            "  - "
            f"layer={row['layer']} kind={row['kind']} agent={row['agent']} score={row['_match_score']} title={row['title']}"
        )
        if row.get("summary"):
            print(f"    summary: {row['summary']}")
        if row.get("recommended_pattern"):
            print(f"    recommended: {row['recommended_pattern']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified memory recall across integrity and strategy")
    sub = parser.add_subparsers(dest="cmd", required=True)

    recall = sub.add_parser("recall", help="Retrieve relevant memory across layers")
    recall.add_argument("--query", required=True)
    recall.add_argument("--agent", default="")
    recall.add_argument("--limit", type=int, default=5)
    recall.add_argument("--all-agents", action="store_true")
    recall.add_argument("--json", action="store_true")
    recall.set_defaults(func=cmd_recall)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
