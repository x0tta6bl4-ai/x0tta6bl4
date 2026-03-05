#!/usr/bin/env python3
"""
x0tta6bl4 Self-Healing Daemon
Monitors singbox_tun latency AND VPN proxy health.
Triggers healing when latency exceeds 150ms, packet loss occurs, or proxy is unhealthy.
"""

import os
import signal
import subprocess
import time
import logging
from datetime import datetime

# Configuration
INTERFACE = "singbox_tun"
TEST_TARGET = "8.8.8.8"
MAX_LATENCY_MS = 150.0
CHECK_INTERVAL_SEC = 5
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 10808

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MAPE-K Self-Healing] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/tmp/healing.log"),
        logging.StreamHandler()
    ]
)

_consecutive_failures = 0
_healing_attempts_count = 0
_last_heal_time = 0.0
_HEAL_COOLDOWN = 60


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
    import socket
    try:
        with socket.create_connection((SOCKS_HOST, SOCKS_PORT), timeout=3) as s:
            s.send(b"\x05\x01\x00")
            resp = s.recv(2)
            return resp == b"\x05\x00"
    except Exception:
        return False


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

    now = time.monotonic()
    if (now - _last_heal_time) < _HEAL_COOLDOWN:
        logging.warning(f"Healing skipped (cooldown): {reason}")
        return

    logging.warning(f"=== Triggering healing Stage {min(_healing_attempts_count + 1, 4)}: {reason} ===")
    _last_heal_time = now
    _healing_attempts_count += 1

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


def run_daemon():
    global _consecutive_failures

    logging.info(f"Started monitoring interface {INTERFACE} → target {TEST_TARGET}")

    # Ensure heal_now.py exists
    heal_script = "/mnt/projects/heal_now.py"
    if not os.path.exists(heal_script):
        with open(heal_script, "w") as f:
            f.write("print('Simulating route rebuild... Done.')\n")

    while True:
        latency = ping_target(TEST_TARGET, INTERFACE)
        proxy_ok = check_proxy_health()
        fw2 = get_fin_wait2_count()

        if latency == float('inf'):
            _consecutive_failures += 1
            logging.error(f"Packet loss detected! (failure #{_consecutive_failures})")
            if _consecutive_failures >= 2:
                trigger_healing("Sustained packet loss")
        elif latency > MAX_LATENCY_MS:
            logging.warning(f"High latency: {latency}ms (limit: {MAX_LATENCY_MS}ms)")
            trigger_healing(f"Latency {latency:.0f}ms > {MAX_LATENCY_MS}ms")
            _consecutive_failures = 0
        else:
            _consecutive_failures = 0
            logging.info(f"Network OK | latency={latency:.1f}ms | proxy={'OK' if proxy_ok else 'FAIL'} | FIN-WAIT-2={fw2}")

        if not proxy_ok:
            trigger_healing("SOCKS5 proxy health check failed")

        if fw2 >= 50:
            trigger_healing(f"FIN-WAIT-2 spike: {fw2} connections")

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    run_daemon()
