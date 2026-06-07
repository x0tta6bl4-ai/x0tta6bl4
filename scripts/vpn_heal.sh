#!/bin/bash
# Emergency VPN heal script: kill stale TCP connections, reload xray
set -euo pipefail

VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
SOCKS_HOST="${VPN_SOCKS_HOST:-127.0.0.1}"

detect_socks_port() {
    VPN_SOCKS_HOST="$SOCKS_HOST" python3 - <<'PY'
import os
import socket
import sys

host = os.environ.get("VPN_SOCKS_HOST", "127.0.0.1")
ports = []
for value in (
    os.environ.get("VPN_SOCKS_PORT"),
    os.environ.get("SOCKS_PORT"),
    os.environ.get("VPN_SOCKS_PORT_CANDIDATES", "10818,10918,10808,10809,10924,40467,1080"),
):
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

for port in ports:
    try:
        with socket.create_connection((host, port), timeout=1.0) as s:
            s.send(b"\x05\x01\x00")
            if s.recv(2) == b"\x05\x00":
                print(port)
                sys.exit(0)
    except OSError:
        pass

sys.exit(1)
PY
}

if [ -n "${VPN_SOCKS_PORT:-}" ]; then
    SOCKS_PORT="$VPN_SOCKS_PORT"
else
    SOCKS_PORT="$(detect_socks_port 2>/dev/null || echo 10918)"
fi

echo "=== VPN Emergency Heal ==="
echo "Target: $VPN_SERVER"
echo "SOCKS5: $SOCKS_HOST:$SOCKS_PORT"

FW2_BEFORE=$(ss -tn "dst $VPN_SERVER" 2>/dev/null | grep -c "FIN-WAIT-2" || true)
CW_BEFORE=$(ss -tn "dst $VPN_SERVER" 2>/dev/null | grep -c "CLOSE-WAIT" || true)
if VPN_SOCKS_HOST="$SOCKS_HOST" VPN_SOCKS_PORT="$SOCKS_PORT" python3 - <<'PY'
import os
import socket
import sys

host = os.environ.get("VPN_SOCKS_HOST", "127.0.0.1")
port = int(os.environ.get("VPN_SOCKS_PORT", "10918"))

try:
    with socket.create_connection((host, port), timeout=3) as s:
        s.send(b'\x05\x01\x00')
        sys.exit(0 if s.recv(2) == b'\x05\x00' else 1)
except Exception:
    sys.exit(1)
PY
then
    PROXY_BEFORE="ok"
else
    PROXY_BEFORE="fail"
fi

echo "Preflight: FIN-WAIT-2=$FW2_BEFORE CLOSE-WAIT=$CW_BEFORE proxy=$PROXY_BEFORE"
if [ "${VPN_HEAL_FORCE:-0}" != "1" ] && [ "$FW2_BEFORE" -eq 0 ] && [ "$CW_BEFORE" -eq 0 ] && [ "$PROXY_BEFORE" = "ok" ]; then
    echo "No heal needed. Set VPN_HEAL_FORCE=1 to reload xray anyway."
    exit 0
fi

PROVIDER_GUARD_SCRIPT="${VPN_PROVIDER_GUARD_SCRIPT:-/mnt/projects/scripts/vpn_provider_guard.py}"
if [ "${VPN_HEAL_IGNORE_PROVIDER_GUARD:-0}" != "1" ] && [ -f "$PROVIDER_GUARD_SCRIPT" ]; then
    GUARD_ARGS=(--check)
    if [ -n "${VPN_PROVIDER_GUARD_MAX_AGE_SECONDS:-}" ]; then
        GUARD_ARGS+=(--max-age-seconds "$VPN_PROVIDER_GUARD_MAX_AGE_SECONDS")
    fi
    if [ "${VPN_HEAL_REQUIRE_FRESH_SNAPSHOT:-${VPN_HEAL_FORCE:-0}}" = "1" ]; then
        GUARD_ARGS+=(--require-fresh)
    fi
    set +e
    GUARD_OUTPUT=$(python3 "$PROVIDER_GUARD_SCRIPT" "${GUARD_ARGS[@]}" 2>&1)
    GUARD_RC=$?
    set -e
    echo "Provider guard: $GUARD_OUTPUT"
    if [ "$GUARD_RC" -eq 10 ]; then
        echo "Provider guard blocked local heal. Set VPN_HEAL_IGNORE_PROVIDER_GUARD=1 to override manually."
        exit 3
    elif [ "$GUARD_RC" -ne 0 ]; then
        echo "WARNING: provider guard returned rc=$GUARD_RC; continuing because no block was proven."
    fi
fi

# Stage 1: force-close stale TCP states (requires CAP_NET_ADMIN / root)
echo ""
echo "[1/3] Killing stale TCP connections..."
if ss -K dst "$VPN_SERVER" state fin-wait-2 2>/dev/null; then
    echo "  FIN-WAIT-2 connections cleared"
else
    echo "  WARNING: ss -K failed (may need sudo)"
fi

if ss -K dst "$VPN_SERVER" state close-wait 2>/dev/null; then
    echo "  CLOSE-WAIT connections cleared"
fi

# Stage 2: graceful xray reload (SIGHUP keeps connections alive during reload)
echo ""
echo "[2/3] Reloading xray..."
XRAY_PID=$(pgrep -f "xray run" 2>/dev/null | head -1 || true)
if [ -n "$XRAY_PID" ]; then
    kill -SIGHUP "$XRAY_PID"
    echo "  Sent SIGHUP to xray PID $XRAY_PID"
    sleep 3
else
    echo "  WARNING: xray process not found"
fi

# Stage 3: verify proxy is alive
echo ""
echo "[3/3] Checking SOCKS5 proxy health..."
if VPN_SOCKS_HOST="$SOCKS_HOST" VPN_SOCKS_PORT="$SOCKS_PORT" python3 - <<'PY'
import os
import socket
import sys

host = os.environ.get("VPN_SOCKS_HOST", "127.0.0.1")
port = int(os.environ.get("VPN_SOCKS_PORT", "10918"))

try:
    with socket.create_connection((host, port), timeout=3) as s:
        s.send(b'\x05\x01\x00')
        resp = s.recv(2)
        if resp == b'\x05\x00':
            print(f'  Proxy OK at {host}:{port} (SOCKS5 handshake success)')
            sys.exit(0)
        else:
            print(f'  Proxy ERROR: unexpected response {resp.hex()}')
            sys.exit(1)
except Exception as e:
    print(f'  Proxy UNREACHABLE: {e}')
    sys.exit(1)
PY
then
    echo ""
    echo "=== Heal complete. VPN proxy is healthy. ==="
else
    echo ""
    echo "=== Heal complete but proxy still unhealthy. Consider restarting v2rayN. ==="
fi

# Show current connection stats
echo ""
echo "Current connections to $VPN_SERVER:"
ss -tn "dst $VPN_SERVER" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn || true
