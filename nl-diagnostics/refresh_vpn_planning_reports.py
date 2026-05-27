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
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
SNAPSHOTS_DIR = DIAGNOSTICS_DIR / "snapshots"
REFRESH_JSON = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.json"
REFRESH_MARKDOWN = DIAGNOSTICS_DIR / "vpn-planning-refresh-2026-05-28.md"


def latest_snapshot(snapshots_dir: Path) -> Path | None:
    if not snapshots_dir.is_dir():
        return None
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def readiness_audit_command(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    return {
        "id": "readiness_audit",
        "command": [
            "python3",
            str(diagnostics_dir / "audit_vpn_plan_readiness.py"),
            "--json-out",
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json"),
            "--markdown-out",
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.md"),
        ],
        "outputs": [
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json"),
            str(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.md"),
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
        plan.append(readiness_audit_command(diagnostics_dir))
    return plan


def command_is_local_only(command: list[str]) -> bool:
    forbidden = {"ssh", "scp", "rsync", "systemctl", "sudo"}
    return not any(Path(part).name in forbidden for part in command)


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
        completed = runner(command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
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


def build_summary(diagnostics_dir: Path) -> dict[str, Any]:
    decision = read_json(diagnostics_dir / "current-vpn-decision-2026-05-28.json").get("decision") or {}
    history = read_json(diagnostics_dir / "blocking-probe-history-2026-05-28.json").get("summary") or {}
    backlog = read_json(diagnostics_dir / "vpn-improvement-backlog-2026-05-28.json").get("summary") or {}
    failover = read_json(diagnostics_dir / "manual-failover-plan-2026-05-28.json")
    transport_probe = read_json(diagnostics_dir / "nl-transport-probe-2026-05-28.json")
    secondary = read_json(diagnostics_dir / "secondary-exit-probe-template-2026-05-28.json")
    operator = read_json(diagnostics_dir / "vpn-operator-card-2026-05-28.json").get("operator") or {}
    readiness = read_json(diagnostics_dir / "vpn-plan-readiness-audit-2026-05-28.json")
    readiness_summary = readiness.get("summary") or {}
    return {
        "decision": decision.get("decision", "unknown"),
        "decision_confidence": decision.get("confidence", "unknown"),
        "operator_status": operator.get("operator_status", "unknown"),
        "blocking_history_trend": history.get("trend", "unknown"),
        "blocking_history_snapshot_count": history.get("snapshot_count", 0),
        "backlog_decision": backlog.get("decision", "unknown"),
        "manual_failover_status": failover.get("status", "unknown"),
        "nl_transport_probe_status": transport_probe.get("status", "unknown"),
        "nl_transport_probe_ok_count": f"{transport_probe.get('ok_count', 'unknown')}/{transport_probe.get('port_count', 'unknown')}",
        "secondary_probe_template_status": secondary.get("status", "unknown"),
        "readiness_audit_status": readiness.get("overall_status", "unknown"),
        "readiness_missing": readiness_summary.get("missing", "unknown"),
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
        f"blocking_history_trend={summary.get('blocking_history_trend')}",
        f"blocking_history_snapshot_count={summary.get('blocking_history_snapshot_count')}",
        f"manual_failover_status={summary.get('manual_failover_status')}",
        f"nl_transport_probe_status={summary.get('nl_transport_probe_status')}",
        f"nl_transport_probe_ok_count={summary.get('nl_transport_probe_ok_count')}",
        f"secondary_probe_template_status={summary.get('secondary_probe_template_status')}",
        f"readiness_audit_status={summary.get('readiness_audit_status')}",
        f"readiness_missing={summary.get('readiness_missing')}",
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

    rows.extend(run_plan([readiness_audit_command()], cwd=ROOT))
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
