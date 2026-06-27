#!/usr/bin/env python3
"""CLI wrapper for the raw-evidence operator packet index."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.production_raw_evidence_operator_packet import main


if __name__ == "__main__":
    raise SystemExit(main())
