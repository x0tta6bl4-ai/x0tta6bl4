#!/usr/bin/env python3
"""Build a local boot-gap watch report from a saved read-only snapshot.

The report reads local snapshot files only. It does not SSH to NL/SPB and does
not mutate VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "boot-gap-watch-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "boot-gap-watch-2026-05-28.md"

PROVIDER_SIGNAL_PATTERNS = (
    r"guest-shutdown called",
    r"hypervisor initiated shutdown",
    r"system is powering down",
)
UNCLEAN_PATTERNS = (
    r"uncleanly shut down",
    r"corrupted or uncleanly",
    r"recovering journal",
    r"journal recovery",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def load_classifier():
    path = DIAGNOSTICS_DIR / "classify_vpn_snapshot.py"
    spec = importlib.util.spec_from_file_location("classify_vpn_snapshot_for_boot_gap_watch", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load classifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify_vpn_snapshot_for_boot_gap_watch"] = module
    spec.loader.exec_module(module)
    return module


def parse_boot_window(boot_history: str) -> dict[str, str | None]:
    previous_first = previous_last = current_first = None
    for line in boot_history.splitlines():
        stripped = line.strip()
        if stripped.startswith("-1 "):
            match = re.search(
                r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)\s+"
                r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)$",
                stripped,
            )
            if match:
                previous_first, previous_last = match.group(1), match.group(2)
        elif stripped.startswith("0 "):
            match = re.search(r"([A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC)", stripped)
            if match:
                current_first = match.group(1)
    return {
        "previous_boot_first_entry": previous_first,
        "previous_boot_last_entry": previous_last,
        "current_boot_first_entry": current_first,
    }


def parse_boot_gap_seconds(boot_window: dict[str, str | None]) -> int | None:
    previous_last = boot_window.get("previous_boot_last_entry")
    current_first = boot_window.get("current_boot_first_entry")
    if not previous_last or not current_first:
        return None
    try:
        previous = datetime.strptime(previous_last, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        current = datetime.strptime(current_first, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, int((current - previous).total_seconds()))


def extract_matching_lines(text: str, patterns: tuple[str, ...], *, limit: int = 8) -> list[str]:
    compiled = [re.compile(pattern, re.I) for pattern in patterns]
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if any(pattern.search(line) for pattern in compiled) and line not in seen:
            lines.append(line)
            seen.add(line)
    return lines[-limit:]


def choose_status(classification: dict[str, Any], boot_gap_seconds: int | None, unclean_lines: list[str], provider_lines: list[str]) -> str:
    overall = str(classification.get("overall_status") or "unknown")
    failure_domain = str(classification.get("failure_domain") or "unknown")
    action = str(classification.get("recommended_action") or "unknown")
    provider_status = str(classification.get("provider_status") or "unknown")
    if overall == "provider_outage" or failure_domain == "provider_host" or action == "provider_ticket":
        return "provider_ticket"
    if provider_lines and provider_status != "historical_incident":
        return "provider_watch"
    if provider_status in {"recent_boot_gap", "unclean_reboot", "historical_incident"}:
        return "watch"
    if boot_gap_seconds is not None and boot_gap_seconds >= 900:
        return "watch"
    if unclean_lines:
        return "watch"
    return "normal"


def recommended_action(status: str, classification: dict[str, Any]) -> str:
    transport = str(classification.get("transport_status") or "unknown")
    if status == "provider_ticket":
        return "build provider incident packet from the same fresh snapshot"
    if status in {"watch", "provider_watch"} and transport in {"healthy", "advisory"}:
        return "observe provider signal; do not restart NL while transport is healthy/advisory"
    if status in {"watch", "provider_watch"}:
        return "collect fresh read-only snapshot and build provider packet if transport is degraded"
    return "observe"


def build_payload(
    snapshot_dir: Path,
    *,
    classifier: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    classifier_fn = classifier or load_classifier().classify
    classification = classifier_fn(snapshot_dir)
    boot_history = read_text(snapshot_dir / "nl" / "boot_history.txt")
    current_boot_integrity = read_text(snapshot_dir / "nl" / "current_boot_integrity.txt")
    provider_signals = read_text(snapshot_dir / "nl" / "provider_signals.txt")
    previous_boot_tail = read_text(snapshot_dir / "nl" / "previous_boot_tail.txt")

    boot_window = parse_boot_window(boot_history)
    boot_gap_seconds = parse_boot_gap_seconds(boot_window)
    unclean_lines = extract_matching_lines(current_boot_integrity, UNCLEAN_PATTERNS)
    provider_lines = extract_matching_lines(provider_signals + "\n" + previous_boot_tail, PROVIDER_SIGNAL_PATTERNS)
    status = choose_status(classification, boot_gap_seconds, unclean_lines, provider_lines)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_boot_gap_watch_report.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot_dir),
        "status": status,
        "boot_window": boot_window,
        "boot_gap_seconds": boot_gap_seconds,
        "unclean_boot_lines": unclean_lines,
        "provider_signal_lines": provider_lines,
        "classification": {
            "overall_status": classification.get("overall_status", "unknown"),
            "transport_status": classification.get("transport_status", "unknown"),
            "provider_status": classification.get("provider_status", "unknown"),
            "failure_domain": classification.get("failure_domain", "unknown"),
            "recommended_action": classification.get("recommended_action", "unknown"),
        },
        "recommended_action": recommended_action(status, classification),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    classification = payload["classification"]
    window = payload["boot_window"]
    lines = [
        "# Boot Gap Watch",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"snapshot: `{payload['snapshot']}`",
        "",
        "## Summary",
        "",
        "```text",
        f"status={payload.get('status')}",
        f"boot_gap_seconds={payload.get('boot_gap_seconds')}",
        f"overall_status={classification.get('overall_status')}",
        f"transport_status={classification.get('transport_status')}",
        f"provider_status={classification.get('provider_status')}",
        f"failure_domain={classification.get('failure_domain')}",
        f"recommended_action={payload.get('recommended_action')}",
        "nl_mutation_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Boot Window",
        "",
        "```text",
        f"previous_boot_first_entry={window.get('previous_boot_first_entry')}",
        f"previous_boot_last_entry={window.get('previous_boot_last_entry')}",
        f"current_boot_first_entry={window.get('current_boot_first_entry')}",
        "```",
        "",
        "## Unclean Boot Lines",
        "",
    ]
    lines.extend(f"- {line}" for line in (payload.get("unclean_boot_lines") or ["none"]))
    lines.extend(["", "## Provider Signal Lines", ""])
    lines.extend(f"- {line}" for line in (payload.get("provider_signal_lines") or ["none"]))
    lines.extend(["", "No NL or SPB writes were performed by this boot-gap watch report."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local boot-gap watch report")
    parser.add_argument("--snapshot", help="Existing snapshot directory. Defaults to latest.")
    parser.add_argument("--snapshots-dir", default=str(SNAPSHOTS_DIR))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot) if args.snapshot else latest_snapshot(Path(args.snapshots_dir))
    if snapshot_dir is None:
        raise SystemExit(f"no snapshots found under {args.snapshots_dir}")
    payload = build_payload(snapshot_dir)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
