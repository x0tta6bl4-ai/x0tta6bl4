#!/usr/bin/env python3
"""Local desktop mesh runtime heartbeat for the native x0tta6bl4 app.

This process is intentionally local-only. It lets the packaged Ubuntu app start
and stop a real service and observe local state files, without claiming external
dataplane delivery, customer traffic, DPI bypass, or production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
SCHEMA = "x0tta6bl4.desktop_mesh_runtime.v1"
CLAIM_BOUNDARY = (
    "Local desktop runtime heartbeat only. This service proves that the local "
    "Ubuntu node service is installed and running; it does not prove production "
    "readiness, customer traffic, external DPI bypass, settlement finality, or "
    "live mesh dataplane delivery."
)

RUNNING = True


def _stop(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _payloads(state_dir: Path, started_at: float) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = _utc_now()
    hostname = socket.gethostname() or "localhost"
    uptime_s = max(0, round(time.time() - started_at, 3))
    node_id = f"desktop-{hostname}"

    runtime = {
        "schema": SCHEMA,
        "mode": "desktop-local-node",
        "node_id": node_id,
        "hostname": hostname,
        "started_at_utc": datetime.fromtimestamp(started_at, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "updated_at_utc": now,
        "uptime_s": uptime_s,
        "recommended_action": "observe",
        "peers": [
            {
                "node_id": node_id,
                "role": "local-desktop-control-plane",
                "status": "local_runtime_running",
                "last_seen_utc": now,
            }
        ],
        "hot_path_summary": {
            "runtime_mode": "desktop-local-node",
            "recommended_action": "observe",
            "best_path": "local-loopback",
            "best_path_port": 8000,
            "transport_health_status": "local_runtime_heartbeat",
            "subscription_health_status": "not_configured",
            "primary_path_latency_s": 0.0,
            "secondary_path_latency_s": None,
            "fallback_nl_path_latency_s": None,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }

    hint = {
        "schema": SCHEMA,
        "runtime_mode": "desktop-local-node",
        "recommended_action": "observe",
        "recommended_profile": "desktop-local-primary",
        "best_path": "local-loopback",
        "best_path_port": 8000,
        "transport_health_status": "local_runtime_heartbeat",
        "subscription_health_status": "not_configured",
        "state_dir": str(state_dir),
        "updated_at_utc": now,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    signal_payload = {
        "schema": SCHEMA,
        "status": "BASELINE_OK",
        "source": "desktop_mesh_runtime",
        "updated_at_utc": now,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    return runtime, hint, signal_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local x0tta6bl4 desktop mesh heartbeat.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true", help="Write one heartbeat and exit.")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    started_at = time.time()
    interval = max(1.0, args.interval)

    if args.once:
        runtime, hint, signal_payload = _payloads(args.state_dir, started_at)
        _write_json(args.state_dir / "runtime-state.json", runtime)
        _write_json(args.state_dir / "client-profile-hint.json", hint)
        _write_json(args.state_dir / "listener-loss-signal.json", signal_payload)
        return 0

    while RUNNING:
        runtime, hint, signal_payload = _payloads(args.state_dir, started_at)
        _write_json(args.state_dir / "runtime-state.json", runtime)
        _write_json(args.state_dir / "client-profile-hint.json", hint)
        _write_json(args.state_dir / "listener-loss-signal.json", signal_payload)
        time.sleep(interval)

    runtime, hint, signal_payload = _payloads(args.state_dir, started_at)
    runtime["recommended_action"] = "stopped"
    runtime["mode"] = "desktop-local-node-stopping"
    hint["recommended_action"] = "stopped"
    signal_payload["status"] = "STOPPING"
    _write_json(args.state_dir / "runtime-state.json", runtime)
    _write_json(args.state_dir / "client-profile-hint.json", hint)
    _write_json(args.state_dir / "listener-loss-signal.json", signal_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
