#!/bin/bash
# VPN status dashboard: connections, proxy health, packet loss
VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
VPN_PORT="${VPN_PORT:-39829}"
SOCKS_HOST="${VPN_SOCKS_HOST:-127.0.0.1}"
SOCKS_PORT="${VPN_SOCKS_PORT:-10808}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }

echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━ VPN Status ━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Server: ${BOLD}$VPN_SERVER:$VPN_PORT${NC}  |  SOCKS5: ${BOLD}$SOCKS_HOST:$SOCKS_PORT${NC}"
echo -e "${CYAN}──────────────────────────────────────────────────────────────${NC}"

# 1. xray process
echo -e "\n${BOLD}[1] xray Process${NC}"
XRAY_PID=$(pgrep -f "xray run" 2>/dev/null | head -1 || true)
if [ -n "$XRAY_PID" ]; then
    XRAY_MEM=$(ps -o rss= -p "$XRAY_PID" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "?")
    ok "Running (PID $XRAY_PID, mem: $XRAY_MEM)"
else
    fail "xray not running"
fi

# 2. sing-box / TUN interface
echo -e "\n${BOLD}[2] TUN Interface${NC}"
if ip link show singbox_tun &>/dev/null; then
    TUN_ADDR=$(ip addr show singbox_tun 2>/dev/null | grep "inet " | awk '{print $2}' || echo "?")
    ok "singbox_tun up — addr: $TUN_ADDR"
else
    fail "singbox_tun not found"
fi

# 3. TCP connection states
echo -e "\n${BOLD}[3] TCP Connections to $VPN_SERVER${NC}"
SS_OUT=$(ss -tn "dst $VPN_SERVER" 2>/dev/null || true)
FW2=$(echo "$SS_OUT" | grep -c "FIN-WAIT-2" || true)
CW=$(echo "$SS_OUT"  | grep -c "CLOSE-WAIT" || true)
EST=$(echo "$SS_OUT" | grep -c "ESTAB"       || true)

echo "  ESTAB=${BOLD}$EST${NC}  FIN-WAIT-2=${BOLD}$FW2${NC}  CLOSE-WAIT=${BOLD}$CW${NC}"
[ "$EST"  -gt 0  ] && ok "Active connections: $EST"
[ "$FW2"  -ge 50 ] && fail "FIN-WAIT-2 critical: $FW2 (threshold 50)" || \
[ "$FW2"  -ge 10 ] && warn "FIN-WAIT-2 elevated: $FW2" || \
[ "$FW2"  -gt 0  ] && ok "FIN-WAIT-2 nominal: $FW2"
[ "$CW"   -ge 30 ] && fail "CLOSE-WAIT critical: $CW" || \
[ "$CW"   -gt 0  ] && warn "CLOSE-WAIT: $CW"

# 4. SOCKS5 proxy health
echo -e "\n${BOLD}[4] SOCKS5 Proxy Health${NC}"
PROXY_RESULT=$(python3 -c "
import socket, time, sys
try:
    t0 = time.monotonic()
    with socket.create_connection(('$SOCKS_HOST', $SOCKS_PORT), timeout=3) as s:
        s.send(b'\x05\x01\x00')
        resp = s.recv(2)
        lat = (time.monotonic() - t0) * 1000
        if resp == b'\x05\x00':
            print(f'OK {lat:.0f}')
        else:
            print(f'FAIL_RESP {resp.hex()}')
except Exception as e:
    print(f'FAIL_CONN {e}')
" 2>/dev/null)

if [[ "$PROXY_RESULT" == OK* ]]; then
    LAT="${PROXY_RESULT#OK }"
    ok "SOCKS5 alive — handshake latency: ${LAT}ms"
else
    fail "SOCKS5 unreachable: $PROXY_RESULT"
fi

# 5. External IP check through proxy
echo -e "\n${BOLD}[5] External Connectivity${NC}"
EXT_IP=$(curl -s --max-time 8 --proxy "socks5h://$SOCKS_HOST:$SOCKS_PORT" https://api.ipify.org 2>/dev/null || true)
if [[ "$EXT_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    if [ "$EXT_IP" != "$VPN_SERVER" ]; then
        ok "Internet reachable via VPN — exit IP: ${BOLD}$EXT_IP${NC}"
    else
        warn "Exit IP matches VPN server: $EXT_IP"
    fi
else
    fail "Cannot reach internet through proxy"
fi

# 6. Packet loss
echo -e "\n${BOLD}[6] Packet Loss to VPN Server${NC}"
PING_OUT=$(ping -c 5 -W 2 -q "$VPN_SERVER" 2>/dev/null || true)
LOSS=$(echo "$PING_OUT" | grep -oP '\d+(?=% packet loss)' || echo "?")
RTT=$(echo "$PING_OUT"  | grep -oP 'rtt.*= \K[\d.]+(?=/)' || echo "?")
if [ "$LOSS" = "0" ]; then
    ok "No packet loss | RTT min: ${RTT}ms"
elif [ "$LOSS" = "?" ]; then
    warn "Ping unavailable"
elif [ "$LOSS" -ge 50 ]; then
    fail "Critical packet loss: ${LOSS}%"
elif [ "$LOSS" -ge 20 ]; then
    warn "High packet loss: ${LOSS}%"
else
    warn "Packet loss: ${LOSS}%"
fi

# 7. Watchdog metrics (if running)
echo -e "\n${BOLD}[7] Watchdog Metrics${NC}"
WD_OUT=$(curl -s --max-time 2 http://127.0.0.1:9091/metrics 2>/dev/null || true)
if [ -n "$WD_OUT" ]; then
    HEAL_CNT=$(echo "$WD_OUT" | grep "^vpn_heal_total " | awk '{print $2}' || echo "?")
    CHK_CNT=$(echo  "$WD_OUT" | grep "^vpn_checks_total " | awk '{print $2}' || echo "?")
    ok "Watchdog running — checks: $CHK_CNT, heals: $HEAL_CNT"
else
    warn "Watchdog not running (start: python3 src/network/vpn_watchdog.py)"
fi

echo -e "\n${CYAN}──────────────────────────────────────────────────────────────${NC}"
echo -e "  Quick actions:"
echo -e "    ${YELLOW}bash scripts/vpn_heal.sh${NC}           — emergency heal"
echo -e "    ${YELLOW}python3 src/network/vpn_watchdog.py${NC} — start watchdog"
echo -e "    ${YELLOW}curl --proxy socks5h://127.0.0.1:10808 https://api.ipify.org${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
