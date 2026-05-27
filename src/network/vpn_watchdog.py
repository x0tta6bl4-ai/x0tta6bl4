#!/usr/bin/env python3
"""
VPN Watchdog — MAPE-K Self-Healing for xray/sing-box VPN.

Monitors:
- FIN-WAIT-2 / CLOSE-WAIT connection accumulation (main cause of xray slowdowns)
- Actual SOCKS5 proxy health via real HTTP request
- Packet loss to VPN server
- xray process liveness

Heals:
- SIGHUP to xray for graceful reload (clears stale connections)
- optional SIGTERM + wait for v2rayN to auto-restart xray if SIGHUP fails
- ss -K to force-close stuck TCP states (requires root or CAP_NET_ADMIN)

Exposes Prometheus metrics on port 9091.
"""

import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional


def _build_log_handlers() -> list[logging.Handler]:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_path = os.getenv("VPN_WATCHDOG_LOG_PATH", f"/tmp/vpn_watchdog-{os.getuid()}.log")
    if not log_path:
        return handlers

    try:
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    except OSError as exc:
        print(f"VPN Watchdog file logging disabled for {log_path}: {exc}", file=sys.stderr)

    return handlers


logger = logging.getLogger("vpn_watchdog")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VPN-Watchdog] %(levelname)s %(message)s",
    handlers=_build_log_handlers(),
)

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_SOCKS_PORT_CANDIDATES = (10918, 10808, 10809, 10924, 40467, 1080, 7890, 7891)


def _parse_ports(*values: str | None) -> tuple[int, ...]:
    ports: list[int] = []
    for value in values:
        if not value:
            continue
        for raw in value.replace(";", ",").split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                port = int(raw)
            except ValueError:
                continue
            if 0 < port < 65536 and port not in ports:
                ports.append(port)
    for port in DEFAULT_SOCKS_PORT_CANDIDATES:
        if port not in ports:
            ports.append(port)
    return tuple(ports)


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _socks_handshake(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.send(b"\x05\x01\x00")
            return s.recv(2) == b"\x05\x00"
    except OSError:
        return False


VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
VPN_PORT = int(os.getenv("VPN_PORT", "39829"))
SOCKS_HOST = os.getenv("VPN_SOCKS_HOST", "127.0.0.1")
SOCKS_PORT_CANDIDATES = _parse_ports(
    os.getenv("VPN_SOCKS_PORT"),
    os.getenv("SOCKS_PORT"),
    os.getenv("VPN_SOCKS_PORT_CANDIDATES"),
)
SOCKS_PORT = SOCKS_PORT_CANDIDATES[0]
METRICS_PORT = int(os.getenv("VPN_WATCHDOG_METRICS_PORT", "9091"))

FIN_WAIT2_THRESHOLD = int(os.getenv("VPN_FIN_WAIT2_THRESHOLD", "50"))
CLOSE_WAIT_THRESHOLD = int(os.getenv("VPN_CLOSE_WAIT_THRESHOLD", "30"))
PACKET_LOSS_WARN_PCT = float(os.getenv("VPN_PACKET_LOSS_WARN", "20.0"))
PACKET_LOSS_HEAL_PCT = float(os.getenv("VPN_PACKET_LOSS_HEAL", "50.0"))
PROXY_TIMEOUT_SEC = float(os.getenv("VPN_PROXY_TIMEOUT", "8.0"))
CHECK_INTERVAL_SEC = int(os.getenv("VPN_CHECK_INTERVAL", "10"))
ENABLE_HEAL = _parse_bool(os.getenv("VPN_WATCHDOG_ENABLE_HEAL"), False)
PROXY_HEAL_FAILURES = int(os.getenv("VPN_PROXY_HEAL_FAILURES", "3"))
PACKET_LOSS_HEAL_FAILURES = int(os.getenv("VPN_PACKET_LOSS_HEAL_FAILURES", "2"))
STALE_STATE_HEAL_FAILURES = int(os.getenv("VPN_STALE_STATE_HEAL_FAILURES", "2"))
PREEMPTIVE_CLEANUP_FAILURES = int(os.getenv("VPN_PREEMPTIVE_CLEANUP_FAILURES", "3"))

XRAY_PROCESS_PATTERN = "xray run"
HEAL_COOLDOWN_SEC = int(os.getenv("VPN_HEAL_COOLDOWN_SEC", "1800"))
PROVIDER_GUARD_SCRIPT = os.getenv("VPN_PROVIDER_GUARD_SCRIPT", "/mnt/projects/scripts/vpn_provider_guard.py")
PROVIDER_GUARD_DISABLED = _parse_bool(os.getenv("VPN_PROVIDER_GUARD_DISABLE"), False)
PROVIDER_GUARD_REQUIRE_FRESH = _parse_bool(os.getenv("VPN_PROVIDER_GUARD_REQUIRE_FRESH"), False)
PROVIDER_GUARD_MAX_AGE_SECONDS = int(os.getenv("VPN_PROVIDER_GUARD_MAX_AGE_SECONDS", "3600"))
ENABLE_HARD_HEAL = _parse_bool(
    os.getenv("VPN_WATCHDOG_ALLOW_HARD_HEAL", os.getenv("VPN_ALLOW_HARD_HEAL")),
    False,
)


def provider_guard_allows_heal(*, require_fresh: bool | None = None) -> tuple[bool, str]:
    effective_require_fresh = PROVIDER_GUARD_REQUIRE_FRESH if require_fresh is None else require_fresh
    if PROVIDER_GUARD_DISABLED:
        if effective_require_fresh:
            return False, "provider guard disabled; fresh snapshot required"
        return True, "provider guard disabled"
    if not os.path.exists(PROVIDER_GUARD_SCRIPT):
        if effective_require_fresh:
            return False, "provider guard unavailable; fresh snapshot required"
        return True, "provider guard unavailable"
    cmd = [
        sys.executable,
        PROVIDER_GUARD_SCRIPT,
        "--check",
        "--max-age-seconds",
        str(PROVIDER_GUARD_MAX_AGE_SECONDS),
    ]
    if effective_require_fresh:
        cmd.append("--require-fresh")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if effective_require_fresh:
            return False, f"provider guard inconclusive while fresh snapshot is required: {exc}"
        return True, f"provider guard inconclusive: {exc}"
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 10:
        return False, output or "provider guard blocked local heal"
    if result.returncode != 0:
        if effective_require_fresh:
            return False, f"provider guard inconclusive while fresh snapshot is required rc={result.returncode}: {output}"
        return True, f"provider guard inconclusive rc={result.returncode}: {output}"
    return True, output or "provider guard allowed local heal"


# ── Metrics (simple Prometheus text format) ────────────────────────────────────

@dataclass
class WatchdogMetrics:
    fin_wait2_count: int = 0
    close_wait_count: int = 0
    established_count: int = 0
    packet_loss_pct: float = 0.0
    proxy_healthy: int = 0       # 1 = healthy, 0 = unhealthy
    proxy_latency_ms: float = 0.0
    heal_count: int = 0
    last_heal_timestamp: float = 0.0
    check_count: int = 0
    proxy_failure_streak: int = 0
    packet_loss_failure_streak: int = 0
    stale_state_failure_streak: int = 0

    def to_prometheus(self) -> str:
        lines = [
            "# HELP vpn_fin_wait2_connections FIN-WAIT-2 connections to VPN server",
            "# TYPE vpn_fin_wait2_connections gauge",
            f"vpn_fin_wait2_connections {self.fin_wait2_count}",
            "# HELP vpn_close_wait_connections CLOSE-WAIT connections to VPN server",
            "# TYPE vpn_close_wait_connections gauge",
            f"vpn_close_wait_connections {self.close_wait_count}",
            "# HELP vpn_established_connections ESTABLISHED connections to VPN server",
            "# TYPE vpn_established_connections gauge",
            f"vpn_established_connections {self.established_count}",
            "# HELP vpn_packet_loss_percent Packet loss percentage to VPN server",
            "# TYPE vpn_packet_loss_percent gauge",
            f"vpn_packet_loss_percent {self.packet_loss_pct:.1f}",
            "# HELP vpn_proxy_healthy 1 if SOCKS5 proxy is healthy",
            "# TYPE vpn_proxy_healthy gauge",
            f"vpn_proxy_healthy {self.proxy_healthy}",
            "# HELP vpn_proxy_latency_ms Proxy latency in milliseconds",
            "# TYPE vpn_proxy_latency_ms gauge",
            f"vpn_proxy_latency_ms {self.proxy_latency_ms:.1f}",
            "# HELP vpn_heal_total Total number of healing actions taken",
            "# TYPE vpn_heal_total counter",
            f"vpn_heal_total {self.heal_count}",
            "# HELP vpn_checks_total Total number of health checks performed",
            "# TYPE vpn_checks_total counter",
            f"vpn_checks_total {self.check_count}",
            "# HELP vpn_proxy_failure_streak Consecutive unhealthy SOCKS5 proxy checks",
            "# TYPE vpn_proxy_failure_streak gauge",
            f"vpn_proxy_failure_streak {self.proxy_failure_streak}",
            "# HELP vpn_packet_loss_failure_streak Consecutive packet-loss heal-threshold breaches",
            "# TYPE vpn_packet_loss_failure_streak gauge",
            f"vpn_packet_loss_failure_streak {self.packet_loss_failure_streak}",
            "# HELP vpn_stale_state_failure_streak Consecutive stale TCP state threshold breaches",
            "# TYPE vpn_stale_state_failure_streak gauge",
            f"vpn_stale_state_failure_streak {self.stale_state_failure_streak}",
        ]
        return "\n".join(lines) + "\n"


_metrics = WatchdogMetrics()


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/metrics", "/"):
            body = _metrics.to_prometheus().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress HTTP server logs


def start_metrics_server():
    server = HTTPServer(("127.0.0.1", METRICS_PORT), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Prometheus metrics on http://127.0.0.1:{METRICS_PORT}/metrics")


# ── Health Checks ──────────────────────────────────────────────────────────────

def check_connection_states() -> dict:
    """Parse ss output for connection states to VPN server."""
    states = {"ESTAB": 0, "FIN-WAIT-2": 0, "CLOSE-WAIT": 0, "LAST-ACK": 0}
    try:
        result = subprocess.run(
            ["ss", "-tn", "dst", VPN_SERVER],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            for state in states:
                if state in line:
                    states[state] += 1
                    break
    except Exception as e:
        logger.warning(f"ss check failed: {e}")
    return states


def check_proxy_health() -> tuple[bool, float]:
    """Test actual HTTP request through SOCKS5 proxy. Returns (ok, latency_ms)."""
    global SOCKS_PORT

    detected_port = discover_socks_port()
    if detected_port is None:
        return False, 0.0
    if detected_port != SOCKS_PORT:
        logger.info(f"Detected active SOCKS5 proxy at {SOCKS_HOST}:{detected_port}")
        SOCKS_PORT = detected_port

    curl_result = _curl_proxy_health(SOCKS_PORT)
    if curl_result is not None:
        return curl_result

    try:
        import urllib.request
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"socks5h://{SOCKS_HOST}:{SOCKS_PORT}",
            "https": f"socks5h://{SOCKS_HOST}:{SOCKS_PORT}",
        })
        opener = urllib.request.build_opener(proxy_handler)
        t0 = time.monotonic()
        # Use a lightweight endpoint
        resp = opener.open("http://cp.cloudflare.com/", timeout=PROXY_TIMEOUT_SEC)
        latency = (time.monotonic() - t0) * 1000
        ok = resp.status == 200
        return ok, latency
    except Exception:
        pass

    # Fallback: raw TCP SOCKS5 handshake check
    try:
        t0 = time.monotonic()
        with socket.create_connection((SOCKS_HOST, SOCKS_PORT), timeout=3) as s:
            # SOCKS5 greeting: VER=5, NMETHODS=1, METHOD=0 (no auth)
            s.send(b"\x05\x01\x00")
            resp = s.recv(2)
            latency = (time.monotonic() - t0) * 1000
            if resp == b"\x05\x00":
                return True, latency
    except Exception as e:
        logger.debug(f"SOCKS5 handshake failed: {e}")

    return False, 0.0


def discover_socks_port() -> Optional[int]:
    for port in SOCKS_PORT_CANDIDATES:
        if _socks_handshake(SOCKS_HOST, port):
            return port
    return None


def _curl_proxy_health(port: int) -> Optional[tuple[bool, float]]:
    try:
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "--max-time",
                str(PROXY_TIMEOUT_SEC),
                "--proxy",
                f"socks5h://{SOCKS_HOST}:{port}",
                "-w",
                "%{time_total} %{http_code}",
                "https://cp.cloudflare.com/generate_204",
            ],
            capture_output=True,
            text=True,
            timeout=PROXY_TIMEOUT_SEC + 2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        total_raw, code = result.stdout.strip().split(maxsplit=1)
        latency_ms = float(total_raw) * 1000.0
    except ValueError:
        return None

    return code in {"200", "204"}, latency_ms


def check_packet_loss() -> float:
    """Ping VPN server 5 times, return packet loss percentage."""
    try:
        result = subprocess.run(
            ["ping", "-c", "5", "-W", "2", "-q", VPN_SERVER],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            # "5 packets transmitted, 3 received, 40% packet loss"
            m = re.search(r"(\d+)% packet loss", line)
            if m:
                return float(m.group(1))
    except Exception as e:
        logger.warning(f"Ping check failed: {e}")
    return 0.0


def get_xray_pid() -> Optional[int]:
    """Find running xray process PID."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", XRAY_PROCESS_PATTERN],
            capture_output=True, text=True, timeout=3
        )
        pids = result.stdout.strip().splitlines()
        if pids:
            return int(pids[0])
    except Exception:
        pass
    return None


# ── Healing Actions ────────────────────────────────────────────────────────────

class VPNHealer:
    def __init__(self):
        self._last_heal = 0.0
        self._heal_count = 0

    def _can_heal(self) -> bool:
        return (time.monotonic() - self._last_heal) > HEAL_COOLDOWN_SEC

    def force_close_stale(self):
        """Force close FIN-WAIT-2 and CLOSE-WAIT connections (needs CAP_NET_ADMIN)."""
        for state in ("fin-wait-2", "close-wait"):
            try:
                subprocess.run(
                    ["ss", "-K", "dst", VPN_SERVER, "state", state],
                    timeout=5, capture_output=True
                )
                logger.info(f"Force-closed {state} connections to {VPN_SERVER}")
            except Exception as e:
                logger.debug(f"ss -K {state} failed (may need root): {e}")

    def sighup_xray(self) -> bool:
        """Send SIGHUP to xray for graceful reload (clears connection state)."""
        pid = get_xray_pid()
        if not pid:
            logger.error("xray process not found, cannot SIGHUP")
            return False
        try:
            os.kill(pid, signal.SIGHUP)
            logger.info(f"Sent SIGHUP to xray PID {pid}")
            time.sleep(3)
            return get_xray_pid() is not None
        except Exception as e:
            logger.error(f"SIGHUP failed: {e}")
            return False

    def restart_xray(self) -> bool:
        """Kill xray — v2rayN will auto-restart it."""
        if not ENABLE_HARD_HEAL:
            logger.error(
                "Hard heal skipped; set VPN_WATCHDOG_ALLOW_HARD_HEAL=1 "
                "to allow SIGTERM of local xray."
            )
            return False

        guard_ok, guard_reason = provider_guard_allows_heal(require_fresh=True)
        if not guard_ok:
            logger.warning(f"Hard heal blocked by provider guard: {guard_reason}")
            return False

        pid = get_xray_pid()
        if not pid:
            logger.error("xray not running, v2rayN should restart it")
            return False
        try:
            os.kill(pid, signal.SIGTERM)
            logger.warning(f"Killed xray PID {pid} — v2rayN will restart")
            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"Kill xray failed: {e}")
            return False

    def heal(self, reason: str):
        guard_ok, guard_reason = provider_guard_allows_heal()
        if not guard_ok:
            logger.warning(f"Heal blocked by provider guard: {guard_reason}; reason={reason}")
            return

        if not self._can_heal():
            secs_left = int(HEAL_COOLDOWN_SEC - (time.monotonic() - self._last_heal))
            logger.info(f"Heal skipped (cooldown {secs_left}s remaining): {reason}")
            return

        logger.warning(f"=== HEALING: {reason} ===")
        self._last_heal = time.monotonic()
        self._heal_count += 1
        _metrics.heal_count = self._heal_count
        _metrics.last_heal_timestamp = time.time()

        # Step 1: force-close stuck TCP states
        self.force_close_stale()

        # Step 2: SIGHUP for graceful reload
        if not self.sighup_xray():
            logger.warning("SIGHUP failed or xray died — checking hard-heal gate")
            if self.restart_xray():
                time.sleep(8)

        # Step 3: verify recovery
        ok, latency = check_proxy_health()
        if ok:
            logger.info(f"Recovery successful, proxy latency {latency:.0f}ms")
        else:
            logger.error("Recovery failed — proxy still unhealthy after healing")


# ── Main Loop ──────────────────────────────────────────────────────────────────

class VPNWatchdog:
    def __init__(self):
        self.healer = VPNHealer()
        self._stop = threading.Event()
        self._proxy_failures = 0
        self._packet_loss_failures = 0
        self._stale_state_failures = 0
        self._preemptive_cleanup_failures = 0

    def stop(self):
        self._stop.set()

    def run(self):
        logger.info(
            f"VPN Watchdog started | server={VPN_SERVER}:{VPN_PORT} "
            f"| socks={SOCKS_HOST}:{SOCKS_PORT} candidates={SOCKS_PORT_CANDIDATES} "
            f"| interval={CHECK_INTERVAL_SEC}s | heal_enabled={ENABLE_HEAL}"
        )
        start_metrics_server()

        while not self._stop.is_set():
            try:
                self._check_cycle()
            except Exception as e:
                logger.error(f"Check cycle error: {e}")
            self._stop.wait(CHECK_INTERVAL_SEC)

    def _check_cycle(self):
        _metrics.check_count += 1

        # 1. Connection states
        states = check_connection_states()
        fw2 = states["FIN-WAIT-2"]
        cw = states["CLOSE-WAIT"]
        estab = states["ESTAB"]
        _metrics.fin_wait2_count = fw2
        _metrics.close_wait_count = cw
        _metrics.established_count = estab

        if fw2 > 10 or cw > 5:
            logger.warning(
                f"Connection leak: FIN-WAIT-2={fw2} CLOSE-WAIT={cw} ESTAB={estab}"
            )
        else:
            logger.info(f"Connections: ESTAB={estab} FIN-WAIT-2={fw2} CLOSE-WAIT={cw}")

        # 2. Proxy health
        proxy_ok, latency = check_proxy_health()
        _metrics.proxy_healthy = 1 if proxy_ok else 0
        _metrics.proxy_latency_ms = latency
        if proxy_ok:
            self._proxy_failures = 0
            logger.info(f"Proxy healthy, latency={latency:.0f}ms")
        else:
            self._proxy_failures += 1
            logger.error(
                "Proxy UNHEALTHY — cannot reach internet through SOCKS5 "
                f"(failure {self._proxy_failures}/{PROXY_HEAL_FAILURES})"
            )
        _metrics.proxy_failure_streak = self._proxy_failures

        # 3. Decide on healing
        heal_reason = None
        stale_state_over_threshold = fw2 >= FIN_WAIT2_THRESHOLD or cw >= CLOSE_WAIT_THRESHOLD
        if stale_state_over_threshold:
            self._stale_state_failures += 1
        else:
            self._stale_state_failures = 0
        _metrics.stale_state_failure_streak = self._stale_state_failures

        if fw2 >= FIN_WAIT2_THRESHOLD and self._stale_state_failures >= STALE_STATE_HEAL_FAILURES:
            heal_reason = (
                f"FIN-WAIT-2 count {fw2} >= threshold {FIN_WAIT2_THRESHOLD} "
                f"for {self._stale_state_failures} consecutive checks"
            )
        elif cw >= CLOSE_WAIT_THRESHOLD and self._stale_state_failures >= STALE_STATE_HEAL_FAILURES:
            heal_reason = (
                f"CLOSE-WAIT count {cw} >= threshold {CLOSE_WAIT_THRESHOLD} "
                f"for {self._stale_state_failures} consecutive checks"
            )
        elif not proxy_ok and self._proxy_failures >= PROXY_HEAL_FAILURES:
            heal_reason = f"Proxy health check failed {self._proxy_failures} consecutive times"

        if heal_reason and ENABLE_HEAL:
            self.healer.heal(heal_reason)
        elif heal_reason:
            logger.warning(f"Heal disabled by VPN_WATCHDOG_ENABLE_HEAL=false: {heal_reason}")
        elif fw2 > 20 or cw > 10:
            self._preemptive_cleanup_failures += 1
            if ENABLE_HEAL and self._preemptive_cleanup_failures >= PREEMPTIVE_CLEANUP_FAILURES:
                logger.info(
                    f"Preemptive cleanup after {self._preemptive_cleanup_failures} "
                    f"consecutive elevated stale-state checks: FIN-WAIT-2={fw2} CLOSE-WAIT={cw}"
                )
                self.healer.force_close_stale()
                self._preemptive_cleanup_failures = 0
            else:
                logger.info(
                    f"Preemptive cleanup deferred: FIN-WAIT-2={fw2} CLOSE-WAIT={cw} "
                    f"(elevated {self._preemptive_cleanup_failures}/{PREEMPTIVE_CLEANUP_FAILURES}, "
                    f"heal_enabled={ENABLE_HEAL})"
                )
        else:
            self._preemptive_cleanup_failures = 0

        # 4. Packet loss (less frequent — every 6 cycles = 60s)
        if _metrics.check_count % 6 == 0:
            loss = check_packet_loss()
            _metrics.packet_loss_pct = loss
            if loss >= PACKET_LOSS_HEAL_PCT:
                self._packet_loss_failures += 1
                _metrics.packet_loss_failure_streak = self._packet_loss_failures
                logger.error(
                    f"Critical packet loss {loss:.0f}% to {VPN_SERVER} "
                    f"(failure {self._packet_loss_failures}/{PACKET_LOSS_HEAL_FAILURES})"
                )
                if ENABLE_HEAL and self._packet_loss_failures >= PACKET_LOSS_HEAL_FAILURES:
                    self.healer.heal(
                        f"Packet loss {loss:.0f}% >= {PACKET_LOSS_HEAL_PCT}% "
                        f"for {self._packet_loss_failures} consecutive packet-loss checks"
                    )
                else:
                    logger.warning(
                        "Packet-loss heal deferred "
                        f"(heal_enabled={ENABLE_HEAL}, streak={self._packet_loss_failures})"
                    )
            elif loss >= PACKET_LOSS_WARN_PCT:
                self._packet_loss_failures = 0
                _metrics.packet_loss_failure_streak = 0
                logger.warning(f"High packet loss {loss:.0f}% to {VPN_SERVER}")
            else:
                self._packet_loss_failures = 0
                _metrics.packet_loss_failure_streak = 0
                logger.info(f"Packet loss {loss:.0f}%")


def main():
    watchdog = VPNWatchdog()

    def _signal_handler(sig, frame):
        logger.info("Stopping VPN Watchdog...")
        watchdog.stop()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    watchdog.run()


if __name__ == "__main__":
    main()
