#!/bin/bash
# Emergency VPN heal script: kill stale TCP connections, reload xray
set -euo pipefail

VPN_SERVER="${VPN_SERVER:-89.125.1.107}"

echo "=== VPN Emergency Heal ==="
echo "Target: $VPN_SERVER"

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
if python3 -c "
import socket, sys
try:
    with socket.create_connection(('127.0.0.1', 10808), timeout=3) as s:
        s.send(b'\x05\x01\x00')
        resp = s.recv(2)
        if resp == b'\x05\x00':
            print('  Proxy OK (SOCKS5 handshake success)')
            sys.exit(0)
        else:
            print(f'  Proxy ERROR: unexpected response {resp.hex()}')
            sys.exit(1)
except Exception as e:
    print(f'  Proxy UNREACHABLE: {e}')
    sys.exit(1)
" 2>&1; then
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
