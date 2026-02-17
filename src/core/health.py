from __future__ import annotations

import os
import sys
from typing import Any, Dict

_VERSION = os.getenv("X0TTA6BL4_VERSION", "3.2.1")


def get_health() -> Dict[str, Any]:
    """Return minimal service health metadata.

    Future extensions: dependency checks, mesh status, identity state, build info.
    Keep fast (<1ms) and allocation‑light.
    """
    return {"status": "ok", "version": _VERSION}


def get_health_with_dependencies() -> Dict[str, Any]:
    """Return comprehensive health status including dependency checks.

    This includes all optional dependencies and their graceful degradation status.
    """
    try:
        from src.core.dependency_health import check_dependencies_health

        deps_health = check_dependencies_health()

        return {
            "status": (
                "ok" if deps_health.get("overall_status") == "healthy" else "degraded"
            ),
            "version": _VERSION,
            "dependencies": deps_health,
        }
    except Exception as e:
        # Fallback to basic health if dependency checker fails
        return {"status": "ok", "version": _VERSION, "dependency_check_error": str(e)}


def check_cli():
    """CLI entry point for health check."""
    import json

    health = get_health()
    print(json.dumps(health, indent=2))
    sys.exit(0 if health.get("status") == "ok" else 1)
