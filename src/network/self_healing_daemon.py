#!/usr/bin/env python3
"""
x0tta6bl4 Self-Healing Daemon
Monitors singbox_tun latency AND VPN proxy health.
Triggers healing when latency exceeds 150ms, packet loss occurs, or proxy is unhealthy.
"""

import os
import signal
import socket
import subprocess
import sys
import time
import logging

DEFAULT_SOCKS_PORT_CANDIDATES = (10918, 10808, 10809, 10924, 40467, 1080, 7890, 7891)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _socks_handshake(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.send(b"\x05\x01\x00")
            return s.recv(2) == b"\x05\x00"
    except OSError:
        return False


def discover_socks_port() -> int | None:
    for port in SOCKS_PORT_CANDIDATES:
        if _socks_handshake(SOCKS_HOST, port):
            return port
    return None


# Configuration
INTERFACE = os.getenv("INTERFACE", "singbox_tun")
TEST_TARGET = os.getenv("TEST_TARGET", "8.8.8.8")
MAX_LATENCY_MS = float(os.getenv("MAX_LATENCY_MS", "150.0"))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "5"))
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
SOCKS_HOST = os.getenv("VPN_SOCKS_HOST", os.getenv("SOCKS_HOST", "127.0.0.1"))
SOCKS_PORT_CANDIDATES = _parse_ports(
    os.getenv("VPN_SOCKS_PORT"),
    os.getenv("SOCKS_PORT"),
    os.getenv("VPN_SOCKS_PORT_CANDIDATES"),
)
SOCKS_PORT = SOCKS_PORT_CANDIDATES[0]
ENABLE_REALITY_ROTATION = _truthy(os.getenv("VPN_ENABLE_REALITY_ROTATION"))
ENABLE_PULSE_SHIFT = _truthy(os.getenv("VPN_ENABLE_PULSE_SHIFT"))
ENABLE_HEAL = _truthy(os.getenv("VPN_SELF_HEAL_ENABLE"))
PACKET_LOSS_HEAL_FAILURES = int(os.getenv("VPN_PACKET_LOSS_HEAL_FAILURES", "3"))
LATENCY_HEAL_FAILURES = int(os.getenv("VPN_LATENCY_HEAL_FAILURES", "3"))
PROXY_HEAL_FAILURES = int(os.getenv("VPN_PROXY_HEAL_FAILURES", "3"))
FIN_WAIT2_HEAL_FAILURES = int(os.getenv("VPN_FIN_WAIT2_HEAL_FAILURES", "2"))
PROVIDER_GUARD_SCRIPT = os.getenv("VPN_PROVIDER_GUARD_SCRIPT", "/mnt/projects/scripts/vpn_provider_guard.py")
PROVIDER_GUARD_DISABLED = _truthy(os.getenv("VPN_PROVIDER_GUARD_DISABLE"))
PROVIDER_GUARD_REQUIRE_FRESH = _truthy(os.getenv("VPN_PROVIDER_GUARD_REQUIRE_FRESH"))
PROVIDER_GUARD_MAX_AGE_SECONDS = int(os.getenv("VPN_PROVIDER_GUARD_MAX_AGE_SECONDS", "3600"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MAPE-K Self-Healing] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/tmp/healing.log"),
        logging.StreamHandler()
    ]
)

_consecutive_failures = 0
_consecutive_latency_failures = 0
_consecutive_proxy_failures = 0
_consecutive_fin_wait2_failures = 0
_healing_attempts_count = 0
_last_heal_time = 0.0
_HEAL_COOLDOWN = int(os.getenv("VPN_HEAL_COOLDOWN_SEC", os.getenv("VPN_SELF_HEAL_COOLDOWN_SEC", "1800")))


def provider_guard_allows_heal() -> tuple[bool, str]:
    if PROVIDER_GUARD_DISABLED:
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, "provider guard disabled; fresh snapshot required"
        return True, "provider guard disabled"
    if not os.path.exists(PROVIDER_GUARD_SCRIPT):
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, "provider guard unavailable; fresh snapshot required"
        return True, "provider guard unavailable"
    cmd = [
        sys.executable,
        PROVIDER_GUARD_SCRIPT,
        "--check",
        "--max-age-seconds",
        str(PROVIDER_GUARD_MAX_AGE_SECONDS),
    ]
    if PROVIDER_GUARD_REQUIRE_FRESH:
        cmd.append("--require-fresh")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, f"provider guard inconclusive while fresh snapshot is required: {exc}"
        return True, f"provider guard inconclusive: {exc}"
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 10:
        return False, output or "provider guard blocked local heal"
    if result.returncode != 0:
        if PROVIDER_GUARD_REQUIRE_FRESH:
            return False, f"provider guard inconclusive while fresh snapshot is required rc={result.returncode}: {output}"
        return True, f"provider guard inconclusive rc={result.returncode}: {output}"
    return True, output or "provider guard allowed local heal"


def ping_target(target, interface):
    """Ping target through interface, return latency in ms or inf on failure."""
    try:
        cmd = ["ping", "-I", interface, "-c", "1", "-W", "1", target]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in output.splitlines():
            if "time=" in line:
                latency_str = line.split("time=")[1].split(" ")[0]
                return float(latency_str)
        return float('inf')
    except subprocess.CalledProcessError:
        return float('inf')


def check_proxy_health() -> bool:
    """Quick TCP check that SOCKS5 proxy is alive."""
    global SOCKS_PORT

    port = discover_socks_port()
    if port is None:
        return False

    if port != SOCKS_PORT:
        logging.info(f"Detected active SOCKS5 proxy at {SOCKS_HOST}:{port}")
        SOCKS_PORT = port
    return True


def get_fin_wait2_count() -> int:
    """Count FIN-WAIT-2 connections to VPN server."""
    try:
        result = subprocess.run(
            ["ss", "-tn", "dst", VPN_SERVER],
            capture_output=True, text=True, timeout=5
        )
        return sum(1 for line in result.stdout.splitlines() if "FIN-WAIT-2" in line)
    except Exception:
        return 0


def trigger_healing(reason: str):
    """Multi-stage healing: force-close stale connections, SIGHUP, then Rotate Keys."""
    global _last_heal_time, _healing_attempts_count

    if not ENABLE_HEAL:
        logging.warning(f"Healing disabled by VPN_SELF_HEAL_ENABLE=false: {reason}")
        return

    guard_ok, guard_reason = provider_guard_allows_heal()
    if not guard_ok:
        logging.warning(f"Healing blocked by provider guard: {guard_reason}; reason={reason}")
        return

    now = time.monotonic()
    if (now - _last_heal_time) < _HEAL_COOLDOWN:
        logging.warning(f"Healing skipped (cooldown): {reason}")
        return

    logging.warning(f"=== Triggering healing Stage {min(_healing_attempts_count + 1, 5)}: {reason} ===")
    _last_heal_time = now
    _healing_attempts_count += 1

    # Stage 0: optional pulse adaptation. Disabled by default because VPN
    # recovery must not mutate traffic profiles on a single local symptom.
    if _healing_attempts_count == 1 and ENABLE_PULSE_SHIFT:
        logging.info("🧠 MAPE-K: Phase 0 - Transitioning x0tta6bl4_pulse mimicry profile (Dynamic Pulse Shift)...")
        try:
            import json
            cmd_file = "/mnt/projects/.tmp/pulse_cmd.json"
            os.makedirs(os.path.dirname(cmd_file), exist_ok=True)
            with open(cmd_file, "w") as f:
                json.dump({"action": "switch_profile", "target": "vk", "reason": reason}, f)
            logging.info("✅ Pulse shift command issued to mesh daemon.")
            time.sleep(5)
            # Check if pulse shift fixed it
            if ping_target(TEST_TARGET, INTERFACE) != float('inf'):
                logging.info("💪 Pulse Shift SUCCESSFUL. Latency restored via VK-Mimicry.")
                return
        except Exception as e:
            logging.error(f"Pulse shift failed: {e}")
    elif _healing_attempts_count == 1:
        logging.info("Pulse shift skipped; set VPN_ENABLE_PULSE_SHIFT=true to allow it.")

    # Stage 1: force-close stale TCP connections
    for state in ("fin-wait-2", "close-wait"):
        subprocess.run(
            ["ss", "-K", "dst", VPN_SERVER, "state", state],
            timeout=5, capture_output=True
        )

    # Stage 2: SIGHUP xray (graceful reload)
    if _healing_attempts_count == 2:
        try:
            result = subprocess.run(["pgrep", "-f", "xray run"], capture_output=True, text=True)
            pid = result.stdout.strip().split()[0] if result.stdout.strip() else None
            if pid:
                os.kill(int(pid), signal.SIGHUP)
                logging.info(f"Sent SIGHUP to xray PID {pid}")
                time.sleep(3)
        except Exception as e:
            logging.error(f"SIGHUP failed: {e}")

    # Stage 3: run project heal script
    if _healing_attempts_count == 3:
        heal_script = "/mnt/projects/heal_now.py"
        if os.path.exists(heal_script):
            subprocess.run(["python3", heal_script], check=False)

    # Stage 4: CRITICAL - Rotate Reality Keys (Possible IP blocking/GFW detection)
    if _healing_attempts_count >= 4:
        if not ENABLE_REALITY_ROTATION:
            logging.error(
                "Reality key rotation skipped; set VPN_ENABLE_REALITY_ROTATION=true "
                "to allow this destructive recovery step."
            )
            logging.info("Healing iteration complete. Waiting for stabilization.")
            time.sleep(10)
            return

        logging.critical("🚨 Stage 4: Initiating Reality Key Rotation (Self-Healing)")
        try:
            from vpn_config_generator import XUIAPIClient
            xui = XUIAPIClient()
            xui.rotate_reality_credentials()
            logging.info("✅ Reality keys rotated and x-ui restarted.")
            _healing_attempts_count = 0 # Reset after deep healing
        except Exception as e:
            logging.error(f"❌ Critical rotation failed: {e}")

    logging.info("Healing iteration complete. Waiting for stabilization.")
    time.sleep(10)


def check_once():
    """Run one monitoring iteration. Kept separate so thresholds are testable."""
    global _consecutive_failures
    global _consecutive_latency_failures
    global _consecutive_proxy_failures
    global _consecutive_fin_wait2_failures

    latency = ping_target(TEST_TARGET, INTERFACE)
    proxy_ok = check_proxy_health()
    fw2 = get_fin_wait2_count()

    if latency == float('inf'):
        _consecutive_failures += 1
        _consecutive_latency_failures = 0
        logging.error(f"Packet loss detected! (failure #{_consecutive_failures})")
        if _consecutive_failures >= PACKET_LOSS_HEAL_FAILURES:
            trigger_healing(
                f"Sustained packet loss for {_consecutive_failures} checks"
            )
    elif latency > MAX_LATENCY_MS:
        _consecutive_latency_failures += 1
        logging.warning(f"High latency: {latency}ms (limit: {MAX_LATENCY_MS}ms)")
        if _consecutive_latency_failures >= LATENCY_HEAL_FAILURES:
            trigger_healing(
                f"Latency {latency:.0f}ms > {MAX_LATENCY_MS}ms "
                f"for {_consecutive_latency_failures} checks"
            )
        _consecutive_failures = 0
    else:
        _consecutive_failures = 0
        _consecutive_latency_failures = 0
        logging.info(f"Network OK | latency={latency:.1f}ms | proxy={'OK' if proxy_ok else 'FAIL'} | FIN-WAIT-2={fw2}")

    if not proxy_ok:
        _consecutive_proxy_failures += 1
        logging.error(
            f"SOCKS5 proxy health check failed "
            f"({_consecutive_proxy_failures}/{PROXY_HEAL_FAILURES})"
        )
        if _consecutive_proxy_failures >= PROXY_HEAL_FAILURES:
            trigger_healing(
                f"SOCKS5 proxy health check failed for {_consecutive_proxy_failures} checks"
            )
    else:
        _consecutive_proxy_failures = 0

    if fw2 >= 50:
        _consecutive_fin_wait2_failures += 1
        if _consecutive_fin_wait2_failures >= FIN_WAIT2_HEAL_FAILURES:
            trigger_healing(
                f"FIN-WAIT-2 spike: {fw2} connections for "
                f"{_consecutive_fin_wait2_failures} checks"
            )
    else:
        _consecutive_fin_wait2_failures = 0


def run_daemon():
    logging.info(
        f"Started monitoring interface {INTERFACE} → target {TEST_TARGET} "
        f"| socks={SOCKS_HOST}:{SOCKS_PORT} candidates={SOCKS_PORT_CANDIDATES} "
        f"| heal_enabled={ENABLE_HEAL}"
    )

    # Do not create recovery scripts implicitly in production. Missing
    # recovery scripts are reported when that later recovery stage is reached.
    heal_script = "/mnt/projects/heal_now.py"
    if not os.path.exists(heal_script):
        logging.info("Optional heal_now.py script is absent; stage 3 will be skipped if reached.")

    while True:
        check_once()
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    run_daemon()
