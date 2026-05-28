#!/usr/bin/env python3
"""Build a local root-cleanup approval packet without deleting anything.

The packet turns the cleanup plan into an operator-review checklist. It does
not run cleanup commands, does not use sudo, does not connect to NL/SPB, and
does not mutate local or remote VPN state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_LOCAL_ENV = DIAGNOSTICS_DIR / "local-diagnostic-environment-2026-05-28.json"
DEFAULT_CLEANUP_PLAN = DIAGNOSTICS_DIR / "local-root-cleanup-plan-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "local-root-cleanup-approval-packet-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "local-root-cleanup-approval-packet-2026-05-28.md"

LOW_RISK_IDS = {"APT-CACHE-01"}
MEDIUM_STANDARD_IDS = {"JOURNAL-01"}
MANUAL_REVIEW_IDS = {"TMP-ANTIGRAVITY-01", "TMP-ANTIGRAVITY-02", "VARTMP-01"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def flag_is_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def candidate_by_id(cleanup_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = cleanup_plan.get("candidates")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


def choose_review_order(cleanup_plan: dict[str, Any]) -> list[str]:
    by_id = candidate_by_id(cleanup_plan)
    ordered: list[str] = []
    for candidate_id in ["APT-CACHE-01", "JOURNAL-01", "TMP-ANTIGRAVITY-01", "TMP-ANTIGRAVITY-02", "VARTMP-01"]:
        row = by_id.get(candidate_id) or {}
        if row.get("exists") is True:
            ordered.append(candidate_id)
    if ordered:
        return ordered
    raw_order = cleanup_plan.get("review_order")
    return [str(value) for value in raw_order] if isinstance(raw_order, list) else []


def command_row(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "missing")
    if candidate_id in LOW_RISK_IDS:
        approval_level = "single_command_approval"
    elif candidate_id in MEDIUM_STANDARD_IDS:
        approval_level = "confirm_log_retention_approval"
    else:
        approval_level = "manual_path_review_required"
    return {
        "id": candidate_id,
        "path": candidate.get("path", "missing"),
        "size_gib": candidate.get("size_gib", 0.0),
        "risk": candidate.get("risk", "missing"),
        "approval_level": approval_level,
        "command_preview": candidate.get("command_preview", "missing"),
        "may_execute_after_approval": False,
    }


def build_payload(*, local_env: dict[str, Any], cleanup_plan: dict[str, Any]) -> dict[str, Any]:
    env_summary = local_env.get("summary") or {}
    plan_summary = cleanup_plan.get("summary") or {}
    by_id = candidate_by_id(cleanup_plan)
    review_order = choose_review_order(cleanup_plan)
    command_previews = [command_row(by_id[candidate_id]) for candidate_id in review_order if candidate_id in by_id]
    safe = all(
        [
            flag_is_false(cleanup_plan, "cleanup_execute_allowed"),
            flag_is_false(cleanup_plan, "nl_mutation_allowed"),
            flag_is_false(cleanup_plan, "spb_fallback_allowed"),
            flag_is_false(cleanup_plan, "automatic_failover_allowed"),
            flag_is_false(local_env, "nl_mutation_allowed"),
            flag_is_false(local_env, "spb_fallback_allowed"),
            flag_is_false(local_env, "automatic_failover_allowed"),
            plan_summary.get("cleanup_execute_allowed") is False,
            plan_summary.get("nl_write_allowed") is False,
            plan_summary.get("spb_fallback_allowed") is False,
            plan_summary.get("automatic_failover_allowed") is False,
            env_summary.get("diagnostic_tmpdir_writable") is True,
        ]
    )
    existing_count = int(plan_summary.get("existing_candidate_count") or 0)
    cleanup_required = env_summary.get("cleanup_required") is True
    if not safe:
        status = "cleanup_approval_packet_unsafe_flags"
    elif cleanup_plan.get("status") == "no_cleanup_needed":
        status = "cleanup_approval_packet_no_cleanup_needed"
    elif cleanup_required and existing_count > 0 and command_previews:
        status = "cleanup_approval_packet_ready"
    elif cleanup_required:
        status = "cleanup_approval_packet_no_candidates"
    else:
        status = "cleanup_approval_packet_watch_only"

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_local_root_cleanup_approval_packet.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": safe,
        "summary": {
            "root_status": env_summary.get("root_status", "missing"),
            "root_free_gib": env_summary.get("root_free_gib", "missing"),
            "diagnostic_tmpdir": env_summary.get("diagnostic_tmpdir", "missing"),
            "diagnostic_tmpdir_writable": env_summary.get("diagnostic_tmpdir_writable", "missing"),
            "cleanup_plan_status": cleanup_plan.get("status", "missing"),
            "existing_candidate_count": existing_count,
            "estimated_reclaim_gib": plan_summary.get("estimated_reclaim_gib", "missing"),
            "first_review_id": review_order[0] if review_order else "none",
            "command_preview_count": len(command_previews),
            "approval_required": status == "cleanup_approval_packet_ready",
            "commands_executed": 0,
            "cleanup_execute_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "precheck_commands": [
            "df -h / /tmp /mnt/projects",
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_local_diagnostic_environment.py",
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/plan_local_root_cleanup.py",
        ],
        "command_previews": command_previews,
        "postcheck_commands": [
            "df -h / /tmp /mnt/projects",
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_local_diagnostic_environment.py",
            "TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T021824Z",
        ],
        "execution_rules": [
            "Do not execute any command preview without separate local cleanup approval.",
            "Prefer APT-CACHE-01 before manual rm -rf candidates.",
            "Review /tmp/antigravity_restore* contents before approving deletion.",
            "Keep TMPDIR=/mnt/projects/.tmp until root free space is no longer critical.",
            "This packet does not permit NL writes or SPB fallback.",
        ],
        "mutation_allowed": False,
        "cleanup_execute_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Root Cleanup Approval Packet",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"root_status={summary.get('root_status')}",
        f"root_free_gib={summary.get('root_free_gib')}",
        f"diagnostic_tmpdir={summary.get('diagnostic_tmpdir')}",
        f"diagnostic_tmpdir_writable={str(summary.get('diagnostic_tmpdir_writable')).lower()}",
        f"cleanup_plan_status={summary.get('cleanup_plan_status')}",
        f"existing_candidate_count={summary.get('existing_candidate_count')}",
        f"estimated_reclaim_gib={summary.get('estimated_reclaim_gib')}",
        f"first_review_id={summary.get('first_review_id')}",
        f"command_preview_count={summary.get('command_preview_count')}",
        f"approval_required={str(summary.get('approval_required')).lower()}",
        f"commands_executed={summary.get('commands_executed')}",
        "cleanup_execute_allowed=false",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Precheck Commands",
        "",
        "```bash",
    ]
    lines.extend(payload["precheck_commands"])
    lines.extend(["```", "", "## Command Previews", ""])
    lines.extend(
        [
            "| ID | Size GiB | Risk | Approval Level | May Execute Now | Command Preview |",
            "|---|---:|---|---|---:|---|",
        ]
    )
    for row in payload["command_previews"]:
        lines.append(
            "| "
            f"`{row['id']}` | "
            f"`{row['size_gib']}` | "
            f"`{row['risk']}` | "
            f"`{row['approval_level']}` | "
            f"`{str(row['may_execute_after_approval']).lower()}` | "
            f"`{row['command_preview']}` |"
        )
    lines.extend(["", "## Postcheck Commands", "", "```bash"])
    lines.extend(payload["postcheck_commands"])
    lines.extend(["```", "", "## Execution Rules", ""])
    lines.extend(f"- {value}" for value in payload["execution_rules"])
    lines.extend(["", "No cleanup, NL writes, or SPB fallback were performed by this approval packet."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local root cleanup approval packet")
    parser.add_argument("--local-env", default=str(DEFAULT_LOCAL_ENV))
    parser.add_argument("--cleanup-plan", default=str(DEFAULT_CLEANUP_PLAN))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(local_env=read_json(Path(args.local_env)), cleanup_plan=read_json(Path(args.cleanup_plan)))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
