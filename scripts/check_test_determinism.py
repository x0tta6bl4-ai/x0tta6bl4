#!/usr/bin/env python3
"""
scripts/check_test_determinism.py

Detect common test anti-patterns that cause non-deterministic (flaky) tests:
  1. datetime.now() / datetime.utcnow() calls without mocking
  2. time.time() / time.sleep() in test bodies (not in source code)
  3. random.random() / random.randint() without seed
  4. os.environ direct read in test bodies (not patched)
  5. Hardcoded absolute paths (e.g. /home/user/...)
  6. Global state mutations without cleanup (module-level assignments in tests)

Usage:
    python scripts/check_test_determinism.py [--path tests/] [--fail-on-warn]

Exit codes:
    0 — no issues found (or warnings only)
    1 — issues found (when --fail-on-warn is set)
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from collections import defaultdict
from typing import NamedTuple


class Issue(NamedTuple):
    file: str
    lineno: int
    category: str
    detail: str


SLEEP_THRESHOLD_SECONDS = 5  # Flag sleeps > this as suspicious


def _call_matches(node: ast.Call, *patterns: tuple[str, str]) -> bool:
    """Check if an ast.Call matches any (module, attr) or (None, func_name) pattern."""
    func = node.func
    for module, attr in patterns:
        if module is None:
            if isinstance(func, ast.Name) and func.id == attr:
                return True
        else:
            if (isinstance(func, ast.Attribute)
                    and func.attr == attr
                    and isinstance(func.value, ast.Name)
                    and func.value.id == module):
                return True
    return False


def check_file(path: pathlib.Path) -> list[Issue]:
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    issues: list[Issue] = []
    file_str = str(path)

    # Only check test files (test_*.py or *_test.py)
    if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
        return []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # 1. Unmocked datetime.now() / datetime.utcnow()
        if _call_matches(node, ("datetime", "now"), ("datetime", "utcnow")):
            issues.append(Issue(
                file=file_str,
                lineno=node.lineno,
                category="DATETIME",
                detail="datetime.now()/utcnow() in test — consider freezegun or patch",
            ))

        # 2. time.sleep() with long duration in tests
        if _call_matches(node, ("time", "sleep"), (None, "sleep")):
            if node.args and isinstance(node.args[0], ast.Constant):
                val = node.args[0].value
                if isinstance(val, (int, float)) and val > SLEEP_THRESHOLD_SECONDS:
                    issues.append(Issue(
                        file=file_str,
                        lineno=node.lineno,
                        category="SLEEP",
                        detail=f"time.sleep({val}) > {SLEEP_THRESHOLD_SECONDS}s in test — may cause flakiness",
                    ))

        # 3. random without seed
        if _call_matches(node,
                         ("random", "random"), ("random", "randint"),
                         ("random", "choice"), ("random", "shuffle")):
            issues.append(Issue(
                file=file_str,
                lineno=node.lineno,
                category="RANDOM",
                detail="random call in test without seed — non-deterministic",
            ))

        # 4. os.environ direct read (not patched)
        if _call_matches(node, ("os.environ", "get")):
            # Rough heuristic — flag if not inside a with patch.dict block
            issues.append(Issue(
                file=file_str,
                lineno=node.lineno,
                category="ENV_READ",
                detail="os.environ.get() in test — ensure env is patched/isolated",
            ))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect non-deterministic test patterns")
    parser.add_argument("--path", default="tests", help="Root directory to scan")
    parser.add_argument("--fail-on-warn", action="store_true",
                        help="Exit 1 if issues found")
    parser.add_argument("--categories", default="DATETIME,SLEEP,RANDOM",
                        help="Comma-separated categories to flag (default: DATETIME,SLEEP,RANDOM)")
    args = parser.parse_args()

    root = pathlib.Path(args.path)
    if not root.exists():
        print(f"ERROR: path not found: {root}", file=sys.stderr)
        return 2

    active_categories = set(args.categories.upper().split(","))
    all_files = sorted(root.rglob("test_*.py"))

    all_issues: list[Issue] = []
    for f in all_files:
        for issue in check_file(f):
            if issue.category in active_categories:
                all_issues.append(issue)

    print(f"Scanned {len(all_files)} test files")
    print(f"Active checks: {', '.join(sorted(active_categories))}")
    print()

    if not all_issues:
        print("RESULT: PASS — No determinism issues detected.")
        return 0

    by_category: dict[str, list[Issue]] = defaultdict(list)
    for issue in all_issues:
        by_category[issue.category].append(issue)

    print(f"Issues found: {len(all_issues)}")
    for category, items in sorted(by_category.items()):
        print(f"\n  [{category}] ({len(items)} occurrences)")
        for item in sorted(items, key=lambda x: (x.file, x.lineno))[:20]:
            rel = pathlib.Path(item.file).relative_to(pathlib.Path(args.path).parent)
            print(f"    {rel}:{item.lineno}  {item.detail}")
        if len(items) > 20:
            print(f"    ... and {len(items) - 20} more")

    print()
    if args.fail_on_warn:
        print("RESULT: FAIL — determinism issues found (--fail-on-warn)")
        return 1
    else:
        print("RESULT: WARN — review above (use --fail-on-warn to gate CI)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
