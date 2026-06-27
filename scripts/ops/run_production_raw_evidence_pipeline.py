#!/usr/bin/env python3
"""CLI wrapper for the read-only production raw-evidence pipeline plan."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.production_raw_evidence_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
