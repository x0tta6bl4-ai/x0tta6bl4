#!/usr/bin/env python3
"""
scripts/check_unused_fixtures.py

Detect test fixtures that are defined but never used as test parameters.

Usage:
    python scripts/check_unused_fixtures.py [--fail-on-warn] [--path tests/]

Exit codes:
    0 — no unused fixtures (or only autouse fixtures)
    1 — unused fixtures found (when --fail-on-warn is set)
"""
from __future__ import annotations

import argparse
import ast
import os
import pathlib
import re
import sys
from collections import defaultdict


def find_python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(root.rglob("*.py"))


def extract_fixture_definitions(path: pathlib.Path) -> list[dict]:
    """Return list of {name, autouse, lineno, file} for each @pytest.fixture."""
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    fixtures = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            # Match @pytest.fixture or @pytest.fixture(...)
            is_fixture = False
            autouse = False

            if isinstance(decorator, ast.Attribute):
                if decorator.attr == "fixture":
                    is_fixture = True
            elif isinstance(decorator, ast.Name):
                if decorator.id == "fixture":
                    is_fixture = True
            elif isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute) and func.attr == "fixture":
                    is_fixture = True
                elif isinstance(func, ast.Name) and func.id == "fixture":
                    is_fixture = True
                # Check autouse keyword
                if is_fixture:
                    for kw in decorator.keywords:
                        if kw.arg == "autouse" and isinstance(kw.value, ast.Constant):
                            autouse = bool(kw.value.value)

            if is_fixture:
                fixtures.append({
                    "name": node.name,
                    "autouse": autouse,
                    "lineno": node.lineno,
                    "file": str(path),
                })
                break  # one fixture decorator per function is enough

    return fixtures


def extract_fixture_usages(path: pathlib.Path) -> set[str]:
    """Return set of all identifiers used as function parameters in test functions."""
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    used: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        for arg in node.args.args:
            used.add(arg.arg)
    return used


def extract_usefixtures_usages(path: pathlib.Path) -> set[str]:
    """Return fixture names referenced in @pytest.mark.usefixtures(...)."""
    try:
        source = path.read_text()
    except Exception:
        return set()
    used: set[str] = set()
    for match in re.finditer(r'usefixtures\(([^)]+)\)', source):
        for name in re.findall(r'["\'](\w+)["\']', match.group(1)):
            used.add(name)
    return used


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect unused pytest fixtures")
    parser.add_argument("--path", default="tests", help="Root directory to scan")
    parser.add_argument("--fail-on-warn", action="store_true",
                        help="Exit 1 if unused fixtures found")
    args = parser.parse_args()

    root = pathlib.Path(args.path)
    if not root.exists():
        print(f"ERROR: path not found: {root}", file=sys.stderr)
        return 2

    all_files = find_python_files(root)

    # Collect all fixture definitions
    all_fixtures: list[dict] = []
    for f in all_files:
        all_fixtures.extend(extract_fixture_definitions(f))

    # Collect all usages across all test files
    all_used: set[str] = set()
    for f in all_files:
        all_used |= extract_fixture_usages(f)
        all_used |= extract_usefixtures_usages(f)

    # Well-known pytest built-ins that don't need to be "used" by name
    BUILTINS = {
        "request", "tmp_path", "tmp_path_factory", "capsys", "capfd",
        "capfdbinary", "caplog", "monkeypatch", "recwarn", "pytestconfig",
        "record_property", "record_xml_attribute", "testdir", "pytester",
        "benchmark", "event_loop",
    }

    unused = []
    for fix in all_fixtures:
        name = fix["name"]
        if fix["autouse"]:
            continue  # autouse fixtures are never explicitly referenced
        if name in BUILTINS:
            continue
        if name in all_used:
            continue
        unused.append(fix)

    # Output
    print(f"Scanned {len(all_files)} Python files")
    print(f"Found {len(all_fixtures)} fixture definitions")
    print(f"Unique fixture usages (as test params): {len(all_used)}")
    print()

    if not unused:
        print("RESULT: PASS — No unused fixtures detected.")
        return 0

    print(f"Potentially unused fixtures ({len(unused)}):")
    by_file: dict[str, list] = defaultdict(list)
    for fix in unused:
        by_file[fix["file"]].append(fix)

    for fpath, fixes in sorted(by_file.items()):
        print(f"\n  {fpath}")
        for fix in sorted(fixes, key=lambda x: x["lineno"]):
            print(f"    L{fix['lineno']:4d}  {fix['name']}")

    print()
    if args.fail_on_warn:
        print("RESULT: FAIL — unused fixtures found (--fail-on-warn)")
        return 1
    else:
        print("RESULT: WARN — review unused fixtures above (use --fail-on-warn to gate CI)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
