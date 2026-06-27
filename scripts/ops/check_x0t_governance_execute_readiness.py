#!/usr/bin/env python3
"""Generate read-only X0T governance execute-readiness evidence."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.x0t_governance_execute_readiness import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
