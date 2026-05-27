#!/usr/bin/env python3
"""Compatibility wrapper for the external X0T settlement operator handoff."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.external_settlement_operator_handoff import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
