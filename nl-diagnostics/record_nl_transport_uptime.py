#!/usr/bin/env python3
"""Record outside-in NL transport probe results into a local uptime history.

This script reads a local probe JSON and writes local history/report files only.
It does not SSH to NL/SPB and does not mutate VPN runtime state.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_PROBE_JSON = DIAGNOSTICS_DIR / "nl-transport-probe-2026-05-28.json"
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "nl-transport-uptime-history.jsonl"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "nl-transport-uptime-summary-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "nl-transport-uptime-summary-2026-05-28.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def compact_probe(probe: dict[str, Any]) -> dict[str, Any]:
    results = probe.get("results") if isinstance(probe.get("results"), list) else []
    compact_results = []
    for row in results:
        if not isinstance(row, dict):
            continue
        compact_results.append(
            {
                "port": row.get("port"),
                "ok": row.get("ok") is True,
                "latency_ms": row.get("latency_ms"),
                "error": str(row.get("error") or "")[-200:],
            }
        )
    return {
        "generated_at": probe.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "host": probe.get("host", "unknown"),
        "ports": probe.get("ports") or [row.get("port") for row in compact_results],
        "status": probe.get("status", "unknown"),
        "ok_count": probe.get("ok_count", 0),
        "port_count": probe.get("port_count", len(compact_results)),
        "results": compact_results,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def append_record(path: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history(path)
    if not history or history[-1].get("generated_at") != record.get("generated_at"):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        history.append(record)
    return history


def consecutive_non_healthy(history: list[dict[str, Any]]) -> int:
    count = 0
    for row in reversed(history):
        if row.get("status") == "healthy":
            break
        count += 1
    return count


def summarize(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "status": "insufficient_data",
            "sample_count": 0,
            "latest_status": "missing",
            "consecutive_non_healthy": 0,
        }
    latest = history[-1]
    counts = Counter(str(row.get("status") or "unknown") for row in history)
    bad_streak = consecutive_non_healthy(history)
    latest_status = str(latest.get("status") or "unknown")
    if latest_status == "healthy" and bad_streak == 0:
        status = "stable_healthy"
    elif latest_status in {"degraded", "critical"}:
        status = "watch"
    else:
        status = "review"
    return {
        "status": status,
        "sample_count": len(history),
        "latest_status": latest_status,
        "latest_generated_at": latest.get("generated_at"),
        "latest_ok_count": latest.get("ok_count"),
        "latest_port_count": latest.get("port_count"),
        "consecutive_non_healthy": bad_streak,
        "status_counts": dict(counts),
        "recent_statuses": [row.get("status", "unknown") for row in history[-12:]],
    }


def build_payload(history: list[dict[str, Any]], history_path: Path) -> dict[str, Any]:
    summary = summarize(history)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/record_nl_transport_uptime.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history": str(history_path),
        "summary": summary,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# NL Transport Uptime Summary",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"history: `{payload['history']}`",
        "",
        "## Summary",
        "",
        "```text",
        f"status={summary.get('status')}",
        f"sample_count={summary.get('sample_count')}",
        f"latest_status={summary.get('latest_status')}",
        f"latest_ok_count={summary.get('latest_ok_count')}/{summary.get('latest_port_count')}",
        f"consecutive_non_healthy={summary.get('consecutive_non_healthy')}",
        "nl_mutation_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "Recent statuses:",
        "",
        "```text",
        " ".join(str(value) for value in summary.get("recent_statuses", [])),
        "```",
        "",
        "No NL or SPB writes were performed by this uptime recorder.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record NL transport uptime from local probe JSON")
    parser.add_argument("--probe-json", default=str(DEFAULT_PROBE_JSON))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--no-append", action="store_true")
    args = parser.parse_args()

    record = compact_probe(read_json(Path(args.probe_json)))
    history_path = Path(args.history)
    if args.no_append:
        history = load_history(history_path) + [record]
    else:
        history = append_record(history_path, record)
    payload = build_payload(history, history_path)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
