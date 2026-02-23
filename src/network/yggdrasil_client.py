"""Yggdrasil mesh network client (Strict Production Edition)."""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _find_yggdrasilctl() -> Optional[str]:
    """Find yggdrasilctl binary in standard locations."""
    locations: List[str] = [
        "yggdrasilctl",
        "/usr/local/bin/yggdrasilctl",
        "/usr/bin/yggdrasilctl",
        "/usr/sbin/yggdrasilctl",
        "/sbin/yggdrasilctl",
    ]
    for loc in locations:
        if shutil.which(loc) or os.path.exists(loc):
            return loc
    return None

def get_yggdrasil_status() -> Dict[str, Any]:
    """Get Yggdrasil node status. Requires real binary unless TESTING is set."""
    testing = os.getenv("X0TTA6BL4_TESTING", "false").lower() == "true"
    force_mock = os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}

    if force_mock or testing:
        return {
            "address": "fd00::mock",
            "subnet": "fd00::/8",
            "status": "mock",
        }

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        raise RuntimeError("yggdrasilctl not found. Mesh networking unavailable.")

    try:
        result = subprocess.run(
            [yggdrasilctl_path, "getSelf"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        status = {}
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                status[key] = value.strip()
        return {"status": "online", "node": status}
    except Exception as e:
        return {"status": "offline", "error": str(e)}

def get_yggdrasil_peers() -> Dict[str, Any]:
    """Get list of connected peers."""
    testing = os.getenv("X0TTA6BL4_TESTING", "false").lower() == "true"
    force_mock = os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}

    if force_mock or testing:
        return {"status": "ok", "peers": [], "count": 0}

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        raise RuntimeError("yggdrasilctl not found")

    try:
        result = subprocess.run(
            [yggdrasilctl_path, "getPeers"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        peers = []
        for line in result.stdout.strip().split("\n"):
            if line.strip() and not line.startswith("Peer"):
                parts = line.split()
                if len(parts) >= 3:
                    peers.append({"port": parts[0], "protocol": parts[1], "remote": parts[2]})
        return {"status": "ok", "peers": peers, "count": len(peers)}
    except Exception as e:
        return {"status": "error", "error": str(e), "peers": [], "count": 0}

def get_yggdrasil_routes() -> Dict[str, Any]:
    """Get routing table information."""
    testing = os.getenv("X0TTA6BL4_TESTING", "false").lower() == "true"
    force_mock = os.environ.get("YGGDRASIL_MOCK", "").lower() in {"1", "true", "yes"}

    if force_mock or testing:
        return {"status": "ok", "routing_table_size": 0}

    yggdrasilctl_path = _find_yggdrasilctl()
    if not yggdrasilctl_path:
        raise RuntimeError("yggdrasilctl not found")

    try:
        result = subprocess.run(
            [yggdrasilctl_path, "getSelf"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        routing_size = 0
        for line in result.stdout.strip().split("\n"):
            if "Routing table size" in line:
                _, value = line.split(":", 1)
                routing_size = int(value.strip())
        return {"status": "ok", "routing_table_size": routing_size}
    except Exception as e:
        return {"status": "error", "error": str(e), "routing_table_size": 0}
