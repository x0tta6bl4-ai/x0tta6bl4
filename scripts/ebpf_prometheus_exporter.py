#!/usr/bin/env python3
"""
eBPF Prometheus Exporter for x0tta6bl4.

Exports XDP datapath telemetry as Prometheus metrics on port 9101.

Stub mode (BPF_STUB_MODE=1):
  Runs without root or bpftool; emits synthetic counters for CI validation.
"""

import json
import logging
import os
import subprocess
import time
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROG_NAME = os.getenv("BPF_PROG_NAME", "xdp_mesh_filter_prog")
EXPORT_PORT = int(os.getenv("BPF_EXPORT_PORT", "9101"))
COLLECTION_INTERVAL = int(os.getenv("BPF_COLLECTION_INTERVAL", "10"))
STUB_MODE = os.getenv("BPF_STUB_MODE", "0").strip().lower() in {"1", "true", "yes"}

# ---------------------------------------------------------------------------
# Prometheus metrics (imported lazily so tests can patch before import)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter, Gauge, start_http_server as _start_http

    _XDP_RUN_TOTAL = Counter(
        "x0tta6bl4_xdp_runs_total",
        "Total number of times XDP program has run",
        ["prog_name", "iface"],
    )
    _XDP_PPS = Gauge(
        "x0tta6bl4_xdp_pps",
        "Processed packets per second by XDP program",
        ["prog_name", "iface"],
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Stub data generator (no kernel / root required)
# ---------------------------------------------------------------------------
_STUB_BASE_RUN_CNT = 0
_STUB_DELTA = 4500  # ~450 PPS at 10s interval


def _stub_get_run_cnt() -> int:
    """Return a monotonically increasing synthetic run count."""
    global _STUB_BASE_RUN_CNT
    _STUB_BASE_RUN_CNT += _STUB_DELTA
    return _STUB_BASE_RUN_CNT


def _stub_get_iface() -> str:
    return "stub0"


def _reset_stub_state() -> None:
    """Reset stub counters (for test isolation)."""
    global _STUB_BASE_RUN_CNT
    _STUB_BASE_RUN_CNT = 0


# ---------------------------------------------------------------------------
# Live data collection (requires bpftool + root)
# ---------------------------------------------------------------------------

def _live_get_run_cnt(prog_name: str = PROG_NAME) -> Optional[int]:
    """Query bpftool for XDP program run count. Returns None on failure."""
    try:
        result = subprocess.run(
            ["sudo", "bpftool", "prog", "show", "name", prog_name, "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        if isinstance(data, list):
            data = data[0] if data else {}
        return int(data.get("run_cnt", 0))
    except Exception as exc:
        log.debug("bpftool query failed: %s", exc)
        return None


def _live_get_iface(prog_name: str = PROG_NAME) -> str:
    """Return the network interface where the XDP program is attached."""
    try:
        result = subprocess.run(
            ["sudo", "bpftool", "net", "show", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return "unknown"
        data = json.loads(result.stdout)
        for entry in data:
            for xdp_entry in entry.get("xdp", []):
                if xdp_entry.get("name") == prog_name:
                    return entry.get("devname", "unknown")
    except Exception as exc:
        log.debug("bpftool net query failed: %s", exc)
    return "unknown"


def _enable_bpf_stats() -> None:
    """Enable kernel BPF stats (requires root). No-op in stub mode."""
    if STUB_MODE:
        return
    try:
        subprocess.run(
            ["sudo", "sysctl", "-w", "kernel.bpf_stats_enabled=1"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except Exception as exc:
        log.warning("Could not enable bpf_stats: %s", exc)


# ---------------------------------------------------------------------------
# Public interface (used by tests and the main loop)
# ---------------------------------------------------------------------------

def collect_stats(
    prog_name: str = PROG_NAME,
    stub: bool = STUB_MODE,
) -> Tuple[Optional[int], str]:
    """
    Collect XDP run count and active interface.

    Returns:
        (run_count, iface) — run_count is None if the program is not loaded.
    """
    if stub:
        return _stub_get_run_cnt(), _stub_get_iface()
    run_cnt = _live_get_run_cnt(prog_name)
    iface = _live_get_iface(prog_name) if run_cnt is not None else "unknown"
    return run_cnt, iface


def compute_pps(delta_runs: int, elapsed_seconds: float) -> float:
    """Calculate packets-per-second from run delta and elapsed time."""
    if elapsed_seconds <= 0:
        return 0.0
    return delta_runs / elapsed_seconds


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_exporter(
    port: int = EXPORT_PORT,
    interval: int = COLLECTION_INTERVAL,
    prog_name: str = PROG_NAME,
    stub: bool = STUB_MODE,
) -> None:  # pragma: no cover — integration entry point
    if not _PROMETHEUS_AVAILABLE:
        raise RuntimeError("prometheus_client is not installed")

    mode_tag = "[STUB]" if stub else "[LIVE]"
    log.info("%s Starting eBPF Prometheus Exporter on port %d", mode_tag, port)

    _enable_bpf_stats()
    _start_http(port)

    last_run_cnt: int = 0
    last_time: float = time.time()

    while True:
        run_cnt, iface = collect_stats(prog_name=prog_name, stub=stub)
        now = time.time()

        if run_cnt is not None:
            delta = max(0, run_cnt - last_run_cnt)
            pps = compute_pps(delta, now - last_time)

            _XDP_RUN_TOTAL.labels(prog_name=prog_name, iface=iface).inc(delta)
            _XDP_PPS.labels(prog_name=prog_name, iface=iface).set(pps)

            log.info("%s iface=%s pps=%.2f total_runs=%d", mode_tag, iface, pps, run_cnt)
            last_run_cnt = run_cnt
        else:
            log.info("%s Waiting for %s to be loaded...", mode_tag, prog_name)

        last_time = now
        time.sleep(interval)


if __name__ == "__main__":
    run_exporter()
