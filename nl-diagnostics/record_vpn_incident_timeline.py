#!/usr/bin/env python3
"""Append a local VPN incident timeline event from existing reports.

The recorder reads local JSON reports only. It does not SSH to NL/SPB and does
not mutate VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
DEFAULT_SNAPSHOT = SNAPSHOTS_DIR / "20260527T230246Z"
DEFAULT_DECISION = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_BOOT_GAP = DIAGNOSTICS_DIR / "boot-gap-watch-2026-05-28.json"
DEFAULT_HISTORY = DIAGNOSTICS_DIR / "blocking-probe-history-2026-05-28.json"
DEFAULT_OPERATOR_CARD = DIAGNOSTICS_DIR / "vpn-operator-card-2026-05-28.json"
DEFAULT_FAILOVER = DIAGNOSTICS_DIR / "manual-failover-plan-2026-05-28.json"
DEFAULT_TRANSPORT_PROBE = DIAGNOSTICS_DIR / "nl-transport-probe-2026-05-28.json"
DEFAULT_TRANSPORT_UPTIME = DIAGNOSTICS_DIR / "nl-transport-uptime-summary-2026-05-28.json"
DEFAULT_READINESS = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.json"
DEFAULT_JSONL_OUT = DIAGNOSTICS_DIR / "vpn-incident-timeline-2026-05-28.jsonl"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-incident-timeline-2026-05-28.md"


def provider_packet_path(snapshot: Path, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path:
    return (
        diagnostics_dir
        / "provider-incident-packets"
        / f"provider-incident-packet-{snapshot.name}.json"
    )


def latest_snapshot(snapshots_dir: Path = SNAPSHOTS_DIR) -> Path | None:
    if not snapshots_dir.exists():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    return sorted(candidates, key=lambda path: path.name)[-1] if candidates else None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_events(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def choose_event_type(
    *,
    decision_name: str,
    failure_domain: str,
    boot_gap_status: str,
    transport_probe_status: str,
    uptime_status: str,
) -> str:
    if decision_name == "provider_ticket" or failure_domain == "provider_host":
        return "provider_ticket"
    if transport_probe_status not in {"healthy", "unknown"}:
        return "transport_watch"
    if uptime_status not in {"stable_healthy", "unknown"}:
        return "transport_watch"
    if boot_gap_status in {"watch", "provider_watch"}:
        return "provider_watch"
    return "observe"


def build_event(
    *,
    snapshot: Path,
    decision_report: dict[str, Any],
    boot_gap: dict[str, Any],
    provider_packet: dict[str, Any],
    history: dict[str, Any],
    operator_card: dict[str, Any],
    failover: dict[str, Any],
    transport_probe: dict[str, Any],
    transport_uptime: dict[str, Any],
    readiness: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (now or datetime.now(timezone.utc)).isoformat()
    snapshot_name = snapshot.name
    decision = decision_report.get("decision") or {}
    classification = decision_report.get("classification") or {}
    history_summary = history.get("summary") or {}
    operator = operator_card.get("operator") or {}
    uptime_summary = transport_uptime.get("summary") or {}
    readiness_summary = readiness.get("summary") or {}

    decision_name = str(decision.get("decision") or "unknown")
    failure_domain = str(classification.get("failure_domain") or "unknown")
    boot_gap_status = str(boot_gap.get("status") or "unknown")
    transport_probe_status = str(transport_probe.get("status") or "unknown")
    uptime_status = str(uptime_summary.get("status") or "unknown")
    event_type = choose_event_type(
        decision_name=decision_name,
        failure_domain=failure_domain,
        boot_gap_status=boot_gap_status,
        transport_probe_status=transport_probe_status,
        uptime_status=uptime_status,
    )

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/record_vpn_incident_timeline.py",
        "event_id": f"{snapshot_name}-{generated_at}",
        "generated_at": generated_at,
        "snapshot": str(snapshot),
        "snapshot_name": snapshot_name,
        "event_type": event_type,
        "decision": decision_name,
        "decision_confidence": decision.get("confidence", "unknown"),
        "operator_status": operator.get("operator_status", "unknown"),
        "overall_status": classification.get("overall_status", "unknown"),
        "transport_status": classification.get("transport_status", "unknown"),
        "telegram_media_status": classification.get("telegram_media_status", "unknown"),
        "provider_status": classification.get("provider_status", "unknown"),
        "failure_domain": failure_domain,
        "boot_gap_watch_status": boot_gap_status,
        "boot_gap_seconds": boot_gap.get("boot_gap_seconds", "unknown"),
        "provider_packet_type": provider_packet.get("packet_type", "unknown"),
        "provider_packet_stale": provider_packet.get("snapshot_stale", "unknown"),
        "provider_packet_snapshot_age_seconds": provider_packet.get("snapshot_age_seconds", "unknown"),
        "blocking_history_trend": history_summary.get("trend", "unknown"),
        "blocking_history_snapshot_count": history_summary.get("snapshot_count", 0),
        "manual_failover_status": failover.get("status", "unknown"),
        "nl_transport_probe_status": transport_probe_status,
        "nl_transport_probe_ok_count": f"{transport_probe.get('ok_count', 'unknown')}/{transport_probe.get('port_count', 'unknown')}",
        "nl_transport_uptime_status": uptime_status,
        "nl_transport_uptime_samples": uptime_summary.get("sample_count", "unknown"),
        "nl_transport_uptime_bad_streak": uptime_summary.get("consecutive_non_healthy", "unknown"),
        "readiness_audit_status": readiness.get("overall_status", "unknown"),
        "readiness_missing": readiness_summary.get("missing", "unknown"),
        "timeline_action": timeline_action(event_type),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def timeline_action(event_type: str) -> str:
    if event_type == "provider_ticket":
        return "open or update provider packet from fresh evidence"
    if event_type == "transport_watch":
        return "collect fresh read-only snapshot and compare listeners/provider signals"
    if event_type == "provider_watch":
        return "keep provider boot gap on watch while transport is healthy"
    return "observe and refresh evidence during the next visible outage"


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def render_markdown(events: list[dict[str, Any]], *, limit: int = 30) -> str:
    selected = events[-limit:]
    lines = [
        "# VPN Incident Timeline",
        "",
        f"event_count: `{len(events)}`",
        "",
        "## Recent Events",
        "",
        "| Time | Snapshot | Type | Decision | Transport | Provider | Boot Gap | Action |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for event in selected:
        lines.append(
            "| "
            f"`{event.get('generated_at', 'unknown')}` | "
            f"`{event.get('snapshot_name', 'unknown')}` | "
            f"`{event.get('event_type', 'unknown')}` | "
            f"`{event.get('decision', 'unknown')}` | "
            f"`{event.get('nl_transport_probe_status', 'unknown')}` | "
            f"`{event.get('provider_status', 'unknown')}` | "
            f"`{event.get('boot_gap_seconds', 'unknown')}` | "
            f"{event.get('timeline_action', 'review evidence')} |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "```text",
            "nl_mutation_allowed=false",
            "spb_fallback_allowed=false",
            "automatic_failover_allowed=false",
            "raw VPN URIs, UUIDs, private keys, and bot tokens are not recorded",
            "```",
            "",
            "No NL or SPB writes were performed by this timeline recorder.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a local VPN incident timeline event")
    parser.add_argument("--snapshot", help="Existing snapshot directory. Defaults to latest local snapshot.")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--boot-gap", default=str(DEFAULT_BOOT_GAP))
    parser.add_argument("--provider-packet", help="Provider packet JSON. Defaults to the packet matching --snapshot.")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--operator-card", default=str(DEFAULT_OPERATOR_CARD))
    parser.add_argument("--failover", default=str(DEFAULT_FAILOVER))
    parser.add_argument("--transport-probe", default=str(DEFAULT_TRANSPORT_PROBE))
    parser.add_argument("--transport-uptime", default=str(DEFAULT_TRANSPORT_UPTIME))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--jsonl-out", default=str(DEFAULT_JSONL_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    snapshot = Path(args.snapshot) if args.snapshot else latest_snapshot() or DEFAULT_SNAPSHOT
    provider_packet = Path(args.provider_packet) if args.provider_packet else provider_packet_path(snapshot)

    event = build_event(
        snapshot=snapshot,
        decision_report=read_json(Path(args.decision)),
        boot_gap=read_json(Path(args.boot_gap)),
        provider_packet=read_json(provider_packet),
        history=read_json(Path(args.history)),
        operator_card=read_json(Path(args.operator_card)),
        failover=read_json(Path(args.failover)),
        transport_probe=read_json(Path(args.transport_probe)),
        transport_uptime=read_json(Path(args.transport_uptime)),
        readiness=read_json(Path(args.readiness)),
    )
    jsonl_out = Path(args.jsonl_out)
    append_event(jsonl_out, event)
    events = read_events(jsonl_out)
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(events), encoding="utf-8")
    if not args.jsonl_out and not args.markdown_out:
        print(json.dumps(event, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
