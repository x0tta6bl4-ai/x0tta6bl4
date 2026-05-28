#!/usr/bin/env python3
"""Refresh local VPN planning reports from existing read-only evidence.

This script does not collect a new snapshot, does not SSH to NL or SPB, and
does not mutate VPN runtime state. It only rebuilds local reports from the
latest saved snapshot and local planning inputs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
REFRESH_JSON = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.json"
REFRESH_MARKDOWN = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.md"
TIMELINE_JSONL = DIAGNOSTICS_DIR / "vpn-incident-timeline-2026-05-28.jsonl"
TIMELINE_MARKDOWN = DIAGNOSTICS_DIR / "vpn-incident-timeline-2026-05-28.md"
DEFAULT_LOCAL_TMPDIR = ROOT / ".tmp"


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def provider_packet_paths(snapshot_dir: Path, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> list[str]:
    stem = f"provider-incident-packet-{snapshot_dir.name}"
    output_dir = diagnostics_dir / "provider-incident-packets"
    return [
        str(output_dir / f"{stem}.json"),
        str(output_dir / f"{stem}.md"),
    ]


def readiness_audit_command(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    command = [
        "python3",
        str(diagnostics_dir / "audit_vpn_plan_readiness.py"),
        "--json-out",
        str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json"),
        "--markdown-out",
        str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.md"),
    ]
    if snapshot_dir is not None:
        command.extend(["--provider-packet", provider_packet_paths(snapshot_dir, diagnostics_dir)[0]])
    return {
        "id": "readiness_audit",
        "command": command,
        "outputs": [
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json"),
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.md"),
        ],
    }


def incident_timeline_command(
    snapshot_dir: Path,
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    return {
        "id": "incident_timeline",
        "command": [
            "python3",
            str(diagnostics_dir / "record_vpn_incident_timeline.py"),
            "--snapshot",
            str(snapshot_dir),
            "--provider-packet",
            provider_packet_paths(snapshot_dir, diagnostics_dir)[0],
            "--jsonl-out",
            str(diagnostics_dir / "vpn-incident-timeline-2026-05-28.jsonl"),
            "--markdown-out",
            str(diagnostics_dir / "vpn-incident-timeline-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "vpn-incident-timeline-2026-05-28.jsonl"),
            str(diagnostics_dir / "vpn-incident-timeline-2026-05-28.md"),
        ],
    }


def manual_failover_readiness_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "manual_failover_readiness",
        "command": [
            "python3",
            str(diagnostics_dir / "audit_manual_failover_readiness.py"),
            "--json-out",
            str(diagnostics_dir / "manual-failover-readiness-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "manual-failover-readiness-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "manual-failover-readiness-2026-05-28.json"),
            str(diagnostics_dir / "manual-failover-readiness-2026-05-28.md"),
        ],
    }


def secondary_exit_requirements_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "secondary_exit_requirements",
        "command": [
            "python3",
            str(diagnostics_dir / "build_secondary_exit_requirements.py"),
            "--json-out",
            str(diagnostics_dir / "secondary-exit-requirements-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "secondary-exit-requirements-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "secondary-exit-requirements-2026-05-28.json"),
            str(diagnostics_dir / "secondary-exit-requirements-2026-05-28.md"),
        ],
    }


def secondary_candidate_score_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "secondary_candidate_score",
        "command": [
            "python3",
            str(diagnostics_dir / "score_secondary_exit_candidates.py"),
            "--json-out",
            str(diagnostics_dir / "secondary-exit-candidate-score-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "secondary-exit-candidate-score-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "secondary-exit-candidate-score-2026-05-28.json"),
            str(diagnostics_dir / "secondary-exit-candidate-score-2026-05-28.md"),
        ],
    }


def local_diagnostic_environment_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "local_diagnostic_environment",
        "command": [
            "python3",
            str(diagnostics_dir / "audit_local_diagnostic_environment.py"),
            "--json-out",
            str(diagnostics_dir / "local-diagnostic-environment-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "local-diagnostic-environment-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "local-diagnostic-environment-2026-05-28.json"),
            str(diagnostics_dir / "local-diagnostic-environment-2026-05-28.md"),
        ],
    }


def local_root_cleanup_plan_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "local_root_cleanup_plan",
        "command": [
            "python3",
            str(diagnostics_dir / "plan_local_root_cleanup.py"),
            "--local-env",
            str(diagnostics_dir / "local-diagnostic-environment-2026-05-28.json"),
            "--json-out",
            str(diagnostics_dir / "local-root-cleanup-plan-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "local-root-cleanup-plan-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "local-root-cleanup-plan-2026-05-28.json"),
            str(diagnostics_dir / "local-root-cleanup-plan-2026-05-28.md"),
        ],
    }


def command_plan(
    snapshot_dir: Path,
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
    *,
    include_readiness_audit: bool = True,
) -> list[dict[str, Any]]:
    plan = [
        {
            "id": "blocking_history",
            "command": [
                "python3",
                str(diagnostics_dir / "summarize_blocking_probe_history.py"),
                "--json-out",
                str(diagnostics_dir / "blocking-probe-history-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "blocking-probe-history-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "blocking-probe-history-2026-05-28.json"),
                str(diagnostics_dir / "blocking-probe-history-2026-05-28.md"),
            ],
        },
        {
            "id": "decision_report",
            "command": [
                "python3",
                str(diagnostics_dir / "build_vpn_decision_report.py"),
                "--snapshot",
                str(snapshot_dir),
                "--json-out",
                str(diagnostics_dir / "current-vpn-decision-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "current-vpn-decision-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "current-vpn-decision-2026-05-28.json"),
                str(diagnostics_dir / "current-vpn-decision-2026-05-28.md"),
            ],
        },
        {
            "id": "boot_gap_watch",
            "command": [
                "python3",
                str(diagnostics_dir / "build_boot_gap_watch_report.py"),
                "--snapshot",
                str(snapshot_dir),
                "--json-out",
                str(diagnostics_dir / "boot-gap-watch-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "boot-gap-watch-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "boot-gap-watch-2026-05-28.json"),
                str(diagnostics_dir / "boot-gap-watch-2026-05-28.md"),
            ],
        },
        {
            "id": "provider_packet",
            "command": [
                "python3",
                str(diagnostics_dir / "build_provider_incident_packet.py"),
                "--snapshot-dir",
                str(snapshot_dir),
                "--output-dir",
                str(diagnostics_dir / "provider-incident-packets"),
            ],
            "outputs": provider_packet_paths(snapshot_dir, diagnostics_dir),
        },
        {
            "id": "improvement_backlog",
            "command": [
                "python3",
                str(diagnostics_dir / "build_vpn_improvement_backlog.py"),
                "--json-out",
                str(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.json"),
                str(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.md"),
            ],
        },
        {
            "id": "manual_failover_plan",
            "command": [
                "python3",
                str(diagnostics_dir / "build_manual_failover_plan.py"),
                "--json-out",
                str(diagnostics_dir / "manual-failover-plan-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "manual-failover-plan-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "manual-failover-plan-2026-05-28.json"),
                str(diagnostics_dir / "manual-failover-plan-2026-05-28.md"),
            ],
        },
        {
            "id": "nl_transport_probe",
            "command": [
                "python3",
                str(diagnostics_dir / "probe_nl_transport_ports.py"),
                "--json-out",
                str(diagnostics_dir / "nl-transport-probe-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "nl-transport-probe-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "nl-transport-probe-2026-05-28.json"),
                str(diagnostics_dir / "nl-transport-probe-2026-05-28.md"),
            ],
        },
        {
            "id": "nl_transport_uptime",
            "command": [
                "python3",
                str(diagnostics_dir / "record_nl_transport_uptime.py"),
                "--probe-json",
                str(diagnostics_dir / "nl-transport-probe-2026-05-28.json"),
                "--history",
                str(diagnostics_dir / "nl-transport-uptime-history.jsonl"),
                "--json-out",
                str(diagnostics_dir / "nl-transport-uptime-summary-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "nl-transport-uptime-summary-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "nl-transport-uptime-history.jsonl"),
                str(diagnostics_dir / "nl-transport-uptime-summary-2026-05-28.json"),
                str(diagnostics_dir / "nl-transport-uptime-summary-2026-05-28.md"),
            ],
        },
        {
            "id": "secondary_probe_template_check",
            "command": [
                "python3",
                str(diagnostics_dir / "probe_secondary_exit.py"),
                "--config",
                str(diagnostics_dir / "manual-failover-secondary.example.json"),
                "--json-out",
                str(diagnostics_dir / "secondary-exit-probe-template-2026-05-28.json"),
            ],
            "outputs": [
                str(diagnostics_dir / "secondary-exit-probe-template-2026-05-28.json"),
            ],
        },
        manual_failover_readiness_command(diagnostics_dir),
        secondary_candidate_score_command(diagnostics_dir),
        secondary_exit_requirements_command(diagnostics_dir),
        local_diagnostic_environment_command(diagnostics_dir),
        local_root_cleanup_plan_command(diagnostics_dir),
        {
            "id": "operator_card",
            "command": [
                "python3",
                str(diagnostics_dir / "build_vpn_operator_card.py"),
                "--json-out",
                str(diagnostics_dir / "vpn-operator-card-2026-05-28.json"),
                "--markdown-out",
                str(diagnostics_dir / "vpn-operator-card-2026-05-28.md"),
            ],
            "outputs": [
                str(diagnostics_dir / "vpn-operator-card-2026-05-28.json"),
                str(diagnostics_dir / "vpn-operator-card-2026-05-28.md"),
            ],
        },
    ]
    if include_readiness_audit:
        plan.append(readiness_audit_command(diagnostics_dir, snapshot_dir))
        plan.append(incident_timeline_command(snapshot_dir, diagnostics_dir))
    return plan


def command_is_local_only(command: list[str]) -> bool:
    forbidden = {"ssh", "scp", "rsync", "systemctl", "sudo"}
    return not any(Path(part).name in forbidden for part in command)


def local_command_env(
    base_env: dict[str, str] | None = None,
    tmpdir: Path = DEFAULT_LOCAL_TMPDIR,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    if "TMPDIR" not in env and tmpdir.is_dir():
        env["TMPDIR"] = str(tmpdir)
    return env


def run_plan(
    plan: list[dict[str, Any]],
    *,
    cwd: Path,
    runner=subprocess.run,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in plan:
        command = item["command"]
        if not command_is_local_only(command):
            rows.append(
                {
                    "id": item["id"],
                    "ok": False,
                    "exit_code": 126,
                    "error": "blocked non-local command",
                    "outputs": item.get("outputs", []),
                }
            )
            continue
        completed = runner(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=local_command_env(),
        )
        rows.append(
            {
                "id": item["id"],
                "ok": completed.returncode == 0,
                "exit_code": completed.returncode,
                "stdout_tail": completed.stdout[-1000:],
                "stderr_tail": completed.stderr[-1000:],
                "outputs": item.get("outputs", []),
            }
        )
    return rows


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def latest_timeline_event(path: Path) -> tuple[dict[str, Any], int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}, 0
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
    return (events[-1], len(events)) if events else ({}, 0)


def build_summary(diagnostics_dir: Path) -> dict[str, Any]:
    decision = read_json(diagnostics_dir / "current-vpn-decision-2026-05-28.json").get("decision") or {}
    boot_gap = read_json(diagnostics_dir / "boot-gap-watch-2026-05-28.json")
    provider_packet_path = provider_packet_paths(Path(str(boot_gap.get("snapshot") or "")), diagnostics_dir)[0]
    provider_packet = read_json(Path(provider_packet_path))
    history = read_json(diagnostics_dir / "blocking-probe-history-2026-05-28.json").get("summary") or {}
    backlog = read_json(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.json").get("summary") or {}
    failover = read_json(diagnostics_dir / "manual-failover-plan-2026-05-28.json")
    transport_probe = read_json(diagnostics_dir / "nl-transport-probe-2026-05-28.json")
    uptime = read_json(diagnostics_dir / "nl-transport-uptime-summary-2026-05-28.json").get("summary") or {}
    secondary = read_json(diagnostics_dir / "secondary-exit-probe-template-2026-05-28.json")
    failover_readiness = read_json(diagnostics_dir / "manual-failover-readiness-2026-05-28.json")
    secondary_score = read_json(diagnostics_dir / "secondary-exit-candidate-score-2026-05-28.json")
    secondary_score_summary = secondary_score.get("summary") or {}
    secondary_requirements = read_json(diagnostics_dir / "secondary-exit-requirements-2026-05-28.json")
    secondary_requirements_summary = secondary_requirements.get("summary") or {}
    local_env = read_json(diagnostics_dir / "local-diagnostic-environment-2026-05-28.json")
    local_env_summary = local_env.get("summary") or {}
    cleanup_plan = read_json(diagnostics_dir / "local-root-cleanup-plan-2026-05-28.json")
    cleanup_summary = cleanup_plan.get("summary") or {}
    operator = read_json(diagnostics_dir / "vpn-operator-card-2026-05-28.json").get("operator") or {}
    readiness = read_json(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json")
    readiness_summary = readiness.get("summary") or {}
    timeline_event, timeline_count = latest_timeline_event(diagnostics_dir / "vpn-incident-timeline-2026-05-28.jsonl")
    return {
        "decision": decision.get("decision", "unknown"),
        "decision_confidence": decision.get("confidence", "unknown"),
        "operator_status": operator.get("operator_status", "unknown"),
        "boot_gap_watch_status": boot_gap.get("status", "unknown"),
        "boot_gap_seconds": boot_gap.get("boot_gap_seconds", "unknown"),
        "provider_packet_type": provider_packet.get("packet_type", "unknown"),
        "provider_packet_stale": provider_packet.get("snapshot_stale", "unknown"),
        "provider_packet_snapshot_age_seconds": provider_packet.get("snapshot_age_seconds", "unknown"),
        "blocking_history_trend": history.get("trend", "unknown"),
        "blocking_history_snapshot_count": history.get("snapshot_count", 0),
        "backlog_decision": backlog.get("decision", "unknown"),
        "manual_failover_status": failover.get("status", "unknown"),
        "manual_failover_readiness_status": failover_readiness.get("status", "unknown"),
        "manual_failover_probe_allowed": failover_readiness.get("manual_probe_allowed", "unknown"),
        "manual_failover_switch_allowed": failover_readiness.get("manual_switch_allowed", "unknown"),
        "secondary_candidate_score_status": secondary_score.get("status", "unknown"),
        "secondary_candidate_viable_count": secondary_score_summary.get("viable_count", "unknown"),
        "secondary_exit_requirements_status": secondary_requirements.get("status", "unknown"),
        "secondary_exit_requirements_missing": ",".join(secondary_requirements_summary.get("missing_items") or []) or "none",
        "local_diagnostic_environment_status": local_env.get("status", "unknown"),
        "local_root_status": local_env_summary.get("root_status", "unknown"),
        "local_tmpdir_writable": local_env_summary.get("diagnostic_tmpdir_writable", "unknown"),
        "local_recommended_tmpdir_prefix": local_env_summary.get("recommended_tmpdir_prefix", "unknown"),
        "local_root_cleanup_plan_status": cleanup_plan.get("status", "unknown"),
        "local_root_cleanup_estimated_reclaim_gib": cleanup_summary.get("estimated_reclaim_gib", "unknown"),
        "local_root_cleanup_execute_allowed": cleanup_summary.get("cleanup_execute_allowed", "unknown"),
        "nl_transport_probe_status": transport_probe.get("status", "unknown"),
        "nl_transport_probe_ok_count": f"{transport_probe.get('ok_count', 'unknown')}/{transport_probe.get('port_count', 'unknown')}",
        "nl_transport_uptime_status": uptime.get("status", "unknown"),
        "nl_transport_uptime_samples": uptime.get("sample_count", "unknown"),
        "nl_transport_uptime_bad_streak": uptime.get("consecutive_non_healthy", "unknown"),
        "secondary_probe_template_status": secondary.get("status", "unknown"),
        "readiness_audit_status": readiness.get("overall_status", "unknown"),
        "readiness_missing": readiness_summary.get("missing", "unknown"),
        "incident_timeline_event_count": timeline_count,
        "incident_timeline_latest_type": timeline_event.get("event_type", "unknown"),
        "incident_timeline_latest_snapshot": timeline_event.get("snapshot_name", "unknown"),
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def build_payload(snapshot_dir: Path, rows: list[dict[str, Any]], diagnostics_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/refresh_vpn_planning_reports.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": str(snapshot_dir),
        "ok": all(row.get("ok") for row in rows),
        "summary": build_summary(diagnostics_dir),
        "steps": rows,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# VPN Planning Refresh",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"snapshot: `{payload['snapshot']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"decision={summary.get('decision')}",
        f"decision_confidence={summary.get('decision_confidence')}",
        f"operator_status={summary.get('operator_status')}",
        f"boot_gap_watch_status={summary.get('boot_gap_watch_status')}",
        f"boot_gap_seconds={summary.get('boot_gap_seconds')}",
        f"provider_packet_type={summary.get('provider_packet_type')}",
        f"provider_packet_stale={summary.get('provider_packet_stale')}",
        f"provider_packet_snapshot_age_seconds={summary.get('provider_packet_snapshot_age_seconds')}",
        f"blocking_history_trend={summary.get('blocking_history_trend')}",
        f"blocking_history_snapshot_count={summary.get('blocking_history_snapshot_count')}",
        f"manual_failover_status={summary.get('manual_failover_status')}",
        f"manual_failover_readiness_status={summary.get('manual_failover_readiness_status')}",
        f"manual_failover_probe_allowed={summary.get('manual_failover_probe_allowed')}",
        f"manual_failover_switch_allowed={summary.get('manual_failover_switch_allowed')}",
        f"secondary_candidate_score_status={summary.get('secondary_candidate_score_status')}",
        f"secondary_candidate_viable_count={summary.get('secondary_candidate_viable_count')}",
        f"secondary_exit_requirements_status={summary.get('secondary_exit_requirements_status')}",
        f"secondary_exit_requirements_missing={summary.get('secondary_exit_requirements_missing')}",
        f"local_diagnostic_environment_status={summary.get('local_diagnostic_environment_status')}",
        f"local_root_status={summary.get('local_root_status')}",
        f"local_tmpdir_writable={summary.get('local_tmpdir_writable')}",
        f"local_recommended_tmpdir_prefix={summary.get('local_recommended_tmpdir_prefix')}",
        f"local_root_cleanup_plan_status={summary.get('local_root_cleanup_plan_status')}",
        f"local_root_cleanup_estimated_reclaim_gib={summary.get('local_root_cleanup_estimated_reclaim_gib')}",
        f"local_root_cleanup_execute_allowed={summary.get('local_root_cleanup_execute_allowed')}",
        f"nl_transport_probe_status={summary.get('nl_transport_probe_status')}",
        f"nl_transport_probe_ok_count={summary.get('nl_transport_probe_ok_count')}",
        f"nl_transport_uptime_status={summary.get('nl_transport_uptime_status')}",
        f"nl_transport_uptime_samples={summary.get('nl_transport_uptime_samples')}",
        f"nl_transport_uptime_bad_streak={summary.get('nl_transport_uptime_bad_streak')}",
        f"secondary_probe_template_status={summary.get('secondary_probe_template_status')}",
        f"readiness_audit_status={summary.get('readiness_audit_status')}",
        f"readiness_missing={summary.get('readiness_missing')}",
        f"incident_timeline_event_count={summary.get('incident_timeline_event_count')}",
        f"incident_timeline_latest_type={summary.get('incident_timeline_latest_type')}",
        f"incident_timeline_latest_snapshot={summary.get('incident_timeline_latest_snapshot')}",
        "nl_mutation_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Steps",
        "",
    ]
    for row in payload["steps"]:
        lines.extend(
            [
                f"### {row['id']}",
                "",
                "```text",
                f"ok={str(row.get('ok')).lower()}",
                f"exit_code={row.get('exit_code')}",
                "```",
                "",
            ]
        )
    lines.append("No NL or SPB writes were performed by this refresh.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh local VPN planning reports")
    parser.add_argument("--snapshot", help="Existing snapshot directory. Defaults to latest.")
    parser.add_argument("--snapshots-dir", default=str(SNAPSHOTS_DIR))
    parser.add_argument("--json-out", default=str(REFRESH_JSON))
    parser.add_argument("--markdown-out", default=str(REFRESH_MARKDOWN))
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot) if args.snapshot else latest_snapshot(Path(args.snapshots_dir))
    if snapshot_dir is None:
        raise SystemExit(f"no snapshots found under {args.snapshots_dir}")
    rows = run_plan(command_plan(snapshot_dir, include_readiness_audit=False), cwd=ROOT)
    payload = build_payload(snapshot_dir, rows, DIAGNOSTICS_DIR)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")

    rows.extend(run_plan([readiness_audit_command(snapshot_dir=snapshot_dir)], cwd=ROOT))
    rows.extend(run_plan([incident_timeline_command(snapshot_dir=snapshot_dir)], cwd=ROOT))
    payload = build_payload(snapshot_dir, rows, DIAGNOSTICS_DIR)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
