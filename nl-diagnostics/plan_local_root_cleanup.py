#!/usr/bin/env python3
"""Build a local root-disk cleanup plan without deleting anything.

The plan is evidence only. It estimates reclaimable space and prints commands
that require separate local approval before execution.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_LOCAL_ENV = DIAGNOSTICS_DIR / "local-diagnostic-environment-2026-05-28.json"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "local-root-cleanup-plan-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "local-root-cleanup-plan-2026-05-28.md"

MIN_TARGET_FREE_GIB = 2.0


def bytes_to_gib(value: int) -> float:
    return round(value / (1024**3), 2)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def cleanup_candidate(
    *,
    candidate_id: str,
    path: str,
    title: str,
    risk: str,
    action: str,
    command_preview: str,
    approval: str,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "path": path,
        "title": title,
        "risk": risk,
        "action": action,
        "command_preview": command_preview,
        "approval": approval,
    }


def default_candidates() -> list[dict[str, Any]]:
    return [
        cleanup_candidate(
            candidate_id="TMP-ANTIGRAVITY-01",
            path="/tmp/antigravity_restore",
            title="Old Antigravity restore directory",
            risk="medium_manual_review",
            action="manual_review_before_delete",
            command_preview="sudo rm -rf /tmp/antigravity_restore",
            approval="separate local cleanup approval after reviewing directory contents",
        ),
        cleanup_candidate(
            candidate_id="TMP-ANTIGRAVITY-02",
            path="/tmp/antigravity_restore_correct",
            title="Old Antigravity restore correction directory",
            risk="medium_manual_review",
            action="manual_review_before_delete",
            command_preview="sudo rm -rf /tmp/antigravity_restore_correct",
            approval="separate local cleanup approval after reviewing directory contents",
        ),
        cleanup_candidate(
            candidate_id="APT-CACHE-01",
            path="/var/cache/apt/archives",
            title="APT package archive cache",
            risk="low_standard_cache",
            action="command_requires_approval",
            command_preview="sudo apt-get clean",
            approval="separate local cleanup approval",
        ),
        cleanup_candidate(
            candidate_id="JOURNAL-01",
            path="/var/log/journal",
            title="Systemd persistent journal",
            risk="medium_keep_recent_logs",
            action="command_requires_approval",
            command_preview="sudo journalctl --vacuum-size=500M",
            approval="separate local cleanup approval; keep recent logs",
        ),
        cleanup_candidate(
            candidate_id="VARTMP-01",
            path="/var/tmp",
            title="Persistent temporary files",
            risk="high_manual_review",
            action="manual_review_before_delete",
            command_preview="sudo find /var/tmp -mindepth 1 -maxdepth 1 -mtime +7 -print",
            approval="review printed paths first; delete only explicitly approved items",
        ),
    ]


def measure_path(path: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "size_bytes": 0,
        "size_gib": 0.0,
        "error_count": 0,
        "errors": [],
    }
    if not row["exists"]:
        return row
    try:
        if path.is_file() or path.is_symlink():
            size = path.lstat().st_size
            row["size_bytes"] = size
            row["size_gib"] = bytes_to_gib(size)
            return row
        total = 0
        errors: list[str] = []

        def onerror(exc: OSError) -> None:
            errors.append(str(exc))

        for dirpath, dirnames, filenames in os.walk(path, onerror=onerror, followlinks=False):
            for name in dirnames + filenames:
                child = Path(dirpath) / name
                try:
                    total += child.lstat().st_size
                except OSError as exc:
                    errors.append(str(exc))
        row["size_bytes"] = total
        row["size_gib"] = bytes_to_gib(total)
        row["error_count"] = len(errors)
        row["errors"] = errors[:5]
    except OSError as exc:
        row["error_count"] = 1
        row["errors"] = [str(exc)]
    return row


def inspect_candidates(
    candidates: list[dict[str, Any]],
    size_provider: Callable[[Path], dict[str, Any]] = measure_path,
) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        measured = size_provider(Path(str(candidate["path"])))
        rows.append({**candidate, **measured})
    return rows


def choose_status(local_env: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    summary = local_env.get("summary") or {}
    root_status = str(summary.get("root_status") or "missing")
    total_gib = sum(float(row.get("size_gib") or 0.0) for row in candidates if row.get("exists") is True)
    if root_status in {"ok", "watch_high_usage"} and summary.get("root_free_gib") not in {0, 0.0, "0.0"}:
        return "no_cleanup_needed"
    if root_status == "missing":
        return "missing_local_environment"
    if total_gib >= MIN_TARGET_FREE_GIB:
        return "manual_cleanup_plan_ready"
    if total_gib > 0:
        return "manual_cleanup_plan_low_reclaim"
    return "manual_cleanup_plan_no_candidates"


def build_payload(
    local_env: dict[str, Any],
    *,
    candidate_provider: Callable[[], list[dict[str, Any]]] = default_candidates,
    size_provider: Callable[[Path], dict[str, Any]] = measure_path,
) -> dict[str, Any]:
    candidates = inspect_candidates(candidate_provider(), size_provider)
    existing = [row for row in candidates if row.get("exists") is True]
    review_order = sorted(existing, key=lambda row: float(row.get("size_gib") or 0.0), reverse=True)
    total_gib = round(sum(float(row.get("size_gib") or 0.0) for row in existing), 2)
    status = choose_status(local_env, candidates)
    root_summary = local_env.get("summary") or {}

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/plan_local_root_cleanup.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status != "missing_local_environment",
        "summary": {
            "root_status": root_summary.get("root_status", "missing"),
            "root_free_gib": root_summary.get("root_free_gib", "missing"),
            "candidate_count": len(candidates),
            "existing_candidate_count": len(existing),
            "estimated_reclaim_gib": total_gib,
            "min_target_free_gib": MIN_TARGET_FREE_GIB,
            "top_candidate_id": review_order[0]["id"] if review_order else "none",
            "top_candidate_size_gib": review_order[0].get("size_gib", 0.0) if review_order else 0.0,
            "cleanup_execute_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidates": candidates,
        "review_order": [row["id"] for row in review_order],
        "execution_rules": [
            "This report does not delete files.",
            "Run command previews only after separate local cleanup approval.",
            "Review /tmp/antigravity_restore* contents before any rm -rf command.",
            "Keep using TMPDIR=/mnt/projects/.tmp until root has free space again.",
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
        "# Local Root Cleanup Plan",
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
        f"existing_candidate_count={summary.get('existing_candidate_count')}",
        f"estimated_reclaim_gib={summary.get('estimated_reclaim_gib')}",
        f"top_candidate_id={summary.get('top_candidate_id')}",
        f"top_candidate_size_gib={summary.get('top_candidate_size_gib')}",
        "cleanup_execute_allowed=false",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Review Order",
        "",
    ]
    for candidate_id in payload["review_order"]:
        lines.append(f"- `{candidate_id}`")

    lines.extend(
        [
            "",
            "## Candidates",
            "",
            "| ID | Exists | Size GiB | Risk | Action | Command Preview |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    for row in payload["candidates"]:
        lines.append(
            f"| `{row['id']}` | {str(row.get('exists')).lower()} | {row.get('size_gib')} | "
            f"`{row.get('risk')}` | `{row.get('action')}` | `{row.get('command_preview')}` |"
        )

    lines.extend(["", "## Execution Rules", ""])
    lines.extend(f"- {rule}" for rule in payload["execution_rules"])
    lines.append("")
    lines.append("No cleanup, NL writes, or SPB fallback were performed by this plan.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan local root cleanup without deleting files")
    parser.add_argument("--local-env", default=str(DEFAULT_LOCAL_ENV))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(read_json(Path(args.local_env)))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
