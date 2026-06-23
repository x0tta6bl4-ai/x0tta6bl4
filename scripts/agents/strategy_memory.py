#!/usr/bin/env python3
"""Append-only strategy memory for successful and failed working patterns."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MEMORY_PATH = ROOT / ".agent-coord" / "strategy_memory.jsonl"
STATE_PATH = ROOT / ".agent-coord" / "strategy_memory_state.json"
ROADMAP_QUEUE_PATH = ROOT / "plans" / "ROADMAP_AGENT_QUEUE.json"

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

KIND_ALIASES = {
    "success": "success",
    "success_pattern": "success",
    "successful_pattern": "success",
    "failure": "failure",
    "failure_pattern": "failure",
    "pattern": "pattern",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_kind(kind: str) -> str:
    return KIND_ALIASES.get(str(kind or "").strip().lower(), "pattern")


def ensure_parent() -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_entries() -> list[dict[str, Any]]:
    if not MEMORY_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with MEMORY_PATH.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_operator_agents() -> set[str]:
    if ROADMAP_QUEUE_PATH.exists():
        try:
            data = json.loads(ROADMAP_QUEUE_PATH.read_text(encoding="utf-8"))
            agents = {str(row.get("agent") or "").strip() for row in data.get("tasks", []) if str(row.get("agent") or "").strip()}
            if agents:
                return agents
        except Exception:
            pass
    return {str(entry.get("agent") or "").strip() for entry in load_entries() if str(entry.get("agent") or "").strip()}


def tokenize(text: str) -> set[str]:
    parts = re.findall(r"[A-Za-z0-9_./:-]+", text.lower())
    return {part for part in parts if part not in STOPWORDS and len(part) > 1}


def compute_match_score(entry: dict[str, Any], query_tokens: set[str]) -> int:
    haystack = " ".join(
        str(entry.get(field, ""))
        for field in (
            "task_shape",
            "context",
            "strategy",
            "what_worked",
            "what_failed",
            "recommended_pattern",
            "files_touched",
            "tooling_path",
            "failure_signature",
        )
    )
    entry_tokens = tokenize(haystack)
    overlap = query_tokens & entry_tokens
    base = len(overlap)
    kind_bonus = 2 if str(entry.get("kind", "")) == "success" else 1
    return base * 10 + kind_bonus


def retrieve(entries: list[dict[str, Any]], query: str, limit: int, agent: str = "") -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        if agent and str(entry.get("agent") or "") != agent:
            continue
        score = compute_match_score(entry, query_tokens)
        if score <= 0:
            continue
        ranked.append((score, entry))
    ranked.sort(key=lambda item: (item[0], item[1].get("ts", "")), reverse=True)
    rows: list[dict[str, Any]] = []
    for score, entry in ranked[:limit]:
        enriched = dict(entry)
        enriched["_match_score"] = score
        rows.append(enriched)
    return rows


def select_entries(entries: list[dict[str, Any]], include_all_agents: bool) -> list[dict[str, Any]]:
    if include_all_agents:
        return entries
    allowed = load_operator_agents()
    return [entry for entry in entries if str(entry.get("agent") or "").strip() in allowed]


def summarize_agents(entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False) -> list[dict[str, Any]]:
    selected = select_entries(entries, include_all_agents)
    counts: Counter[str] = Counter()
    kind_counts: dict[str, Counter[str]] = {}
    for entry in selected:
        agent = str(entry.get("agent") or "").strip()
        kind = normalize_kind(str(entry.get("kind") or "pattern"))
        if not agent:
            continue
        counts[agent] += 1
        kind_counts.setdefault(agent, Counter())[kind] += 1
    rows = []
    for agent, total in counts.most_common(limit):
        rows.append(
            {
                "agent": agent,
                "count": total,
                "kinds": dict(kind_counts.get(agent, Counter())),
            }
        )
    return rows


def summarize_task_shapes(entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False) -> list[dict[str, Any]]:
    selected = select_entries(entries, include_all_agents)
    counts: Counter[str] = Counter()
    latest_ts: dict[str, str] = {}
    for entry in selected:
        task_shape = str(entry.get("task_shape") or "").strip()
        if not task_shape:
            continue
        counts[task_shape] += 1
        latest_ts[task_shape] = max(latest_ts.get(task_shape, ""), str(entry.get("ts") or ""))
    rows = []
    for task_shape, total in counts.most_common(limit):
        rows.append(
            {
                "task_shape": task_shape,
                "count": total,
                "latest_ts": latest_ts.get(task_shape, ""),
            }
        )
    return rows


def summarize_failure_signatures(
    entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    selected = select_entries(entries, include_all_agents)
    counts: Counter[tuple[str, str]] = Counter()
    details: dict[tuple[str, str], dict[str, str]] = {}
    for entry in selected:
        kind = normalize_kind(str(entry.get("kind") or "pattern"))
        if kind != "failure":
            continue
        agent = str(entry.get("agent") or "").strip()
        signature = str(entry.get("failure_signature") or "").strip()
        if not agent or not signature:
            continue
        key = (agent, signature)
        counts[key] += 1
        details[key] = {
            "task_shape": str(entry.get("task_shape") or "").strip(),
            "what_failed": str(entry.get("what_failed") or "").strip(),
            "recommended_pattern": str(entry.get("recommended_pattern") or entry.get("strategy") or "").strip(),
        }
    rows = []
    for (agent, signature), total in counts.most_common(limit):
        detail = details.get((agent, signature), {})
        rows.append(
            {
                "agent": agent,
                "failure_signature": signature,
                "count": total,
                "task_shape": detail.get("task_shape", ""),
                "what_failed": detail.get("what_failed", ""),
                "recommended_pattern": detail.get("recommended_pattern", ""),
            }
        )
    return rows


def summarize_recent_patterns(
    entries: list[dict[str, Any]], kind: str = "", limit: int = 5, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    selected = select_entries(entries, include_all_agents)
    rows = []
    for entry in selected:
        entry_kind = normalize_kind(str(entry.get("kind") or "pattern"))
        if kind and entry_kind != kind:
            continue
        rows.append(entry)
    return rows[-limit:]


def write_state_snapshot(entries: list[dict[str, Any]]) -> dict[str, Any]:
    per_agent: dict[str, Counter[str]] = {}
    for entry in entries:
        agent = str(entry.get("agent") or "").strip()
        kind = str(entry.get("kind") or "unknown").strip()
        if not agent:
            continue
        per_agent.setdefault(agent, Counter())[kind] += 1

    state = {
        "_updated": utc_now(),
        "memory_path": str(MEMORY_PATH),
        "entry_count": len(entries),
        "agents": {
            agent: {
                "counts": dict(counter),
                "recent": [entry for entry in entries if str(entry.get("agent") or "") == agent][-5:],
            }
            for agent, counter in sorted(per_agent.items())
        },
        "recent": entries[-10:],
        "summaries": {
            "operator_view": {
                "agents": summarize_agents(entries, limit=10, include_all_agents=False),
                "task_shapes": summarize_task_shapes(entries, limit=10, include_all_agents=False),
                "failure_signatures": summarize_failure_signatures(entries, limit=10, include_all_agents=False),
                "recent_success": summarize_recent_patterns(entries, kind="success", limit=5, include_all_agents=False),
                "recent_failure": summarize_recent_patterns(entries, kind="failure", limit=5, include_all_agents=False),
            },
            "forensic_view": {
                "agents": summarize_agents(entries, limit=10, include_all_agents=True),
                "task_shapes": summarize_task_shapes(entries, limit=10, include_all_agents=True),
                "failure_signatures": summarize_failure_signatures(entries, limit=10, include_all_agents=True),
                "recent_success": summarize_recent_patterns(entries, kind="success", limit=5, include_all_agents=True),
                "recent_failure": summarize_recent_patterns(entries, kind="failure", limit=5, include_all_agents=True),
            },
        },
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return state


def cmd_record(args: argparse.Namespace) -> int:
    ensure_parent()
    entry = {
        "ts": args.ts or utc_now(),
        "agent": args.agent,
        "kind": normalize_kind(args.kind),
        "task_shape": args.task_shape,
        "context": args.context,
        "strategy": args.strategy,
        "recommended_pattern": args.recommended_pattern,
    }
    optional_fields = {
        "what_worked": args.what_worked,
        "what_failed": args.what_failed,
        "files_touched": args.files_touched,
        "tooling_path": args.tooling_path,
        "failure_signature": args.failure_signature,
        "evidence": args.evidence,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            entry[key] = value
    with MEMORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
    write_state_snapshot(load_entries())
    print(json.dumps(entry, ensure_ascii=True))
    return 0


def cmd_retrieve(args: argparse.Namespace) -> int:
    entries = load_entries()
    rows = retrieve(entries, query=args.query, limit=args.limit, agent=args.agent)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[strategy] no relevant patterns found")
        return 0
    print("[strategy] relevant prior patterns:")
    for row in rows:
        print(
            "  - "
            f"{row.get('kind','?').upper()} agent={row.get('agent','?')} score={row.get('_match_score','?')} "
            f"task_shape={row.get('task_shape','')}"
        )
        print(f"    strategy: {row.get('strategy','')}")
        if row.get("recommended_pattern"):
            print(f"    recommended: {row.get('recommended_pattern')}")
        if row.get("what_failed"):
            print(f"    failed: {row.get('what_failed')}")
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    ensure_parent()
    state = write_state_snapshot(load_entries())
    if args.json:
        print(json.dumps(state, ensure_ascii=True))
    else:
        print(str(STATE_PATH))
    return 0


def cmd_report_agents(args: argparse.Namespace) -> int:
    rows = summarize_agents(load_entries(), limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[strategy] no agent activity recorded")
        return 0
    print("[strategy] top agents by strategy memory volume:")
    for row in rows:
        print(f"  - agent={row['agent']} count={row['count']} kinds={row['kinds']}")
    return 0


def cmd_report_task_shapes(args: argparse.Namespace) -> int:
    rows = summarize_task_shapes(load_entries(), limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[strategy] no task_shape activity recorded")
        return 0
    print("[strategy] top task shapes in strategy memory:")
    for row in rows:
        print(f"  - task_shape={row['task_shape']} count={row['count']} latest={row['latest_ts']}")
    return 0


def cmd_report_recent(args: argparse.Namespace) -> int:
    kind = normalize_kind(args.kind)
    rows = summarize_recent_patterns(load_entries(), kind=kind, limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print(f"[strategy] no recent {kind} patterns recorded")
        return 0
    print(f"[strategy] recent {kind} patterns:")
    for row in rows[-args.limit :]:
        summary = row.get("recommended_pattern") or row.get("strategy") or ""
        print(
            "  - "
            f"{row.get('ts', '?')} agent={row.get('agent', '?')} "
            f"task_shape={row.get('task_shape', '')}: {summary}"
        )
        if row.get("what_failed"):
            print(f"    failed: {row.get('what_failed')}")
    return 0


def cmd_report_failure_signatures(args: argparse.Namespace) -> int:
    rows = summarize_failure_signatures(load_entries(), limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[strategy] no failure_signature patterns recorded")
        return 0
    print("[strategy] recurring failure_signatures in strategy memory:")
    for row in rows:
        print(
            "  - "
            f"agent={row['agent']} signature={row['failure_signature']} count={row['count']} "
            f"task_shape={row['task_shape']}: {row['recommended_pattern']}"
        )
        if row.get("what_failed"):
            print(f"    failed: {row['what_failed']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategy memory utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    record = sub.add_parser("record", help="Append a strategy memory entry")
    record.add_argument("--agent", required=True)
    record.add_argument("--kind", required=True)
    record.add_argument("--task-shape", required=True)
    record.add_argument("--context", default="")
    record.add_argument("--strategy", required=True)
    record.add_argument("--recommended-pattern", default="")
    record.add_argument("--what-worked", default="")
    record.add_argument("--what-failed", default="")
    record.add_argument("--files-touched", default="")
    record.add_argument("--tooling-path", default="")
    record.add_argument("--failure-signature", default="")
    record.add_argument("--evidence", default="")
    record.add_argument("--ts", default="")
    record.set_defaults(func=cmd_record)

    retrieve_cmd = sub.add_parser("retrieve", help="Retrieve relevant strategy patterns")
    retrieve_cmd.add_argument("--query", required=True)
    retrieve_cmd.add_argument("--agent", default="")
    retrieve_cmd.add_argument("--limit", type=int, default=3)
    retrieve_cmd.add_argument("--json", action="store_true")
    retrieve_cmd.set_defaults(func=cmd_retrieve)

    state_cmd = sub.add_parser("state", help="Write machine-readable strategy memory state")
    state_cmd.add_argument("--json", action="store_true")
    state_cmd.set_defaults(func=cmd_state)

    report_agents = sub.add_parser("report-agents", help="Summarize strategy memory by agent")
    report_agents.add_argument("--limit", type=int, default=10)
    report_agents.add_argument("--all-agents", action="store_true")
    report_agents.add_argument("--json", action="store_true")
    report_agents.set_defaults(func=cmd_report_agents)

    report_task_shapes = sub.add_parser("report-task-shapes", help="Summarize strategy memory by task_shape")
    report_task_shapes.add_argument("--limit", type=int, default=10)
    report_task_shapes.add_argument("--all-agents", action="store_true")
    report_task_shapes.add_argument("--json", action="store_true")
    report_task_shapes.set_defaults(func=cmd_report_task_shapes)

    report_recent = sub.add_parser("report-recent", help="Summarize recent strategy patterns by kind")
    report_recent.add_argument("--kind", required=True)
    report_recent.add_argument("--limit", type=int, default=5)
    report_recent.add_argument("--all-agents", action="store_true")
    report_recent.add_argument("--json", action="store_true")
    report_recent.set_defaults(func=cmd_report_recent)

    report_failure_signatures = sub.add_parser(
        "report-failure-signatures", help="Summarize recurring failure_signatures in strategy memory"
    )
    report_failure_signatures.add_argument("--limit", type=int, default=10)
    report_failure_signatures.add_argument("--all-agents", action="store_true")
    report_failure_signatures.add_argument("--json", action="store_true")
    report_failure_signatures.set_defaults(func=cmd_report_failure_signatures)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
