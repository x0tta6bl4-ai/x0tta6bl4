from __future__ import annotations

import os
import sys
from typing import Dict

_VERSION = os.getenv("X0TTA6BL4_VERSION", "1.0.0")


def get_health() -> Dict[str, str]:
    """Return minimal service health metadata.

    Future extensions: dependency checks, mesh status, identity state, build info.
    Keep fast (<1ms) and allocation‑light.
    """
    return {"status": "ok", "version": _VERSION}


def check_cli():
    """CLI entry point for health check."""
    import json
    health = get_health()
    print(json.dumps(health, indent=2))
    sys.exit(0 if health.get("status") == "ok" else 1)
