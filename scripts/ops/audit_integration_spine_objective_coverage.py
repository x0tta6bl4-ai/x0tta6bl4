#!/usr/bin/env python3
"""Compatibility wrapper for the repo-backed integration-spine coverage audit."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.objective_coverage_audit import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
