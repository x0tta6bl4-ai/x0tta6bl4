#!/usr/bin/env python3
"""Validate or apply the X0T bridge contract address in operator config."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.x0t_bridge_config import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
