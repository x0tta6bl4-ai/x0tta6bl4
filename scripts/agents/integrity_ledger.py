#!/usr/bin/env python3
"""Integrity ledger for agent incidents and repeat failures.

Human nickname in the repo may stay "Base of Shame", but this tool keeps the
behavior operational and explicit:
- JSONL incident log at `.agent-coord/shame_base.jsonl`
- derived integrity score per agent
- machine-readable summaries for `agent-coord.sh`
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / ".agent-coord" / "shame_base.jsonl"
STATE_PATH = ROOT / ".agent-coord" / "integrity_state.json"
COORD_STATE_PATH = ROOT / ".agent-coord" / "state.json"
ROADMAP_QUEUE_PATH = ROOT / "plans" / "ROADMAP_AGENT_QUEUE.json"
DEFAULT_SCORE = 100
MIN_SCORE = 0
MAX_SCORE = 100

TYPE_WEIGHTS = {
    "fabrication": -50,
    "bullshit": -50,
    "overclaiming": -20,
    "ignored_memory_recall": -20,
    "missed_skill": -20,
    "ignored_source_of_truth": -20,
    "unjustified_manual_path": -15,
    "missed_parallel_review": -10,
    "repeat_error": -15,
    "process_violation": -10,
    "technical_error": -5,
    "fixed_error": 5,
}

SEVERITY_WEIGHTS = {
    "LOW": 0,
    "MEDIUM": -5,
    "HIGH": -10,
    "CRITICAL": -20,
}

FAILURE_SIGNATURES = {
    "handoff.invalid.missing_verification_summary": {
        "category": "handoff_schema",
        "description": "session_end payload omitted verification_summary",
        "owner_hint": "agent",
    },
    "handoff.invalid.missing_verification": {
        "category": "handoff_schema",
        "description": "session_end payload omitted verification entries",
        "owner_hint": "agent",
    },
    "handoff.invalid.missing_tool_audit": {
        "category": "handoff_schema",
        "description": "session_end payload omitted tool_audit",
        "owner_hint": "agent",
    },
    "handoff.invalid.memory_audit_schema": {
        "category": "handoff_schema",
        "description": "tool_audit omitted or malformed memory-aware handoff fields",
        "owner_hint": "agent",
    },
    "handoff.invalid.tool_audit_schema": {
        "category": "handoff_schema",
        "description": "tool_audit exists but violates required field schema",
        "owner_hint": "agent",
    },
    "handoff.invalid.verification_entry_schema": {
        "category": "handoff_schema",
        "description": "verification entry exists but violates command/exit_code schema",
        "owner_hint": "agent",
    },
    "handoff.invalid.other_schema": {
        "category": "handoff_schema",
        "description": "session_end payload failed schema validation outside the named common cases",
        "owner_hint": "agent",
    },
    "handoff.invalid.unknown": {
        "category": "handoff_schema",
        "description": "validator could not classify the rejected handoff payload",
        "owner_hint": "coordination",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_parent() -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_entries() -> list[dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with LEDGER_PATH.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append(
                    {
                        "ts": utc_now(),
                        "agent": "unknown",
                        "type": "process_violation",
                        "severity": "LOW",
                        "description": f"Malformed ledger row: {line[:160]}",
                        "impact": "Ledger parse drift",
                        "rating_delta": -5,
                    }
                )
    return rows


def load_known_agents() -> set[str]:
    roadmap_agents: set[str] = set()
    if ROADMAP_QUEUE_PATH.exists():
        try:
            data = json.loads(ROADMAP_QUEUE_PATH.read_text(encoding="utf-8"))
            queue_agents = data.get("agents", {})
            if isinstance(queue_agents, dict):
                roadmap_agents.update(str(name).strip() for name in queue_agents.keys() if str(name).strip())
        except Exception:
            pass
    if roadmap_agents:
        return roadmap_agents

    agents: set[str] = set()
    if COORD_STATE_PATH.exists():
        try:
            data = json.loads(COORD_STATE_PATH.read_text(encoding="utf-8"))
            state_agents = data.get("agents", {})
            if isinstance(state_agents, dict):
                agents.update(str(name).strip() for name in state_agents.keys() if str(name).strip())
        except Exception:
            pass
    return agents


def select_operator_agents(entries: list[dict[str, Any]], include_all_agents: bool) -> set[str]:
    if include_all_agents:
        return {str(entry.get("agent") or "").strip() for entry in entries if str(entry.get("agent") or "").strip()}
    known = load_known_agents()
    if known:
        return known
    return {str(entry.get("agent") or "").strip() for entry in entries if str(entry.get("agent") or "").strip()}


def clamp_score(score: int) -> int:
    return max(MIN_SCORE, min(MAX_SCORE, score))


def derive_delta(entry: dict[str, Any]) -> int:
    explicit = entry.get("rating_delta")
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass

    entry_type = str(entry.get("type") or "").strip().lower()
    severity = str(entry.get("severity") or "LOW").strip().upper()
    delta = TYPE_WEIGHTS.get(entry_type, 0) + SEVERITY_WEIGHTS.get(severity, 0)

    repeat_count = entry.get("repeat_count")
    try:
        count_value = int(repeat_count)
    except (TypeError, ValueError):
        count_value = 1
    if count_value > 1:
        delta -= min(30, (count_value - 1) * 5)
    return delta


def compute_agent_score(entries: list[dict[str, Any]], agent: str) -> dict[str, Any]:
    filtered = [entry for entry in entries if str(entry.get("agent") or "") == agent]
    score = DEFAULT_SCORE
    counts: Counter[str] = Counter()
    recent = filtered[-5:]
    for entry in filtered:
        score += derive_delta(entry)
        counts[str(entry.get("type") or "unknown")] += 1
    score = clamp_score(score)
    if score < 40:
        band = "compromised"
    elif score < 70:
        band = "probation"
    else:
        band = "clean"
    return {
        "agent": agent,
        "score": score,
        "band": band,
        "incident_count": len(filtered),
        "counts": dict(counts),
        "recent": recent,
    }


def render_recent(entries: list[dict[str, Any]], limit: int) -> str:
    rows = entries[-limit:]
    if not rows:
        return "[integrity] no incidents recorded"
    lines: list[str] = []
    for entry in rows:
        lines.append(
            "[integrity] "
            f"{entry.get('ts', '?')} {entry.get('agent', '?')} "
            f"{entry.get('type', '?')}/{entry.get('severity', '?')}: "
            f"{entry.get('description', '')}"
        )
    return "\n".join(lines)


def cmd_show(args: argparse.Namespace) -> int:
    entries = load_entries()
    if args.agent:
        entries = [entry for entry in entries if str(entry.get("agent") or "") == args.agent]
    print(render_recent(entries, args.limit))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    entries = load_entries()
    summary = compute_agent_score(entries, args.agent)
    if args.json:
        print(json.dumps(summary, ensure_ascii=True))
        return 0
    print(
        "[integrity] "
        f"agent={summary['agent']} score={summary['score']} "
        f"band={summary['band']} incidents={summary['incident_count']}"
    )
    for entry in summary["recent"]:
        print(
            "[integrity] recent "
            f"{entry.get('ts', '?')} {entry.get('type', '?')}/{entry.get('severity', '?')}: "
            f"{entry.get('description', '')}"
        )
    return 0


def cmd_session_check(args: argparse.Namespace) -> int:
    entries = load_entries()
    summary = compute_agent_score(entries, args.agent)
    payload = {
        "agent": summary["agent"],
        "score": summary["score"],
        "band": summary["band"],
        "incident_count": summary["incident_count"],
        "recent": summary["recent"],
        "global_recent": entries[-args.limit :],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
        return 0
    print(
        "[integrity] "
        f"agent={summary['agent']} score={summary['score']} "
        f"band={summary['band']} incidents={summary['incident_count']}"
    )
    if summary["recent"]:
        print("[integrity] recent agent incidents:")
        for entry in summary["recent"]:
            print(
                "  - "
                f"{entry.get('ts', '?')} {entry.get('type', '?')}/{entry.get('severity', '?')}: "
                f"{entry.get('description', '')}"
            )
    elif entries:
        print("[integrity] no agent-specific incidents; recent global incidents:")
        for entry in entries[-args.limit :]:
            print(
                "  - "
                f"{entry.get('ts', '?')} {entry.get('agent', '?')} "
                f"{entry.get('type', '?')}/{entry.get('severity', '?')}: "
                f"{entry.get('description', '')}"
            )
    else:
        print("[integrity] ledger is empty")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    ensure_parent()
    entry = {
        "ts": args.ts or utc_now(),
        "agent": args.agent,
        "type": args.type,
        "severity": args.severity,
        "description": args.description,
        "impact": args.impact,
    }
    optional_fields = {
        "evidence": args.evidence,
        "reporter": args.reporter,
        "repeat_count": args.repeat_count,
        "rating_delta": args.rating_delta,
        "status": args.status,
        "related_task": args.related_task,
        "failure_signature": args.failure_signature,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            entry[key] = value
    with LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
    write_state_snapshot(load_entries())
    print(json.dumps(entry, ensure_ascii=True))
    return 0


def write_state_snapshot(entries: list[dict[str, Any]]) -> dict[str, Any]:
    agents = sorted({str(entry.get("agent") or "").strip() for entry in entries if entry.get("agent")})
    state = {
        "_updated": utc_now(),
        "agents": {agent: compute_agent_score(entries, agent) for agent in agents},
        "summaries": {
            "operator_view": {
                "failure_signatures": summarize_failure_signatures(entries, limit=10, include_all_agents=False),
                "incident_types": summarize_incident_types(entries, limit=10, include_all_agents=False),
                "memory_incidents": summarize_incidents_by_type(
                    entries, incident_type="ignored_memory_recall", limit=10, include_all_agents=False
                ),
                "bands": summarize_agent_bands(entries, limit=10, include_all_agents=False),
                "agents_by_signature_volume": summarize_agents_by_signature_volume(
                    entries, limit=10, include_all_agents=False
                ),
            },
            "forensic_view": {
                "failure_signatures": summarize_failure_signatures(entries, limit=10, include_all_agents=True),
                "incident_types": summarize_incident_types(entries, limit=10, include_all_agents=True),
                "memory_incidents": summarize_incidents_by_type(
                    entries, incident_type="ignored_memory_recall", limit=10, include_all_agents=True
                ),
                "bands": summarize_agent_bands(entries, limit=10, include_all_agents=True),
                "agents_by_signature_volume": summarize_agents_by_signature_volume(
                    entries, limit=10, include_all_agents=True
                ),
            },
        },
        "ledger_path": str(LEDGER_PATH),
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return state


def cmd_state(args: argparse.Namespace) -> int:
    ensure_parent()
    entries = load_entries()
    state = write_state_snapshot(entries)
    if args.json:
        print(json.dumps(state, ensure_ascii=True))
    else:
        print(str(STATE_PATH))
    return 0


def cmd_report_signatures(args: argparse.Namespace) -> int:
    entries = load_entries()
    rows = summarize_failure_signatures(
        entries, agent=args.agent, limit=args.limit, include_all_agents=args.all_agents
    )
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[integrity] no failure_signature incidents recorded")
        return 0
    print("[integrity] recurring failure_signatures:")
    for row in rows:
        print(
            "  - "
            f"agent={row['agent']} signature={row['failure_signature']} "
            f"count={row['count']} category={row['category']} owner_hint={row['owner_hint']}: "
            f"{row['description']}"
        )
    return 0


def cmd_report_bands(args: argparse.Namespace) -> int:
    entries = load_entries()
    rows = summarize_agent_bands(entries, limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[integrity] no scored agents recorded")
        return 0
    print("[integrity] lowest integrity bands:")
    for row in rows:
        print(
            "  - "
            f"agent={row['agent']} score={row['score']} band={row['band']} incidents={row['incident_count']}"
        )
    return 0


def cmd_report_agents(args: argparse.Namespace) -> int:
    entries = load_entries()
    rows = summarize_agents_by_signature_volume(entries, limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[integrity] no failure_signature agents recorded")
        return 0
    print("[integrity] top agents by recurring failure_signatures:")
    for row in rows:
        print(
            "  - "
            f"agent={row['agent']} total={row['total_signature_events']} "
            f"distinct={row['distinct_signatures']} top={row['top_signature']} x{row['top_signature_count']}"
        )
    return 0


def cmd_report_incident_types(args: argparse.Namespace) -> int:
    entries = load_entries()
    rows = summarize_incident_types(entries, limit=args.limit, include_all_agents=args.all_agents)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
        return 0
    if not rows:
        print("[integrity] no incident-type summaries recorded")
        return 0
    print("[integrity] recurring incident types:")
    for row in rows:
        print(
            "  - "
            f"agent={row['agent']} type={row['type']} count={row['count']} severity={row['severity']}: "
            f"{row['description']}"
        )
    return 0


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_verification_entry(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    command = value.get("command")
    exit_code = value.get("exit_code")
    if not _is_nonempty_string(command):
        return False
    if not isinstance(exit_code, int):
        return False
    status = value.get("status")
    if status is not None and not _is_nonempty_string(status):
        return False
    return True


def _is_verification_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required_ints = ["total", "passed", "failed"]
    for field in required_ints:
        if not isinstance(value.get(field), int):
            return False
    if value["total"] < 0 or value["passed"] < 0 or value["failed"] < 0:
        return False
    return True


def find_recent_similar_incidents(
    entries: list[dict[str, Any]], agent: str, incident_type: str, description: str, limit: int = 5
) -> list[dict[str, Any]]:
    matched = [
        entry
        for entry in entries
        if str(entry.get("agent") or "") == agent
        and str(entry.get("type") or "") == incident_type
        and str(entry.get("description") or "") == description
    ]
    return matched[-limit:]


def derive_failure_signature(errors: list[str]) -> str:
    normalized = [str(item).strip() for item in errors if str(item).strip()]
    if not normalized:
        return "handoff.invalid.unknown"
    if any("verification_summary" in item for item in normalized):
        return "handoff.invalid.missing_verification_summary"
    if any("missing required list: verification" in item for item in normalized):
        return "handoff.invalid.missing_verification"
    if any("missing required object: tool_audit" in item for item in normalized):
        return "handoff.invalid.missing_tool_audit"
    if any("tool_audit.memory_" in item for item in normalized):
        return "handoff.invalid.memory_audit_schema"
    if any("tool_audit." in item for item in normalized):
        return "handoff.invalid.tool_audit_schema"
    if any("verification[" in item for item in normalized):
        return "handoff.invalid.verification_entry_schema"
    return "handoff.invalid.other_schema"


def describe_failure_signature(signature: str) -> dict[str, str]:
    data = FAILURE_SIGNATURES.get(signature, FAILURE_SIGNATURES["handoff.invalid.unknown"]).copy()
    data["signature"] = signature
    return data


def summarize_failure_signatures(
    entries: list[dict[str, Any]], agent: str = "", limit: int = 10, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    allowed_agents = select_operator_agents(entries, include_all_agents)
    filtered = []
    for entry in entries:
        row_agent = str(entry.get("agent") or "").strip()
        if agent and row_agent != agent:
            continue
        if not agent and row_agent not in allowed_agents:
            continue
        signature = str(entry.get("failure_signature") or "").strip()
        if not signature:
            continue
        filtered.append(entry)

    counts: Counter[tuple[str, str]] = Counter()
    for entry in filtered:
        counts[(str(entry.get("agent") or ""), str(entry.get("failure_signature") or ""))] += 1

    ranked = counts.most_common(limit)
    rows: list[dict[str, Any]] = []
    for (row_agent, signature), count in ranked:
        meta = describe_failure_signature(signature)
        rows.append(
            {
                "agent": row_agent,
                "failure_signature": signature,
                "count": count,
                "category": meta["category"],
                "description": meta["description"],
                "owner_hint": meta["owner_hint"],
            }
        )
    return rows


def summarize_agent_bands(entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False) -> list[dict[str, Any]]:
    agents = sorted(select_operator_agents(entries, include_all_agents))
    rows = [compute_agent_score(entries, agent) for agent in agents]
    rows.sort(key=lambda item: (item["score"], item["incident_count"] * -1, item["agent"]))
    return rows[:limit]


def summarize_agents_by_signature_volume(
    entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    allowed_agents = select_operator_agents(entries, include_all_agents)
    per_agent: dict[str, Counter[str]] = {}
    for entry in entries:
        agent = str(entry.get("agent") or "").strip()
        signature = str(entry.get("failure_signature") or "").strip()
        if not agent or not signature or agent not in allowed_agents:
            continue
        per_agent.setdefault(agent, Counter())[signature] += 1

    rows: list[dict[str, Any]] = []
    for agent, counts in per_agent.items():
        total = sum(counts.values())
        top_signature, top_count = counts.most_common(1)[0]
        rows.append(
            {
                "agent": agent,
                "total_signature_events": total,
                "distinct_signatures": len(counts),
                "top_signature": top_signature,
                "top_signature_count": top_count,
            }
        )
    rows.sort(key=lambda item: (-item["total_signature_events"], -item["distinct_signatures"], item["agent"]))
    return rows[:limit]


def summarize_incident_types(
    entries: list[dict[str, Any]], limit: int = 10, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    allowed_agents = select_operator_agents(entries, include_all_agents)
    counts: Counter[tuple[str, str]] = Counter()
    latest_meta: dict[tuple[str, str], dict[str, str]] = {}
    for entry in entries:
        agent = str(entry.get("agent") or "").strip()
        incident_type = str(entry.get("type") or "").strip()
        if not agent or not incident_type or agent not in allowed_agents:
            continue
        key = (agent, incident_type)
        counts[key] += 1
        latest_meta[key] = {
            "severity": str(entry.get("severity") or ""),
            "description": str(entry.get("description") or ""),
        }

    rows: list[dict[str, Any]] = []
    for (agent, incident_type), count in counts.most_common(limit):
        meta = latest_meta.get((agent, incident_type), {})
        rows.append(
            {
                "agent": agent,
                "type": incident_type,
                "count": count,
                "severity": meta.get("severity", ""),
                "description": meta.get("description", ""),
            }
        )
    return rows


def summarize_incidents_by_type(
    entries: list[dict[str, Any]], incident_type: str, limit: int = 10, include_all_agents: bool = False
) -> list[dict[str, Any]]:
    allowed_agents = select_operator_agents(entries, include_all_agents)
    counts: Counter[str] = Counter()
    latest_meta: dict[str, dict[str, str]] = {}
    for entry in entries:
        agent = str(entry.get("agent") or "").strip()
        entry_type = str(entry.get("type") or "").strip()
        if not agent or entry_type != incident_type or agent not in allowed_agents:
            continue
        counts[agent] += 1
        latest_meta[agent] = {
            "severity": str(entry.get("severity") or ""),
            "description": str(entry.get("description") or ""),
            "failure_signature": str(entry.get("failure_signature") or ""),
        }
    rows: list[dict[str, Any]] = []
    for agent, count in counts.most_common(limit):
        meta = latest_meta.get(agent, {})
        rows.append(
            {
                "agent": agent,
                "type": incident_type,
                "count": count,
                "severity": meta.get("severity", ""),
                "description": meta.get("description", ""),
                "failure_signature": meta.get("failure_signature", ""),
            }
        )
    return rows


def validate_handoff_payload(agent: str, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return (["payload must be a JSON object"], warnings)

    tool_audit = payload.get("tool_audit")
    if not isinstance(tool_audit, dict):
        errors.append("missing required object: tool_audit")
        return (errors, warnings)

    verification = payload.get("verification")
    if not isinstance(verification, list) or not verification:
        errors.append("missing required list: verification")
    else:
        for index, entry in enumerate(verification):
            if not _is_verification_entry(entry):
                errors.append(
                    f"verification[{index}] must be an object with command=<non-empty string> and exit_code=<int>"
                )

    verification_summary = payload.get("verification_summary")
    if not _is_verification_summary(verification_summary):
        errors.append("missing required object: verification_summary{total,passed,failed}")

    required_bool_fields = [
        "source_of_truth_checked",
        "memory_considered",
        "mcp_considered",
        "skills_considered",
        "subagents_considered",
        "manual_path_used",
    ]
    for field in required_bool_fields:
        if not isinstance(tool_audit.get(field), bool):
            errors.append(f"tool_audit.{field} must be boolean")

    required_list_fields = ["memory_tools_used", "skills_used", "subagents_used"]
    for field in required_list_fields:
        if not _is_string_list(tool_audit.get(field)):
            errors.append(f"tool_audit.{field} must be a list of strings")

    if not any(
        key in payload
        for key in (
            "verified_here",
            "result",
            "summary",
            "next",
            "next_for_claude",
            "next_for_gemini",
            "next_for_codex",
        )
    ):
        warnings.append(
            "payload is missing a closure summary/result field; include result, summary, next, or verified_here"
        )

    if isinstance(verification, list):
        nonzero = [entry for entry in verification if isinstance(entry, dict) and entry.get("exit_code") != 0]
        if nonzero and not _is_nonempty_string(payload.get("verification_note")):
            warnings.append("verification contains non-zero exit_code entries but verification_note is empty")
        if _is_verification_summary(verification_summary):
            total = len(verification)
            passed = sum(1 for entry in verification if isinstance(entry, dict) and entry.get("exit_code") == 0)
            failed = total - passed
            if verification_summary["total"] != total:
                warnings.append(
                    f"verification_summary.total={verification_summary['total']} does not match verification count={total}"
                )
            if verification_summary["passed"] != passed:
                warnings.append(
                    f"verification_summary.passed={verification_summary['passed']} does not match passed count={passed}"
                )
            if verification_summary["failed"] != failed:
                warnings.append(
                    f"verification_summary.failed={verification_summary['failed']} does not match failed count={failed}"
                )

    if tool_audit.get("source_of_truth_checked") and not _is_nonempty_string(tool_audit.get("source_of_truth")):
        warnings.append("tool_audit.source_of_truth_checked=true but tool_audit.source_of_truth is empty")

    if tool_audit.get("memory_considered") and not tool_audit.get("memory_tools_used") and not _is_nonempty_string(
        tool_audit.get("memory_skipped_reason")
    ):
        errors.append("tool_audit.memory_considered=true but neither memory_tools_used nor memory_skipped_reason was provided")

    if tool_audit.get("skills_considered") and not tool_audit.get("skills_used") and not _is_nonempty_string(
        tool_audit.get("skills_skipped_reason")
    ):
        warnings.append("skills were considered but no skills_used/skills_skipped_reason was provided")

    if tool_audit.get("subagents_considered") and not tool_audit.get("subagents_used") and not _is_nonempty_string(
        tool_audit.get("subagents_skipped_reason")
    ):
        warnings.append("subagents were considered but no subagents_used/subagents_skipped_reason was provided")

    if tool_audit.get("manual_path_used") and not _is_nonempty_string(tool_audit.get("manual_path_reason")):
        warnings.append("manual_path_used=true but manual_path_reason is empty")

    if tool_audit.get("mcp_considered") and tool_audit.get("mcp_used") not in (True, False):
        warnings.append("tool_audit.mcp_used should be boolean when MCP was considered")

    agent_name = str(payload.get("agent") or "").strip()
    if agent_name and agent_name != agent:
        warnings.append(f"payload.agent={agent_name} does not match session agent={agent}")

    return (errors, warnings)


def cmd_validate_handoff(args: argparse.Namespace) -> int:
    if bool(args.payload) == bool(args.payload_file):
        print("[integrity] provide exactly one of --payload or --payload-file", flush=True)
        return 2

    if args.payload_file:
        try:
            raw_payload = Path(args.payload_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[integrity] unable to read payload file: {exc}", flush=True)
            return 2
    else:
        raw_payload = args.payload
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        print(f"[integrity] invalid JSON payload: {exc}", flush=True)
        return 2

    errors, warnings = validate_handoff_payload(args.agent, payload)
    failure_signature = derive_failure_signature(errors) if errors else ""
    result = {
        "agent": args.agent,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "failure_signature": failure_signature,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        status = "ok" if not errors else "invalid"
        print(f"[integrity] handoff_payload {status} agent={args.agent}")
        for error in errors:
            print(f"  - error: {error}")
        for warning in warnings:
            print(f"  - warning: {warning}")
        if failure_signature:
            print(f"  - failure_signature: {failure_signature}")
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integrity ledger utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    show = sub.add_parser("show", help="Show recent incidents")
    show.add_argument("--agent", default="", help="Filter by agent")
    show.add_argument("--limit", type=int, default=5)
    show.set_defaults(func=cmd_show)

    score = sub.add_parser("score", help="Compute integrity score for an agent")
    score.add_argument("--agent", required=True)
    score.add_argument("--json", action="store_true")
    score.set_defaults(func=cmd_score)

    session = sub.add_parser("session-check", help="Print startup integrity context")
    session.add_argument("--agent", required=True)
    session.add_argument("--limit", type=int, default=5)
    session.add_argument("--json", action="store_true")
    session.set_defaults(func=cmd_session_check)

    record = sub.add_parser("record", help="Append an incident")
    record.add_argument("--agent", required=True)
    record.add_argument("--type", required=True)
    record.add_argument("--severity", default="MEDIUM")
    record.add_argument("--description", required=True)
    record.add_argument("--impact", required=True)
    record.add_argument("--evidence", default="")
    record.add_argument("--reporter", default="")
    record.add_argument("--repeat-count", type=int, default=1)
    record.add_argument("--rating-delta", type=int)
    record.add_argument("--status", default="")
    record.add_argument("--related-task", default="")
    record.add_argument("--failure-signature", default="")
    record.add_argument("--ts", default="")
    record.set_defaults(func=cmd_record)

    state = sub.add_parser("state", help="Write derived integrity state snapshot")
    state.add_argument("--json", action="store_true")
    state.set_defaults(func=cmd_state)

    report = sub.add_parser("report-signatures", help="Report recurring normalized failure signatures")
    report.add_argument("--agent", default="")
    report.add_argument("--limit", type=int, default=10)
    report.add_argument("--all-agents", action="store_true")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=cmd_report_signatures)

    bands = sub.add_parser("report-bands", help="Report lowest integrity-score agents")
    bands.add_argument("--limit", type=int, default=10)
    bands.add_argument("--all-agents", action="store_true")
    bands.add_argument("--json", action="store_true")
    bands.set_defaults(func=cmd_report_bands)

    agents = sub.add_parser("report-agents", help="Report agents with highest recurring failure_signature volume")
    agents.add_argument("--limit", type=int, default=10)
    agents.add_argument("--all-agents", action="store_true")
    agents.add_argument("--json", action="store_true")
    agents.set_defaults(func=cmd_report_agents)

    incident_types = sub.add_parser("report-incident-types", help="Report recurring integrity incident types")
    incident_types.add_argument("--limit", type=int, default=10)
    incident_types.add_argument("--all-agents", action="store_true")
    incident_types.add_argument("--json", action="store_true")
    incident_types.set_defaults(func=cmd_report_incident_types)

    handoff = sub.add_parser("validate-handoff", help="Validate session_end payload structure")
    handoff.add_argument("--agent", required=True)
    handoff.add_argument("--payload", default="")
    handoff.add_argument("--payload-file", default="")
    handoff.add_argument("--json", action="store_true")
    handoff.set_defaults(func=cmd_validate_handoff)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
