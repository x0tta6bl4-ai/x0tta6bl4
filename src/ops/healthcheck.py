#!/usr/bin/env python3
"""x0tta6bl4 healthcheck — runs every 60s via systemd timer.

Checks critical services and sends Telegram alert on failure.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.security.subprocess_validator import safe_run

VPS_IP = os.getenv("X0_VPS_IP", "89.125.1.107")
VPN_PORT = int(os.getenv("X0_VPN_PORT", "443"))
SPIRE_SOCKET = os.getenv("X0_SPIRE_SOCKET", "/opt/spire/sockets/agent.sock")
TELEGRAM_BOT_TOKEN = os.getenv("X0_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("X0_TELEGRAM_CHAT_ID", "")

checks = []


def check(name):
    def decorator(func):
        checks.append((name, func))
        return func
    return decorator


@check("node_process")
def node_process():
    r = safe_run(
        ["systemctl", "is-active", "x0tta6bl4-node"],
        capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() == "active", r.stdout.strip()


@check("vpn_port")
def vpn_port():
    try:
        with socket.create_connection((VPS_IP, VPN_PORT), timeout=3):
            return True, f"port {VPN_PORT} open"
    except Exception as e:
        return False, str(e)[:80]


@check("spire_agent")
def spire_agent():
    r = subprocess.run(
        ["systemctl", "is-active", "spire-agent"],
        capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() == "active", r.stdout.strip()


@check("spire_socket")
def spire_socket():
    p = Path(SPIRE_SOCKET)
    if not p.exists():
        return False, "socket not found"
    return True, f"exists, uid={p.stat().st_uid}"


@check("disk_space")
def disk_space():
    usage = shutil.disk_usage("/")
    free_pct = usage.free / usage.total * 100
    return free_pct > 15, f"{free_pct:.1f}% free"


@check("memory_pressure")
def memory_pressure():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
                    avail_mb = avail_kb / 1024
                    return avail_mb > 200, f"{avail_mb:.0f}MB available"
    except Exception:
        return True, "cannot read meminfo"
    return True, "ok"


@check("load_average")
def load_average():
    try:
        load1, _, _ = os.getloadavg()
        return load1 < 4.0, f"load1={load1:.2f}"
    except Exception:
        return True, "cannot read load"


@check("ghost_bot")
def ghost_bot():
    r = safe_run(
        ["systemctl", "is-active", "ghost-access-bot"],
        capture_output=True, text=True, timeout=5,
    )
    status = r.stdout.strip()
    if status == "active":
        return True, "active"
    return False, status


@check("spire_jwt_svid")
def spire_jwt_svid():
    """Verify JWT-SVID can be fetched from SPIRE agent."""
    spire_agent = os.getenv("X0_SPIRE_AGENT_BIN", "/opt/spire/bin/spire-agent")
    socket_path = os.getenv("X0_SPIRE_SOCKET", "/opt/spire/sockets/agent.sock")

    if not Path(socket_path).exists():
        return False, "socket not found"

    try:
        r = safe_run(
            [spire_agent, "api", "fetch",
             "-socketPath", socket_path,
             "-jwt",
             "-audience", "x0tta6bl4.mesh"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return False, f"rc={r.returncode}: {r.stderr[:60]}"
        if "svid" in r.stdout.lower() or "token" in r.stdout.lower():
            return True, "JWT-SVID fetched"
        return False, "no token in response"
    except Exception as e:
        return False, str(e)[:60]


def send_telegram_alert(failed_checks):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("TELEGRAM: no token/chat_id configured, skipping alert", file=sys.stderr)
        return

    msg = f"🚨 *x0tta6bl4 ALERT*\nVPS: `{VPS_IP}`\n\n"
    for name, ok, info in failed_checks:
        msg += f"❌ `{name}`: {info}\n"

    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()

    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"TELEGRAM ALERT FAILED: {e}", file=sys.stderr)


def main():
    results = {}
    failed = []

    for name, func in checks:
        try:
            ok, info = func()
        except Exception as e:
            ok, info = False, f"EXCEPTION: {e}"

        status = "ok" if ok else "FAIL"
        results[name] = {"ok": ok, "info": info}
        if not ok:
            failed.append((name, ok, info))

        print(f"[{status}] {name}: {info}")

    print(json.dumps(results, ensure_ascii=False))

    if failed:
        send_telegram_alert(failed)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
