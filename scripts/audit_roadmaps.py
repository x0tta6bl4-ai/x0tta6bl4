#!/usr/bin/env python3
"""Audit roadmap and plan documents for status consistency."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


ROADMAP_KEYWORDS = (
    "roadmap",
    "plan",
    "todo",
    "backlog",
    "priorities",
    "next_steps",
)

EXPLICIT_DOCS = (
    "docs/roadmap.md",
    "docs/STATUS.md",
    "docs/05-operations/project-status-report.md",
    "docs/05-operations/deep-roadmap-analysis.md",
)

STATUS_PATTERNS = (
    re.compile(r"^\*\*(?:Статус|Status)\*\*:\s*(.+)$", re.IGNORECASE),
    re.compile(r"^##\s*Project Status:\s*(.+)$", re.IGNORECASE),
)

READY_PATTERNS = (
    re.compile(r"100%\s*(?:технической\s*)?готовности", re.IGNORECASE),
    re.compile(r"ready for global launch", re.IGNORECASE),
    re.compile(r"production ready", re.IGNORECASE),
    re.compile(r"fully operational", re.IGNORECASE),
    re.compile(r"ready for\s*\$?\d+\s*k\s*mrr", re.IGNORECASE),
)

CAVEAT_PATTERNS = (
    re.compile(r"release gate", re.IGNORECASE),
    re.compile(r"release readiness", re.IGNORECASE),
    re.compile(r"subsystem", re.IGNORECASE),
    re.compile(r"non-authoritative", re.IGNORECASE),
    re.compile(r"historical snapshot", re.IGNORECASE),
)

DONE_RE = re.compile(r"^\s*-\s*\[[xX]\]\s", re.MULTILINE)
OPEN_RE = re.compile(r"^\s*-\s*\[\s\]\s", re.MULTILINE)

MASTER_GATE = "plans/MASTER_100_READINESS_TODOS_2026-02-26.md"
CANONICAL_FILE = "plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md"
AUDIT_FILE = "plans/ROADMAP_AUDIT_2026-02-27.md"


@dataclass(frozen=True)
class AuditRow:
    path: str
    role: str
    done: int
    open_items: int
    status: str
    ready_claim: bool
    release_caveat: bool
    gate_conflict: bool


def _discover_files(root: Path) -> list[Path]:
    found: list[Path] = []

    plans_dir = root / "plans"
    if plans_dir.exists():
        for path in sorted(plans_dir.glob("*.md")):
            lower = path.name.lower()
            if any(keyword in lower for keyword in ROADMAP_KEYWORDS):
                found.append(path)

    for rel in EXPLICIT_DOCS:
        candidate = root / rel
        if candidate.exists():
            found.append(candidate)

    unique: dict[str, Path] = {}
    for item in found:
        unique[str(item.relative_to(root))] = item

    return [unique[key] for key in sorted(unique)]


def _extract_status(lines: Iterable[str]) -> str:
    for idx, line in enumerate(lines):
        if idx > 140:
            break
        stripped = line.strip()
        for pattern in STATUS_PATTERNS:
            match = pattern.search(stripped)
            if match:
                return match.group(1).strip()
    return "-"


def _role_for(path: str) -> str:
    if path == CANONICAL_FILE:
        return "canonical-roadmap"
    if path == AUDIT_FILE:
        return "roadmap-audit-report"
    if path == MASTER_GATE:
        return "release-gate"
    if path == "plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md":
        return "execution-backlog"
    if path == "docs/roadmap.md":
        return "docs-entrypoint"
    if path.startswith("docs/archive/"):
        return "historical"
    if path.startswith("docs/05-operations/project-status"):
        return "legacy-status-snapshot"
    if path.startswith("docs/05-operations/deep-roadmap-analysis"):
        return "legacy-analysis-snapshot"
    if path.startswith("docs/"):
        return "status-snapshot"
    if "grант" in path.lower() or "грант" in path.lower():
        return "program-plan"
    return "domain-plan"


def _audit_window(text: str) -> str:
    # We intentionally audit only the top section where global status is stated.
    return "\n".join(text.splitlines()[:220])


def _has_ready_claim(text: str) -> bool:
    window = _audit_window(text)
    return any(pattern.search(window) for pattern in READY_PATTERNS)


def _has_release_caveat(text: str) -> bool:
    window = _audit_window(text)
    return any(pattern.search(window) for pattern in CAVEAT_PATTERNS)


def _is_gate_conflict(path: str, ready_claim: bool, release_caveat: bool, release_gate_open: int) -> bool:
    if not ready_claim or release_gate_open == 0:
        return False
    if release_caveat:
        return False
    # The release gate itself is allowed to define reality; all other files
    # claiming global readiness are treated as conflicting signals.
    return path != MASTER_GATE


def _sanitize_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _build_report(rows: list[AuditRow], release_gate_open: int) -> str:
    conflicts = [row for row in rows if row.gate_conflict]
    today = date.today().isoformat()

    lines: list[str] = [
        "# Roadmap Consistency Audit",
        "",
        f"**Date:** {today}",
        f"**Release gate open items:** {release_gate_open}",
        f"**Files audited:** {len(rows)}",
        "",
        "## Summary",
        "",
        "- Single source of release truth: `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`.",
        "- Canonical roadmap entrypoint: `plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`.",
        f"- Files with readiness-claim conflict vs release gate: **{len(conflicts)}**.",
        "",
        "## File Matrix",
        "",
        "| File | Role | Done | Open | Status | Ready Claim | Release Caveat | Gate Conflict |",
        "|---|---|---:|---:|---|---|---|---|",
    ]

    for row in rows:
        lines.append(
            "| {path} | {role} | {done} | {open_items} | {status} | {ready} | {caveat} | {conflict} |".format(
                path=f"`{row.path}`",
                role=row.role,
                done=row.done,
                open_items=row.open_items,
                status=_sanitize_cell(row.status),
                ready="yes" if row.ready_claim else "no",
                caveat="yes" if row.release_caveat else "no",
                conflict="yes" if row.gate_conflict else "no",
            )
        )

    lines.extend(
        [
            "",
            "## Conflict List",
            "",
        ]
    )

    if conflicts:
        for row in conflicts:
            lines.append(
                f"- `{row.path}` claims high/global readiness while release gate still has {release_gate_open} open items."
            )
    else:
        lines.append("- No conflicts detected.")

    lines.extend(
        [
            "",
            "## Recommended Sync Actions",
            "",
            "- Keep `docs/roadmap.md` as redirect only.",
            "- In subsystem roadmaps, phrase readiness as subsystem-only and reference the release gate.",
            "- Mark old status reports as historical snapshots to avoid operational confusion.",
        ]
    )

    return "\n".join(lines) + "\n"


def run(root: Path) -> str:
    files = _discover_files(root)
    gate_path = root / MASTER_GATE
    gate_text = gate_path.read_text(encoding="utf-8", errors="ignore") if gate_path.exists() else ""
    release_gate_open = len(OPEN_RE.findall(gate_text))

    rows: list[AuditRow] = []
    for file_path in files:
        rel = str(file_path.relative_to(root))
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        status = _extract_status(text.splitlines())
        done = len(DONE_RE.findall(text))
        open_items = len(OPEN_RE.findall(text))
        ready_claim = _has_ready_claim(text)
        release_caveat = _has_release_caveat(text)
        gate_conflict = _is_gate_conflict(rel, ready_claim, release_caveat, release_gate_open)
        rows.append(
            AuditRow(
                path=rel,
                role=_role_for(rel),
                done=done,
                open_items=open_items,
                status=status,
                ready_claim=ready_claim,
                release_caveat=release_caveat,
                gate_conflict=gate_conflict,
            )
        )

    return _build_report(rows, release_gate_open)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit roadmap consistency across active project plans.")
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument("--out", help="Write markdown report to this path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report = run(root)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Wrote roadmap audit report: {out_path}")
        return 0

    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
