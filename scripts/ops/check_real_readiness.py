#!/usr/bin/env python3
"""Fail-closed local real-readiness gate.

This gate is intentionally conservative: a READY result means the local
repository state, command checks, and current cross-plane evidence context are
consistent enough for review. It does not prove production readiness, customer
traffic, external DPI bypass, settlement finality, or SLOs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence


SCHEMA = "x0tta6bl4.real_readiness.v1"
DEFAULT_CROSS_PLANE_MAP = Path("docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json")
DEFAULT_ACTIVE_GOAL_AUDIT = Path("docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md")
DEFAULT_OUTPUT_JSON = Path(".tmp/validation-shards/real-readiness-current.json")
DEFAULT_OUTPUT_MD = Path(".tmp/validation-shards/real-readiness-current.md")

REQUIRED_PLANES = {
    "control_plane",
    "data_plane",
    "economy_plane",
    "evidence_plane",
    "trust_plane",
}

COMMAND_CHECKS: tuple[tuple[str, ...], ...] = (
    ("python3", "scripts/check_env_security_defaults.py"),
    ("python3", "scripts/check_requirements_lock_sync.py"),
    (
        "python3",
        "-m",
        "pytest",
        "--confcutdir=tests/unit/security",
        "tests/unit/security/test_dependency_security_pins_unit.py",
        "-q",
        "-o",
        "addopts=",
    ),
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


Runner = Callable[[Sequence[str], Mapping[str, str] | None, int], CommandResult]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_runner(
    args: Sequence[str],
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        cwd=None,
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _load_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _status_name(line: str) -> str:
    code = line[:2]
    if code == "??":
        return "untracked"
    if "D" in code:
        return "deleted"
    if "M" in code:
        return "modified"
    if "A" in code:
        return "added"
    if "R" in code:
        return "renamed"
    if "C" in code:
        return "copied"
    if "U" in code:
        return "unmerged"
    return "other"


def _path_from_status_line(line: str) -> str:
    if line.startswith("?? "):
        return line[3:]
    path = line[3:] if len(line) > 3 else line
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1]
    return path.strip()


def _summarize_git_dirty_lines(dirty_lines: Sequence[str], *, limit: int = 12) -> str:
    status_counts: dict[str, int] = {}
    top_paths: dict[str, int] = {}
    shown = [line.strip() for line in dirty_lines[:limit]]

    for line in dirty_lines:
        status = _status_name(line)
        status_counts[status] = status_counts.get(status, 0) + 1
        path = _path_from_status_line(line)
        top = path.split("/", 1)[0] if path else "."
        top_paths[top] = top_paths.get(top, 0) + 1

    status_summary = ", ".join(
        f"{name}={count}" for name, count in sorted(status_counts.items())
    )
    top_summary = ", ".join(
        f"{name}={count}"
        for name, count in sorted(top_paths.items(), key=lambda item: (-item[1], item[0]))[:8]
    )
    details = [
        f"status_counts: {status_summary or 'none'}",
        f"top_paths: {top_summary or 'none'}",
    ]
    if shown:
        remaining = max(0, len(dirty_lines) - len(shown))
        dirty_summary = "dirty_paths=" + ", ".join(shown)
        if remaining:
            dirty_summary += f", ... +{remaining} more"
        details.append(dirty_summary)
    return "; ".join(details)


def check_git_state(root: Path, runner: Runner = _default_runner) -> list[CheckResult]:
    result = runner(("git", "status", "--porcelain"), None, 60)
    if result.returncode != 0:
        return [
            CheckResult(
                "git_worktree_clean",
                "FAIL",
                f"git status failed: {result.stderr.strip() or result.stdout.strip()}",
                "git status --porcelain",
            )
        ]

    dirty_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty_lines:
        return [
            CheckResult(
                "git_worktree_clean",
                "FAIL",
                (
                    f"Worktree has {len(dirty_lines)} uncommitted paths; "
                    f"{_summarize_git_dirty_lines(dirty_lines)}; "
                    "release readiness requires reviewed commits or a clean worktree"
                ),
                "git status --porcelain",
            )
        ]

    return [
        CheckResult(
            "git_worktree_clean",
            "PASS",
            "Worktree is clean",
            "git status --porcelain",
        )
    ]


def _extract_context(data: dict[str, object]) -> tuple[dict[str, object], str]:
    embedded = data.get("current_evidence_context")
    if isinstance(embedded, dict):
        return embedded, "generated_audit_wrapper"
    return data, "top_level_working_map"


def check_current_evidence_context(
    root: Path,
    *,
    map_path: Path = DEFAULT_CROSS_PLANE_MAP,
    audit_path: Path = DEFAULT_ACTIVE_GOAL_AUDIT,
) -> list[CheckResult]:
    absolute_map = root / map_path
    absolute_audit = root / audit_path

    if not absolute_map.exists():
        return [
            CheckResult(
                "current_evidence_context_present",
                "FAIL",
                f"Current cross-plane evidence map is missing: {map_path}",
                str(map_path),
            )
        ]

    data = _load_json(absolute_map)
    if data is None:
        return [
            CheckResult(
                "current_evidence_context_shape",
                "FAIL",
                "Current cross-plane evidence map is not valid JSON object",
                str(map_path),
            )
        ]

    context, source_format = _extract_context(data)
    status = context.get("status")
    plane_ids = set(_as_string_list(context.get("plane_ids")))
    if not plane_ids and isinstance(context.get("planes"), list):
        plane_ids = {
            str(item.get("id"))
            for item in context["planes"]  # type: ignore[index]
            if isinstance(item, dict) and item.get("id")
        }
    elif not plane_ids and isinstance(context.get("planes"), dict):
        plane_ids = set(context.get("planes", {}).keys())

    open_gap_ids = _as_string_list(context.get("open_gap_ids"))
    if not open_gap_ids and isinstance(context.get("current_gaps"), list):
        open_gap_ids = [
            str(item.get("id"))
            for item in context["current_gaps"]  # type: ignore[index]
            if isinstance(item, dict)
            and item.get("id")
            and item.get("blocking_status") not in {"tracked_residual_risk_with_current_contract_checks"}
        ]

    next_action_ids = _as_string_list(context.get("next_action_ids"))
    if not next_action_ids and isinstance(context.get("next_actions"), list):
        next_action_ids = [
            str(item.get("id"))
            for item in context["next_actions"]  # type: ignore[index]
            if isinstance(item, dict) and item.get("id")
        ]

    failures: list[str] = []
    if status != "working_map_not_production_completion_proof":
        failures.append(
            "status must be 'working_map_not_production_completion_proof', "
            f"got {status!r}"
        )
    missing_planes = sorted(REQUIRED_PLANES - plane_ids)
    if missing_planes:
        failures.append(f"missing required planes: {', '.join(missing_planes)}")
    if open_gap_ids:
        failures.append(f"open gaps remain: {', '.join(open_gap_ids)}")
    if next_action_ids:
        failures.append(f"next actions remain: {', '.join(next_action_ids)}")

    if failures:
        return [
            CheckResult(
                "current_evidence_context_shape",
                "FAIL",
                "; ".join(failures),
                str(map_path),
            )
        ]

    audit_note = "audit present" if absolute_audit.exists() else "audit missing"
    return [
        CheckResult(
            "current_evidence_context_clear",
            "PASS",
            (
                "Current cross-plane evidence context is clear; "
                f"source_format={source_format}; planes={len(plane_ids)}; {audit_note}"
            ),
            str(map_path),
        )
    ]


def check_command_contracts(root: Path, runner: Runner = _default_runner) -> list[CheckResult]:
    results: list[CheckResult] = []
    for command in COMMAND_CHECKS:
        result = runner(command, None, 300)
        check_id = "command_" + Path(command[1] if len(command) > 1 else command[0]).stem
        if result.returncode == 0:
            results.append(
                CheckResult(check_id, "PASS", "Command passed", " ".join(command))
            )
        else:
            output = (result.stderr or result.stdout).strip().splitlines()
            detail = output[-1] if output else f"exit_code={result.returncode}"
            results.append(CheckResult(check_id, "FAIL", detail, " ".join(command)))
    return results


def build_report(
    root: Path,
    *,
    runner: Runner = _default_runner,
    include_command_checks: bool = True,
    include_git_check: bool = True,
) -> dict[str, object]:
    checks: list[CheckResult] = []
    checks.extend(check_current_evidence_context(root))
    if include_command_checks:
        checks.extend(check_command_contracts(root, runner))
    if include_git_check:
        checks.extend(check_git_state(root, runner))

    blockers = [check for check in checks if check.status != "PASS"]
    ready = not blockers
    return {
        "schema": SCHEMA,
        "timestamp_utc": _utc_now(),
        "root": str(root),
        "decision": "REAL_READINESS_READY" if ready else "REAL_READINESS_BLOCKED",
        "ready": ready,
        "claim_boundary": (
            "REAL_READINESS_READY means local command checks, clean git state, and "
            "current cross-plane evidence context passed. It does not prove live "
            "customer traffic, external DPI bypass, payment settlement finality, "
            "production SLOs, or durable censorship resistance."
        ),
        "summary": {
            "checks_total": len(checks),
            "passed": len([check for check in checks if check.status == "PASS"]),
            "failures": len(blockers),
            "warnings": 0,
        },
        "blockers": [check.to_dict() for check in blockers],
        "checks": [check.to_dict() for check in checks],
    }


def _write_markdown(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Real Readiness",
        "",
        f"Decision: `{report['decision']}`",
        f"Ready: `{str(report['ready']).lower()}`",
        (
            "Summary: "
            f"{summary.get('passed')} passed / {summary.get('failures')} failed "
            f"({summary.get('checks_total')} checks)"
        ),
        "",
        "## Blockers",
        "",
    ]
    blockers = report["blockers"]
    if isinstance(blockers, list) and blockers:
        for blocker in blockers:
            if isinstance(blocker, dict):
                lines.append(f"- `{blocker.get('check_id')}`: {blocker.get('details')}")
    else:
        lines.append("- none")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--skip-command-checks", action="store_true")
    parser.add_argument("--skip-git-check", action="store_true")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--write-current", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    report = build_report(
        root,
        include_command_checks=not args.skip_command_checks,
        include_git_check=not args.skip_git_check,
    )

    output_json = DEFAULT_OUTPUT_JSON if args.write_current else args.output_json
    output_md = DEFAULT_OUTPUT_MD if args.write_current else args.output_md
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_md is not None:
        _write_markdown(output_md, report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif not report["ready"]:
        print(f"REAL_READINESS_BLOCKED: {report['summary']}")
    else:
        print("REAL_READINESS_READY")

    if args.require_ready and not report["ready"]:
        return 2
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
