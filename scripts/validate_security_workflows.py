#!/usr/bin/env python3
"""Fail CI when security workflow steps are configured as soft-fail."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


WORKFLOWS_DIR = Path(".github/workflows")
SECURITY_TOOLS = (
    "bandit",
    "safety",
    "pip-audit",
    "pip_audit",
    "trivy",
    "trufflehog",
    "snyk",
)
SECURITY_CONTEXT_MARKERS = ("security", "security scan", "security-scan")
CONTEXTUAL_TOOLS = ("cppcheck",)
SOFT_FAIL_PATTERNS = ("|| true", "|| echo")


def _is_security_step(job_name: str, step: dict[str, Any]) -> bool:
    job = str(job_name).lower()
    name = str(step.get("name", "")).lower()
    run = str(step.get("run", "")).lower()
    uses = str(step.get("uses", "")).lower()
    text = "\n".join((name, run, uses))

    if any(marker in text for marker in SECURITY_TOOLS):
        return True

    in_security_context = any(marker in "\n".join((job, name)) for marker in SECURITY_CONTEXT_MARKERS)
    if in_security_context and any(tool in text for tool in CONTEXTUAL_TOOLS):
        return True

    return False


def _validate_security_step(
    workflow: Path,
    job_name: str,
    step_index: int,
    step: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    step_name = str(step.get("name", "<unnamed step>"))
    step_ref = f"{workflow}:{job_name}:step#{step_index} ({step_name})"
    run = str(step.get("run", ""))
    run_lower = run.lower()
    uses = str(step.get("uses", "")).lower()
    security_context = any(marker in f"{job_name.lower()} {step_name.lower()}" for marker in SECURITY_CONTEXT_MARKERS)

    if step.get("continue-on-error") is True:
        errors.append(f"{step_ref}: security step must not use continue-on-error: true")

    run_has_security_tool = any(marker in run_lower for marker in SECURITY_TOOLS)
    run_has_contextual_tool = security_context and any(marker in run_lower for marker in CONTEXTUAL_TOOLS)
    if run_has_security_tool or run_has_contextual_tool:
        for pattern in SOFT_FAIL_PATTERNS:
            if pattern in run:
                errors.append(f"{step_ref}: run command contains disallowed soft-fail pattern `{pattern}`")
        if re.search(r"\bexit\s+0\b", run):
            errors.append(f"{step_ref}: run command contains `exit 0` in security step")

    if "aquasecurity/trivy-action" in uses:
        with_cfg = step.get("with") or {}
        exit_code = str(with_cfg.get("exit-code", "")).strip("'\"")
        if exit_code != "1":
            errors.append(f"{step_ref}: trivy-action must set `with.exit-code: '1'`")

    return errors


def main() -> int:
    if not WORKFLOWS_DIR.exists():
        print(f"ERROR: missing workflows directory: {WORKFLOWS_DIR}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        try:
            data = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover - defensive parsing path
            all_errors.append(f"{workflow}: unable to parse YAML: {exc}")
            continue

        jobs = data.get("jobs") or {}
        if not isinstance(jobs, dict):
            all_errors.append(f"{workflow}: `jobs` must be a mapping")
            continue

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps") or []
            if not isinstance(steps, list):
                continue

            for i, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                if not _is_security_step(str(job_name), step):
                    continue
                all_errors.extend(_validate_security_step(workflow, str(job_name), i, step))

    if all_errors:
        print("Security workflow policy violations:")
        for error in all_errors:
            print(f" - {error}")
        return 1

    print("Security workflow policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
