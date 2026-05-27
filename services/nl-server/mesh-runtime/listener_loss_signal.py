#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path

STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
SIGNAL_PATH = STATE_DIR / "listener-loss-signal.json"
PRIMARY_PORT = 443


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ss_count(args: list[str], needle: str) -> int:
    try:
        result = subprocess.run(
            ["ss", "-H", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return 0
    return sum(1 for line in result.stdout.splitlines() if needle in line)


def collect_metrics(port: int) -> dict:
    needle = f":{port}"
    return {
        "listening_sockets": ss_count(["-ltn"], needle),
        "established_connections": ss_count(["-tn", "state", "established"], needle),
        "time_wait_connections": ss_count(["-tn", "state", "time-wait"], needle),
        "syn_recv_connections": ss_count(["-tn", "state", "syn-recv"], needle),
    }


def score(metrics: dict) -> float:
    listening = metrics["listening_sockets"]
    established = metrics["established_connections"]
    time_wait = metrics["time_wait_connections"]
    syn_recv = metrics["syn_recv_connections"]

    if listening == 0:
        return 0.0

    confidence = 1.0
    if established == 0:
        confidence -= 0.20
    if time_wait > 0:
        confidence -= 0.10 if time_wait < 10 else 0.20
    if syn_recv > 0:
        confidence -= 0.10 if syn_recv < 5 else 0.20
    if established == 0 and (time_wait > 0 or syn_recv > 0):
        confidence -= 0.10
    return max(0.0, round(confidence, 2))


def classify(metrics: dict, confidence: float) -> tuple[str, str]:
    if metrics["listening_sockets"] == 0:
        return "ANOMALY_DETECTED", "primary listener missing"
    if confidence < 0.70:
        return "ANOMALY_DETECTED", "primary listener degraded by TCP symptom pattern"
    return "BASELINE_OK", "primary listener symptom pattern normal"


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    hostname = socket.gethostname()
    metrics = collect_metrics(PRIMARY_PORT)
    confidence = score(metrics)
    status, reason = classify(metrics, confidence)
    payload = {
        "timestamp": now_iso(),
        "source": "vps-listener-loss-signal",
        "hostname": hostname,
        "port": PRIMARY_PORT,
        "status": status,
        "reason": reason,
        "metrics": {
            **metrics,
            "listener_health_confidence": confidence,
        },
    }
    SIGNAL_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
