#!/usr/bin/env python3
"""Fail CI when enterprise workflow hardening invariants are violated."""

from __future__ import annotations

import re
import sys
from pathlib import Path


RELEASE_WORKFLOW = Path(".github/workflows/release.yml")
CI_WORKFLOW = Path(".github/workflows/ci.yml")


def _find_step_block(workflow_text: str, step_name: str) -> str | None:
    pattern = re.compile(
        rf"(?ms)^\s*-\s+name:\s*{re.escape(step_name)}\s*\n(?P<body>.*?)(?=^\s*-\s+name:|\Z)"
    )
    match = pattern.search(workflow_text)
    if not match:
        return None
    return match.group("body")


def validate_release_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []

    if "continue-on-error: true" in workflow_text:
        errors.append("release.yml: `continue-on-error: true` is forbidden for enterprise release flow")

    if "python scripts/sync_version.py --version" not in workflow_text:
        errors.append("release.yml: missing centralized version sync command")
    if "python scripts/validate_version_contract.py" not in workflow_text:
        errors.append("release.yml: missing version contract validation command")

    pypi_step = _find_step_block(workflow_text, "Publish to PyPI")
    if pypi_step is None:
        errors.append("release.yml: missing `Publish to PyPI` step")
    elif not re.search(
        r"^\s*if:\s*\$\{\{\s*secrets\.PYPI_API_TOKEN\s*!=\s*''\s*\}\}",
        pypi_step,
        re.MULTILINE,
    ):
        errors.append(
            "release.yml: `Publish to PyPI` must be guarded by `if: ${{ secrets.PYPI_API_TOKEN != '' }}`"
        )

    docker_guard_pattern = re.compile(
        r"^\s*if:\s*\$\{\{\s*secrets\.DOCKER_USERNAME\s*!=\s*''\s*&&\s*secrets\.DOCKER_PASSWORD\s*!=\s*''\s*\}\}",
        re.MULTILINE,
    )
    for step_name in ("Login to Docker Hub", "Build and push Docker image"):
        step_block = _find_step_block(workflow_text, step_name)
        if step_block is None:
            errors.append(f"release.yml: missing `{step_name}` step")
            continue
        if not docker_guard_pattern.search(step_block):
            errors.append(f"release.yml: `{step_name}` must be guarded by both Docker secrets")

    push_step = _find_step_block(workflow_text, "Build and push Docker image")
    if push_step is not None and not re.search(r"^\s*push:\s*true\s*$", push_step, re.MULTILINE):
        errors.append("release.yml: `Build and push Docker image` must set `push: true`")

    local_build_step = _find_step_block(workflow_text, "Build Docker image (push skipped, no credentials)")
    if local_build_step is None:
        errors.append("release.yml: missing fallback local Docker build step")
    else:
        if not re.search(
            r"^\s*if:\s*\$\{\{\s*secrets\.DOCKER_USERNAME\s*==\s*''\s*\|\|\s*secrets\.DOCKER_PASSWORD\s*==\s*''\s*\}\}",
            local_build_step,
            re.MULTILINE,
        ):
            errors.append("release.yml: fallback local Docker build step must be guarded by missing Docker secrets")
        if not re.search(r"^\s*push:\s*false\s*$", local_build_step, re.MULTILINE):
            errors.append("release.yml: fallback local Docker build step must set `push: false`")

    return errors


def validate_ci_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []
    required_commands = (
        "python scripts/validate_runtime_contracts.py",
        "python scripts/validate_version_contract.py",
        "python scripts/validate_enterprise_workflows.py",
    )

    for command in required_commands:
        if command not in workflow_text:
            errors.append(f"ci.yml: missing required command `{command}`")
    return errors


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    release_text = _read_text(RELEASE_WORKFLOW)
    if release_text is None:
        errors.append(f"missing workflow file: {RELEASE_WORKFLOW}")
    else:
        errors.extend(validate_release_workflow_text(release_text))

    ci_text = _read_text(CI_WORKFLOW)
    if ci_text is None:
        errors.append(f"missing workflow file: {CI_WORKFLOW}")
    else:
        errors.extend(validate_ci_workflow_text(ci_text))

    if errors:
        print("Enterprise workflow policy violations:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Enterprise workflow policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
