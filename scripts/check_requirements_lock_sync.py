#!/usr/bin/env python3
"""Validate that direct pins from requirements.txt are present in requirements.lock."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)==([^\s;#]+)")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = PIN_RE.match(stripped)
        if not match:
            continue
        pkg_name = normalize_name(match.group(1))
        pins[pkg_name] = match.group(2)
    return pins


def main() -> int:
    req_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("requirements.txt")
    lock_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("requirements.lock")

    if not req_path.exists():
        print(f"requirements file not found: {req_path}")
        return 2
    if not lock_path.exists():
        print(f"lock file not found: {lock_path}")
        return 2

    req_pins = load_pins(req_path)
    lock_pins = load_pins(lock_path)

    missing: list[str] = []
    mismatched: list[tuple[str, str, str]] = []

    for package_name, expected_version in sorted(req_pins.items()):
        lock_version = lock_pins.get(package_name)
        if lock_version is None:
            missing.append(f"{package_name}=={expected_version}")
            continue
        if lock_version != expected_version:
            mismatched.append((package_name, expected_version, lock_version))

    if not missing and not mismatched:
        print(
            f"requirements sync OK: {req_path} ({len(req_pins)}) -> "
            f"{lock_path} ({len(lock_pins)})"
        )
        return 0

    print("requirements sync FAILED")
    if missing:
        print("missing in lock:")
        for item in missing:
            print(f"  - {item}")
    if mismatched:
        print("version mismatches:")
        for package_name, expected_version, actual_version in mismatched:
            print(f"  - {package_name}: requirements={expected_version}, lock={actual_version}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

