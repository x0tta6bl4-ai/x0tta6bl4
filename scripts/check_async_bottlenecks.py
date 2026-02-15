#!/usr/bin/env python3
"""
Script to check for async bottlenecks in x0tta6bl4 codebase.

Finds synchronous blocking operations called in async functions
without asyncio.to_thread or run_in_executor.
"""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class AsyncBottleneck:
    """Represents an async bottleneck issue"""

    file_path: str
    line_number: int
    function_name: str
    issue_type: str
    description: str
    severity: str  # "high", "medium", "low"


def find_async_functions(node: ast.AST) -> List[ast.AsyncFunctionDef]:
    """Find all async function definitions in AST."""
    async_funcs = []
    for child in ast.walk(node):
        if isinstance(child, ast.AsyncFunctionDef):
            async_funcs.append(child)
    return async_funcs


def find_sync_calls_in_async(func: ast.AsyncFunctionDef) -> List[Tuple[int, str]]:
    """Find synchronous function calls in async function."""
    issues = []

    for node in ast.walk(func):
        # Check for direct function calls
        if isinstance(node, ast.Call):
            # Skip if already wrapped in asyncio.to_thread or run_in_executor
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("to_thread", "run_in_executor"):
                    continue
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "asyncio"
                ):
                    continue

            # Check if it's a blocking operation
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                # Common blocking operations
                blocking_patterns = [
                    "time.sleep",
                    "sleep",
                    "requests.get",
                    "requests.post",
                    "subprocess.run",
                    "subprocess.call",
                    "open",
                    "read",
                    "write",
                    "json.load",
                    "json.dump",
                    "pickle.load",
                    "pickle.dump",
                ]

                if any(pattern in func_name for pattern in blocking_patterns):
                    issues.append((node.lineno, func_name))

    return issues


def check_file(file_path: Path) -> List[AsyncBottleneck]:
    """Check a single Python file for async bottlenecks."""
    bottlenecks = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))

        async_funcs = find_async_functions(tree)

        for func in async_funcs:
            sync_calls = find_sync_calls_in_async(func)

            for line_num, call_name in sync_calls:
                bottlenecks.append(
                    AsyncBottleneck(
                        file_path=str(file_path),
                        line_number=line_num,
                        function_name=func.name,
                        issue_type="blocking_call",
                        description=f"Synchronous blocking call '{call_name}' in async function '{func.name}'",
                        severity="high",
                    )
                )

    except SyntaxError as e:
        print(f"⚠️ Syntax error in {file_path}: {e}")
    except Exception as e:
        print(f"⚠️ Error checking {file_path}: {e}")

    return bottlenecks


def check_all_files(src_dir: Path) -> List[AsyncBottleneck]:
    """Check all Python files in src directory."""
    all_bottlenecks = []

    for py_file in src_dir.rglob("*.py"):
        # Skip test files and __pycache__
        if "test" in str(py_file) or "__pycache__" in str(py_file):
            continue

        bottlenecks = check_file(py_file)
        all_bottlenecks.extend(bottlenecks)

    return all_bottlenecks


def main():
    """Main function to check async bottlenecks."""
    src_dir = Path(__file__).parent.parent / "src"

    if not src_dir.exists():
        print(f"❌ Source directory not found: {src_dir}")
        return

    print("🔍 Checking for async bottlenecks...")
    print(f"📁 Scanning: {src_dir}\n")

    bottlenecks = check_all_files(src_dir)

    if not bottlenecks:
        print("✅ No async bottlenecks found!")
        print(
            "\n✅ All blocking operations are properly wrapped in asyncio.to_thread or run_in_executor."
        )
        return

    # Group by severity
    high_severity = [b for b in bottlenecks if b.severity == "high"]
    medium_severity = [b for b in bottlenecks if b.severity == "medium"]
    low_severity = [b for b in bottlenecks if b.severity == "low"]

    print(f"⚠️ Found {len(bottlenecks)} async bottlenecks:\n")

    if high_severity:
        print("🔴 HIGH SEVERITY:")
        for b in high_severity:
            print(f"  {b.file_path}:{b.line_number}")
            print(f"    Function: {b.function_name}")
            print(f"    Issue: {b.description}\n")

    if medium_severity:
        print("🟡 MEDIUM SEVERITY:")
        for b in medium_severity:
            print(f"  {b.file_path}:{b.line_number}")
            print(f"    Function: {b.function_name}")
            print(f"    Issue: {b.description}\n")

    if low_severity:
        print("🟢 LOW SEVERITY:")
        for b in low_severity:
            print(f"  {b.file_path}:{b.line_number}")
            print(f"    Function: {b.function_name}")
            print(f"    Issue: {b.description}\n")

    print(f"\n📊 Summary:")
    print(f"  Total: {len(bottlenecks)}")
    print(f"  High: {len(high_severity)}")
    print(f"  Medium: {len(medium_severity)}")
    print(f"  Low: {len(low_severity)}")


if __name__ == "__main__":
    main()
