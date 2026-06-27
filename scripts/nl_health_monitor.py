#!/usr/bin/env python3
"""NL VPS Health Monitor — run every 5 minutes via cron."""
import json, subprocess, sys
from datetime import datetime, timezone

HOST = "nl"
CHECKS = [
    ("SPIRE Server", ["systemctl", "is-active", "spire-server"]),
    ("SPIRE Agent", ["systemctl", "is-active", "spire-agent"]),
    ("Mesh Node 1", ["systemctl", "is-active", "mesh-node"]),
    ("Mesh Node 2", ["systemctl", "is-active", "mesh-node-2"]),
    ("Ghost Beta", ["systemctl", "is-active", "ghost-access-nl-beta"]),
    ("Ghost HTTPS WS", ["systemctl", "is-active", "ghost-access-nl-https-ws"]),
    ("Ghost XHTTP", ["systemctl", "is-active", "ghost-access-nl-xhttp"]),
    ("Ghost VPN", ["systemctl", "is-active", "ghost-vpn"]),
    ("Ghost TCP Bridge", ["systemctl", "is-active", "ghost-tcp-bridge"]),
    ("x-ui", ["systemctl", "is-active", "x-ui"]),
]

def ssh(cmd):
    try:
        r = subprocess.run(["ssh", HOST] + cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), -1

def check_port(port):
    out, rc = ssh(["sh", "-c", f"ss -tlnp | grep -q {port} && echo ok || echo closed"])
    return out == "ok"

def check_health_port(port):
    out, rc = ssh(["curl", "-sf", f"http://127.0.0.1:{port}/health"])
    if rc == 0:
        try:
            return json.loads(out)
        except:
            return None
    return None

results = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "healthy", "services": {}, "mesh": {}, "ports": {}}

all_ok = True
for name, cmd in CHECKS:
    out, rc = ssh(cmd)
    ok = out == "active"
    results["services"][name] = {"status": out, "ok": ok}
    if not ok:
        all_ok = False

# Mesh health
for node_id, port in [("nl-node-1", 9100), ("nl-node-2", 9101)]:
    health = check_health_port(port)
    results["mesh"][node_id] = health if health else {"error": "unreachable"}
    if not health:
        all_ok = False

# Port checks
for port in [9100, 9101, 2443, 443, 80, 628]:
    results["ports"][str(port)] = "open" if check_port(port) else "closed"

results["status"] = "healthy" if all_ok else "degraded"
print(json.dumps(results, indent=2, ensure_ascii=False))
sys.exit(0 if all_ok else 1)
