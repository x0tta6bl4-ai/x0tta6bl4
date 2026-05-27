#!/usr/bin/env python3
"""Static duplicate guard for scripts/verify-v1.1.sh.

The verification entrypoint is intentionally large, so repeated smoke calls or
test paths are easy to add by accident. This guard fails before execution can
hide duplicate coverage or double-count a check.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_VERIFY_SCRIPT = "scripts/verify-v1.1.sh"
DEFAULT_REQUIRED_SMOKE_INVOCATIONS = (
    "run_ghost_pulse_artifact_chain_current_smoke_check",
)
DEFAULT_REQUIRED_PYTEST_ENTRIES = (
    "tests/unit/scripts/test_run_ghost_pulse_verification_suite.py",
    "tests/unit/scripts/test_verify_ghost_pulse_artifact_chain.py",
    "tests/unit/scripts/test_verify_ghost_pulse_rng_replay.py",
    "tests/unit/scripts/test_verify_ghost_pulse_verification_suite.py",
    "tests/unit/network/test_pulse_transport_replay_unit.py",
)

FUNCTION_DEF_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{")
SMOKE_INVOCATION_RE = re.compile(r"^\s*(run_[A-Za-z0-9_]+_smoke_check)\s*(?:#.*)?$")
PYTEST_ENTRY_RE = re.compile(r"^\s*(tests/[^\s\\]+\.py)\s*\\?\s*(?:#.*)?$")


def _duplicates(items: Iterable[Tuple[str, int]]) -> List[Dict[str, Any]]:
    by_name: Dict[str, List[int]] = defaultdict(list)
    for name, line in items:
        by_name[name].append(line)
    return [
        {"name": name, "lines": lines, "count": len(lines)}
        for name, lines in sorted(by_name.items())
        if len(lines) > 1
    ]


def _missing_required(
    required: Iterable[str],
    observed: Iterable[str],
) -> List[Dict[str, Any]]:
    observed_set = set(observed)
    return [
        {"name": name}
        for name in required
        if name not in observed_set
    ]


def build_report(
    path: Path,
    *,
    required_smoke_invocations: Iterable[str] = DEFAULT_REQUIRED_SMOKE_INVOCATIONS,
    required_pytest_entries: Iterable[str] = DEFAULT_REQUIRED_PYTEST_ENTRIES,
) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    function_defs: List[Tuple[str, int]] = []
    smoke_invocations: List[Tuple[str, int]] = []
    pytest_entries: List[Tuple[str, int]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        function_match = FUNCTION_DEF_RE.match(line)
        if function_match:
            function_defs.append((function_match.group(1), line_number))
            continue

        smoke_match = SMOKE_INVOCATION_RE.match(line)
        if smoke_match:
            smoke_invocations.append((smoke_match.group(1), line_number))
            continue

        pytest_match = PYTEST_ENTRY_RE.match(line)
        if pytest_match:
            pytest_entries.append((pytest_match.group(1), line_number))

    duplicate_function_defs = _duplicates(function_defs)
    duplicate_smoke_invocations = _duplicates(smoke_invocations)
    duplicate_pytest_entries = _duplicates(pytest_entries)
    duplicates_total = (
        len(duplicate_function_defs)
        + len(duplicate_smoke_invocations)
        + len(duplicate_pytest_entries)
    )
    required_smoke_invocations = tuple(required_smoke_invocations)
    required_pytest_entries = tuple(required_pytest_entries)
    function_names = [name for name, _line in function_defs]
    smoke_invocation_names = [name for name, _line in smoke_invocations]
    pytest_entry_names = [name for name, _line in pytest_entries]
    missing_required_smoke_definitions = _missing_required(
        required_smoke_invocations,
        function_names,
    )
    missing_required_smoke_invocations = _missing_required(
        required_smoke_invocations,
        smoke_invocation_names,
    )
    missing_required_pytest_entries = _missing_required(
        required_pytest_entries,
        pytest_entry_names,
    )
    required_missing_total = (
        len(missing_required_smoke_definitions)
        + len(missing_required_smoke_invocations)
        + len(missing_required_pytest_entries)
    )

    return {
        "schema_version": "x0tta6bl4-verify-entrypoint-static-guard-v2",
        "status": "VERIFIED HERE",
        "ok": duplicates_total == 0 and required_missing_total == 0,
        "verify_script": str(path),
        "summary": {
            "function_definitions_total": len(function_defs),
            "smoke_invocations_total": len(smoke_invocations),
            "pytest_entries_total": len(pytest_entries),
            "duplicate_function_definitions": len(duplicate_function_defs),
            "duplicate_smoke_invocations": len(duplicate_smoke_invocations),
            "duplicate_pytest_entries": len(duplicate_pytest_entries),
            "duplicates_total": duplicates_total,
            "required_smoke_invocations_total": len(required_smoke_invocations),
            "required_pytest_entries_total": len(required_pytest_entries),
            "missing_required_smoke_definitions": len(missing_required_smoke_definitions),
            "missing_required_smoke_invocations": len(missing_required_smoke_invocations),
            "missing_required_pytest_entries": len(missing_required_pytest_entries),
            "required_missing_total": required_missing_total,
        },
        "duplicate_function_definitions": duplicate_function_defs,
        "duplicate_smoke_invocations": duplicate_smoke_invocations,
        "duplicate_pytest_entries": duplicate_pytest_entries,
        "required_smoke_invocations": list(required_smoke_invocations),
        "required_pytest_entries": list(required_pytest_entries),
        "missing_required_smoke_definitions": missing_required_smoke_definitions,
        "missing_required_smoke_invocations": missing_required_smoke_invocations,
        "missing_required_pytest_entries": missing_required_pytest_entries,
    }


def _render_text(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Verify Entrypoint Static Duplicate Guard",
        f"verify_script: {report['verify_script']}",
        f"ok: {report['ok']}",
        f"duplicates_total: {summary['duplicates_total']}",
        f"duplicate_smoke_invocations: {summary['duplicate_smoke_invocations']}",
        f"duplicate_pytest_entries: {summary['duplicate_pytest_entries']}",
        f"duplicate_function_definitions: {summary['duplicate_function_definitions']}",
        f"required_missing_total: {summary['required_missing_total']}",
        f"missing_required_smoke_definitions: {summary['missing_required_smoke_definitions']}",
        f"missing_required_smoke_invocations: {summary['missing_required_smoke_invocations']}",
        f"missing_required_pytest_entries: {summary['missing_required_pytest_entries']}",
    ]
    for key in ("duplicate_smoke_invocations", "duplicate_pytest_entries", "duplicate_function_definitions"):
        for item in report[key]:
            lines.append(f"{key}: {item['name']} lines={','.join(str(line) for line in item['lines'])}")
    for key in (
        "missing_required_smoke_definitions",
        "missing_required_smoke_invocations",
        "missing_required_pytest_entries",
    ):
        for item in report[key]:
            lines.append(f"{key}: {item['name']}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect duplicate entries in scripts/verify-v1.1.sh")
    parser.add_argument("verify_script", nargs="?", default=DEFAULT_VERIFY_SCRIPT)
    parser.add_argument("--output", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    report = build_report(Path(args.verify_script))
    if args.output == "json":
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(_render_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
