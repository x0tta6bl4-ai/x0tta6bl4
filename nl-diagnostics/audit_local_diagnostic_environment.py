#!/usr/bin/env python3
"""Audit the local host environment used for VPN diagnostics.

This script only inspects local disk state and a project-local temporary
directory. It does not connect to NL/SPB and does not delete files.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_TMPDIR = ROOT / ".tmp"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "local-diagnostic-environment-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "local-diagnostic-environment-2026-05-28.md"

CRITICAL_USED_PERCENT = 99.0
WATCH_USED_PERCENT = 90.0


def bytes_to_gib(value: int) -> float:
    return round(value / (1024**3), 2)


def usage_status(*, used_percent: float, free_bytes: int) -> str:
    if free_bytes <= 0 or used_percent >= CRITICAL_USED_PERCENT:
        return "critical_full"
    if used_percent >= WATCH_USED_PERCENT:
        return "watch_high_usage"
    return "ok"


def disk_row(path: Path, usage_provider: Callable[[Path], Any] = shutil.disk_usage) -> dict[str, Any]:
    try:
        usage = usage_provider(path)
    except OSError as exc:
        return {
            "path": str(path),
            "exists": path.exists(),
            "status": "missing",
            "error": str(exc),
        }
    total = int(usage.total)
    used = int(usage.used)
    free = int(usage.free)
    used_percent = round((used / total) * 100, 1) if total else 100.0
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": usage_status(used_percent=used_percent, free_bytes=free),
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "total_gib": bytes_to_gib(total),
        "used_gib": bytes_to_gib(used),
        "free_gib": bytes_to_gib(free),
        "used_percent": used_percent,
    }


def probe_tmpdir(tmpdir: Path) -> dict[str, Any]:
    result = {
        "path": str(tmpdir),
        "exists": tmpdir.exists(),
        "is_dir": tmpdir.is_dir(),
        "writable": False,
        "error": "",
    }
    if not result["exists"]:
        result["error"] = "tmpdir_missing"
        return result
    if not result["is_dir"]:
        result["error"] = "tmpdir_not_directory"
        return result
    try:
        with tempfile.NamedTemporaryFile(
            dir=tmpdir,
            prefix="vpn-diag-",
            suffix=".tmp",
            delete=True,
        ) as handle:
            handle.write(b"ok\n")
            handle.flush()
        result["writable"] = True
    except OSError as exc:
        result["error"] = str(exc)
    return result


def cleanup_candidates(tmp_root: Path = Path("/tmp")) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for name in ("antigravity_restore", "antigravity_restore_correct"):
        path = tmp_root / name
        candidates.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "action": "manual_review_before_delete",
            }
        )
    return candidates


def choose_status(rows: list[dict[str, Any]], tmpdir_probe: dict[str, Any]) -> str:
    if tmpdir_probe.get("writable") is not True:
        return "missing_writable_temp"
    statuses = {str(row.get("path")): str(row.get("status")) for row in rows}
    if statuses.get("/") == "critical_full" or statuses.get("/tmp") == "critical_full":
        return "watch_root_full_tmpdir_available"
    if any(row.get("status") == "watch_high_usage" for row in rows):
        return "watch_disk_pressure"
    if any(row.get("status") == "missing" for row in rows):
        return "missing_disk_evidence"
    return "ok"


def row_by_path(rows: list[dict[str, Any]], path: str) -> dict[str, Any]:
    for row in rows:
        if row.get("path") == path:
            return row
    return {}


def build_payload(
    *,
    paths: list[Path] | None = None,
    tmpdir: Path = DEFAULT_TMPDIR,
    usage_provider: Callable[[Path], Any] = shutil.disk_usage,
    tmpdir_probe_provider: Callable[[Path], dict[str, Any]] = probe_tmpdir,
    cleanup_provider: Callable[[], list[dict[str, Any]]] = cleanup_candidates,
) -> dict[str, Any]:
    checked_paths = paths or [Path("/"), Path("/tmp"), ROOT]
    rows = [disk_row(path, usage_provider) for path in checked_paths]
    tmpdir_probe = tmpdir_probe_provider(tmpdir)
    cleanup_rows = cleanup_provider()
    status = choose_status(rows, tmpdir_probe)
    root_row = row_by_path(rows, "/")
    tmp_row = row_by_path(rows, "/tmp")
    projects_row = row_by_path(rows, str(ROOT))
    cleanup_required = status in {
        "watch_root_full_tmpdir_available",
        "watch_disk_pressure",
        "missing_writable_temp",
    }

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/audit_local_diagnostic_environment.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "ok": status not in {"missing_writable_temp", "missing_disk_evidence"},
        "summary": {
            "root_status": root_row.get("status", "missing"),
            "root_used_percent": root_row.get("used_percent", "missing"),
            "root_free_gib": root_row.get("free_gib", "missing"),
            "tmp_status": tmp_row.get("status", "missing"),
            "projects_status": projects_row.get("status", "missing"),
            "projects_free_gib": projects_row.get("free_gib", "missing"),
            "diagnostic_tmpdir": str(tmpdir),
            "diagnostic_tmpdir_exists": tmpdir_probe.get("exists") is True,
            "diagnostic_tmpdir_writable": tmpdir_probe.get("writable") is True,
            "cleanup_required": cleanup_required,
            "recommended_tmpdir_prefix": f"TMPDIR={tmpdir}",
            "cleanup_candidate_count": sum(1 for row in cleanup_rows if row.get("exists") is True),
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "disk": rows,
        "tmpdir_probe": tmpdir_probe,
        "cleanup_candidates": cleanup_rows,
        "recommended_local_command_prefix": f"TMPDIR={tmpdir}",
        "operator_notes": [
            "Use TMPDIR=/mnt/projects/.tmp for local Python tests and report refreshes while / is full.",
            "Do not delete /tmp/antigravity_restore* without separate local cleanup approval.",
            "This audit performs no NL writes and does not use SPB.",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Diagnostic Environment Audit",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"root_status={summary.get('root_status')}",
        f"root_used_percent={summary.get('root_used_percent')}",
        f"root_free_gib={summary.get('root_free_gib')}",
        f"tmp_status={summary.get('tmp_status')}",
        f"projects_status={summary.get('projects_status')}",
        f"projects_free_gib={summary.get('projects_free_gib')}",
        f"diagnostic_tmpdir={summary.get('diagnostic_tmpdir')}",
        f"diagnostic_tmpdir_exists={str(summary.get('diagnostic_tmpdir_exists')).lower()}",
        f"diagnostic_tmpdir_writable={str(summary.get('diagnostic_tmpdir_writable')).lower()}",
        f"cleanup_required={str(summary.get('cleanup_required')).lower()}",
        f"recommended_tmpdir_prefix={summary.get('recommended_tmpdir_prefix')}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Disk",
        "",
        "| Path | Status | Used | Free GiB |",
        "|---|---|---:|---:|",
    ]
    for row in payload["disk"]:
        lines.append(
            f"| `{row.get('path')}` | `{row.get('status')}` | "
            f"{row.get('used_percent', 'missing')}% | {row.get('free_gib', 'missing')} |"
        )

    lines.extend(["", "## Cleanup Candidates", ""])
    for row in payload["cleanup_candidates"]:
        lines.append(
            f"- `{row.get('path')}` exists={str(row.get('exists')).lower()} "
            f"action={row.get('action')}"
        )

    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in payload["operator_notes"])
    lines.append("")
    lines.append("No NL or SPB writes were performed by this local environment audit.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local VPN diagnostic environment")
    parser.add_argument("--tmpdir", default=str(DEFAULT_TMPDIR))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload(tmpdir=Path(args.tmpdir))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
