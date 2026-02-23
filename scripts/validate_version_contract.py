#!/usr/bin/env python3
"""
Validate version contract across code and roadmap docs.

Contract:
1) Canonical source is `src/version.py::__version__`.
2) `VERSION`, `pyproject.toml[project.version]`, `ROADMAP.md` version must match.
3) `docs/roadmap.md` must remain a redirect to root `ROADMAP.md`.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.\-]+)?$")


def _extract_src_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not parse __version__ from {path}")
    return match.group(1).strip()


def _extract_roadmap_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"\*\*Version:\*\*\s*([^\n]+)", text)
    if not match:
        raise ValueError(f"Could not parse '**Version:**' from {path}")
    return match.group(1).strip()


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    src_version = _extract_src_version(root / "src" / "version.py")
    version_file = (root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_version = str(pyproject.get("project", {}).get("version", "")).strip()
    roadmap_version = _extract_roadmap_version(root / "ROADMAP.md")

    errors: list[str] = []

    for label, value in [
        ("src/version.py::__version__", src_version),
        ("VERSION", version_file),
        ("pyproject.toml[project.version]", pyproject_version),
        ("ROADMAP.md **Version:**", roadmap_version),
    ]:
        if not value:
            errors.append(f"{label} is empty")
            continue
        if not SEMVER_RE.match(value):
            errors.append(f"{label} has invalid semver format: {value!r}")

    if src_version != version_file:
        errors.append(
            f"VERSION mismatch: src/version.py={src_version} vs VERSION={version_file}"
        )
    if src_version != pyproject_version:
        errors.append(
            "pyproject mismatch: "
            f"src/version.py={src_version} vs pyproject.toml={pyproject_version}"
        )
    if src_version != roadmap_version:
        errors.append(
            f"ROADMAP mismatch: src/version.py={src_version} vs ROADMAP.md={roadmap_version}"
        )

    docs_roadmap = root / "docs" / "roadmap.md"
    if docs_roadmap.exists():
        docs_text = docs_roadmap.read_text(encoding="utf-8")
        redirect_marker = "[`ROADMAP.md`](../ROADMAP.md)"
        if redirect_marker not in docs_text:
            errors.append(
                f"docs/roadmap.md must redirect to root roadmap via {redirect_marker}"
            )

    if errors:
        print("Version contract violations:")
        for err in errors:
            print(f" - {err}")
        return 1

    print(f"Version contract check passed (version={src_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
