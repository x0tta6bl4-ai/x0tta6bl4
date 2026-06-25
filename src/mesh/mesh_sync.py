#!/usr/bin/env python3
"""
x0tta6bl4 Mesh Sync Daemon
Syncs mesh state between local Ghost-Core API and NL peer.
Runs on Athlon, polls both APIs and updates mesh_stats.json.
"""
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [MESH-SYNC] - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mesh-sync")

LOCAL_API = "http://localhost:8001"
NL_API = "http://89.125.1.107:8000"
MESH_STATS_FILE = "/mnt/projects/.tmp/mesh_stats.json"
POLL_INTERVAL = 30  # seconds

LOCAL_NODE_ID = "ATHLON-NODE-01"
NL_NODE_ID = "GHOST-NODE"


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from a URL with timeout."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("https", "http"):
            logger.warning("Banned URL scheme: %s", parsed.scheme)
            return None
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _mesh_status_from_api(api_url: str, api_name: str, expected_node: str) -> dict:
    """Get mesh status from a Ghost-Core API."""
    status = _fetch_json(f"{api_url}/api/status")
    if not status:
        return {
            "node_id": f"{expected_node}",
            "reachable": False,
            "status": "UNREACHABLE",
            "uptime": 0,
        }
    return {
        "node_id": status.get("node_id", expected_node),
        "reachable": True,
        "status": status.get("status", "UNKNOWN"),
        "uptime": status.get("uptime", 0),
        "coherence": status.get("coherence", "0%"),
    }


def sync_mesh_state() -> None:
    """Fetch state from both nodes and write merged mesh_stats.json."""
    local = _mesh_status_from_api(LOCAL_API, "local", LOCAL_NODE_ID)
    remote = _mesh_status_from_api(NL_API, "NL", NL_NODE_ID)

    # Resolve peer address — use NL's real IP
    peer_addr = "89.125.1.107:8000"

    peers = []
    if remote.get("reachable"):
        peers.append({
            "node_id": remote["node_id"],
            "address": peer_addr,
            "status": remote["status"],
            "uptime": remote["uptime"],
            "coherence": remote.get("coherence", "0%"),
        })

    mesh_state = {
        "node_id": local["node_id"],
        "pulse_coherence": local.get("coherence", "100.0%"),
        "dropped_probes": 0,
        "evolution_gen": 1,
        "pulse_status": local.get("status", "NORMAL"),
        "peer_count": len(peers),
        "peers": peers,
        "last_sync_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Write to file
    try:
        with open(MESH_STATS_FILE, "w") as f:
            json.dump(mesh_state, f, indent=2)
        logger.info(
            "Sync OK | local=%s peer_count=%d peers=%s",
            local["node_id"], len(peers),
            [p["node_id"] for p in peers],
        )
    except OSError as exc:
        logger.error("Failed to write %s: %s", MESH_STATS_FILE, exc)


def main() -> None:
    logger.info("Mesh sync daemon starting: local=%s remote=%s", LOCAL_API, NL_API)
    logger.info("Poll interval: %ds", POLL_INTERVAL)

    # Immediate first sync
    sync_mesh_state()

    while True:
        try:
            time.sleep(POLL_INTERVAL)
            sync_mesh_state()
        except KeyboardInterrupt:
            logger.info("Shutting down")
            break
        except Exception as exc:
            logger.error("Sync error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
