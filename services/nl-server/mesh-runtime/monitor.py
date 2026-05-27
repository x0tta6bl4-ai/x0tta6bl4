#!/usr/bin/env python3
import json
import time
from pathlib import Path

import psutil
from prometheus_client import CollectorRegistry, Gauge, start_http_server

STATE_PATH = Path("/opt/x0tta6bl4-mesh/state/runtime-state.json")
registry = CollectorRegistry()
cpu_usage = Gauge("mesh_cpu_usage_percent", "CPU usage", registry=registry)
memory_usage = Gauge("mesh_memory_usage_bytes", "Memory usage", registry=registry)
xray_running = Gauge("xray_process_running", "Xray status", registry=registry)
warp_running = Gauge("warp_proxy_running", "WARP proxy status", registry=registry)
ghost_ready = Gauge("ghost_fallback_ready", "Ghost fallback readiness", registry=registry)
mesh_health = Gauge("mesh_health_score", "Health score", registry=registry)
listener_detector_present = Gauge(
    "listener_loss_detector_present",
    "External listener-loss detector signal presence",
    registry=registry,
)
listener_detector_stale = Gauge(
    "listener_loss_detector_stale",
    "External listener-loss detector signal stale flag",
    registry=registry,
)
listener_detector_confidence = Gauge(
    "listener_loss_detector_confidence",
    "External listener-loss detector confidence",
    registry=registry,
)
public_listener = Gauge(
    "xray_public_listener_status",
    "Public ingress listener status by port",
    ["port"],
    registry=registry,
)
public_sessions = Gauge(
    "xray_public_established_sessions",
    "Established sessions by public ingress port",
    ["port"],
    registry=registry,
)
xui_aux_listener = Gauge(
    "xui_aux_listener_status",
    "Auxiliary x-ui listener status by port",
    ["port"],
    registry=registry,
)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def calculate_health_score(state: dict) -> int:
    mode = state.get("mode")
    if mode == "primary":
        return 100
    if mode == "anti_block":
        return 80
    if mode == "degraded":
        return 55
    if mode == "fallback":
        return 35
    return 20


if __name__ == "__main__":
    start_http_server(9090, addr="127.0.0.1", registry=registry)
    print("runtime-state metrics server on 127.0.0.1:9090")
    while True:
        state = read_state()
        probes = state.get("probes", {})
        cpu_usage.set(psutil.cpu_percent(interval=1))
        memory_usage.set(psutil.virtual_memory().used)
        xray_running.set(1 if probes.get("xui_service_ok") else 0)
        warp_running.set(1 if probes.get("warp_ok") else 0)
        ghost_ready.set(1 if probes.get("ghost_ready") else 0)
        mesh_health.set(calculate_health_score(state))
        detector = probes.get("listener_loss_detector", {})
        listener_detector_present.set(1 if detector.get("present") else 0)
        listener_detector_stale.set(1 if detector.get("stale") else 0)
        listener_detector_confidence.set(float(detector.get("confidence") or 0.0))

        listener_status = probes.get("public_listener_status", {})
        session_counts = probes.get("public_established_sessions", {})
        ports = sorted({*listener_status.keys(), *session_counts.keys()}, key=lambda value: int(value))
        for port in ports:
            public_listener.labels(port=port).set(1 if listener_status.get(port) else 0)
            public_sessions.labels(port=port).set(session_counts.get(port, 0))

        aux_status = probes.get("xui_auxiliary_listener_status", {})
        for port in sorted(aux_status.keys(), key=lambda value: int(value)):
            xui_aux_listener.labels(port=port).set(1 if aux_status.get(port) else 0)

        time.sleep(10)
