#!/usr/bin/env python3
"""Validate CI/CD stage contract for required pipeline stages."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CI_STAGE_PATTERNS: dict[str, str] = {
    "lint": r"-\s*name:\s*Lint with ruff\b",
    "type": r"-\s*name:\s*Type check with mypy\b",
    "unit": r"-\s*name:\s*Test with pytest\b",
    "integration": r"^\s*spire-integration:\s*$",
}

SMOKE_STAGE_PATTERN = r"-\s*name:\s*Run golden smoke \(quick\)"


def _find_stage_positions(text: str, patterns: dict[str, str]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for stage, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            positions[stage] = match.start()
    return positions


def validate_ci_stage_contract(ci_text: str) -> list[str]:
    errors: list[str] = []
    positions = _find_stage_positions(ci_text, CI_STAGE_PATTERNS)

    missing = [stage for stage in CI_STAGE_PATTERNS if stage not in positions]
    if missing:
        errors.append(f"Missing CI stages: {', '.join(missing)}")
        return errors

    ordered = ["lint", "type", "unit", "integration"]
    for prev, current in zip(ordered, ordered[1:]):
        if positions[prev] >= positions[current]:
            errors.append(
                f"Stage order violation: '{prev}' must appear before '{current}'"
            )
    return errors


def validate_smoke_stage_contract(smoke_text: str) -> list[str]:
    if re.search(SMOKE_STAGE_PATTERN, smoke_text, flags=re.IGNORECASE | re.MULTILINE):
        return []
    return ["Missing smoke stage: Run golden smoke (quick)"]


def run_contract_checks(ci_path: Path, smoke_path: Path) -> list[str]:
    errors: list[str] = []
    ci_text = ci_path.read_text(encoding="utf-8")
    smoke_text = smoke_path.read_text(encoding="utf-8")
    errors.extend(validate_ci_stage_contract(ci_text))
    errors.extend(validate_smoke_stage_contract(smoke_text))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check CI/CD stage contract: lint -> type -> unit -> integration + smoke."
    )
    parser.add_argument(
        "--ci-workflow",
        default=".github/workflows/ci.yml",
        help="Path to CI workflow file.",
    )
    parser.add_argument(
        "--smoke-workflow",
        default=".github/workflows/golden-smoke-premerge.yml",
        help="Path to golden smoke workflow file.",
    )
    args = parser.parse_args()

    ci_path = Path(args.ci_workflow)
    smoke_path = Path(args.smoke_workflow)

    missing_files = [str(path) for path in (ci_path, smoke_path) if not path.exists()]
    if missing_files:
        for path in missing_files:
            print(f"Missing workflow file: {path}")
        return 2

    errors = run_contract_checks(ci_path, smoke_path)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        "Pipeline stage contract passed: lint -> type -> unit -> integration + smoke"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
