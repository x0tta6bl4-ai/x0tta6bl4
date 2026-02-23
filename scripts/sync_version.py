#!/usr/bin/env python3
"""
Version synchronization script for x0tta6bl4.

Canonical source by default: src/version.py::__version__

Sync targets:
- src/version.py
- VERSION
- pyproject.toml [project.version]
- ROADMAP.md (**Version:**)
- Dockerfile LABEL version (if present)

Usage:
    python scripts/sync_version.py
    python scripts/sync_version.py --version 3.3.1
    python scripts/sync_version.py --source version-file
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.\-]+)?$")


def _validate_version(version: str) -> str:
    version = version.strip()
    if not SEMVER_RE.match(version):
        raise ValueError(f"Invalid semver: {version!r}")
    return version


def _read_src_version(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not parse __version__ from {path}")
    return _validate_version(match.group(1))


def _read_version_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"VERSION file not found: {path}")
    return _validate_version(path.read_text(encoding="utf-8"))


def _replace_regex(path: Path, pattern: str, replacement: str, dry_run: bool) -> bool:
    if not path.exists():
        return False
    old = path.read_text(encoding="utf-8")
    new = re.sub(pattern, replacement, old, flags=re.MULTILINE)
    if new == old:
        return False
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return True


def _set_exact_file(path: Path, content: str, dry_run: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if old == content:
        return False
    if not dry_run:
        path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync version across contract files")
    parser.add_argument(
        "--version",
        type=str,
        help="Version to set explicitly (overrides source file)",
    )
    parser.add_argument(
        "--source",
        choices=("src", "version-file"),
        default="src",
        help="Source of truth when --version is not provided (default: src)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    src_version_file = root / "src" / "version.py"
    version_file = root / "VERSION"
    pyproject_file = root / "pyproject.toml"
    roadmap_file = root / "ROADMAP.md"
    dockerfile = root / "Dockerfile"

    if args.version:
        version = _validate_version(args.version)
        print(f"Using explicit version: {version}")
    elif args.source == "version-file":
        version = _read_version_file(version_file)
        print(f"Using VERSION as source: {version}")
    else:
        version = _read_src_version(src_version_file)
        print(f"Using src/version.py as source: {version}")

    updated: list[str] = []

    if _replace_regex(
        src_version_file,
        r'^__version__\s*=\s*"[^"]+"',
        f'__version__ = "{version}"',
        args.dry_run,
    ):
        updated.append("src/version.py")

    if _set_exact_file(version_file, f"{version}\n", args.dry_run):
        updated.append("VERSION")

    if _replace_regex(
        pyproject_file,
        r'^(version\s*=\s*")[^"]+(")$',
        rf'\g<1>{version}\g<2>',
        args.dry_run,
    ):
        updated.append("pyproject.toml (project.version)")

    if _replace_regex(
        pyproject_file,
        r'^(# For development, update VERSION file: echo ")[^"]+(" > VERSION)$',
        rf'\g<1>{version}\g<2>',
        args.dry_run,
    ):
        updated.append("pyproject.toml (version comment)")

    if _replace_regex(
        roadmap_file,
        r"(\*\*Version:\*\*\s*)[^\n]+",
        rf"\g<1>{version}",
        args.dry_run,
    ):
        updated.append("ROADMAP.md")

    if _replace_regex(
        dockerfile,
        r'(LABEL\s+version=")[^"]+(")',
        rf"\g<1>{version}\g<2>",
        args.dry_run,
    ):
        updated.append("Dockerfile")

    if args.dry_run:
        if updated:
            print("Would update:")
            for item in updated:
                print(f" - {item}")
        else:
            print("No updates needed.")
        return 0

    if updated:
        print("Updated:")
        for item in updated:
            print(f" - {item}")
    else:
        print("All version targets already in sync.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
