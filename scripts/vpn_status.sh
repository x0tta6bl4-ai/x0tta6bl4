#!/bin/bash
# VPN status dashboard: connections, proxy health, packet loss
VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
VPN_PORT="${VPN_PORT:-39829}"
SOCKS_HOST="${VPN_SOCKS_HOST:-127.0.0.1}"
SOCKS_PORT_SOURCE="env"
BOOT_VALIDATION_RESULT="${VPN_BOOT_VALIDATE_RESULT_FILE:-/var/log/x0tta6bl4/vpn_boot_validation.last}"
STRICT_CHECK=0
NO_COLOR=0
JSON_MODE=0

for arg in "$@"; do
    case "$arg" in
        --check)
            STRICT_CHECK=1
            NO_COLOR=1
            ;;
        --json)
            JSON_MODE=1
            NO_COLOR=1
            ;;
        --no-color)
            NO_COLOR=1
            ;;
        -h|--help)
            echo "Usage: $0 [--check] [--json] [--no-color]"
            echo "  --check     reproducible health-check mode; exits 1 on hard failures"
            echo "  --json      emit machine-readable state contract JSON; exits 1 on hard failures"
            echo "  --no-color  disable ANSI color output"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

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
    os.environ.get("VPN_SOCKS_PORT_CANDIDATES", "10918,10808,10809,10924,40467,1080,7890,7891"),
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
    SOCKS_PORT_SOURCE="auto"
    SOCKS_PORT="$(detect_socks_port 2>/dev/null || echo 10918)"
fi

if [ "$JSON_MODE" -eq 1 ]; then
    CHILD_OUTPUT="$(VPN_STATUS_JSON_CHILD=1 "$0" --check --no-color 2>&1)"
    CHILD_STATUS=$?
    VPN_STATUS_OUTPUT="$CHILD_OUTPUT" VPN_STATUS_EXIT_CODE="$CHILD_STATUS" python3 - <<'PY'
import json
import os
import re

text = os.environ.get("VPN_STATUS_OUTPUT", "")
exit_code = int(os.environ.get("VPN_STATUS_EXIT_CODE", "0") or "0")
lines = [line.rstrip() for line in text.splitlines()]

result_line = next((line for line in reversed(lines) if line.startswith("Result: ")), "")
failures = 0
warnings = 0
raw_result = "UNKNOWN"
match = re.search(r"Result:\s+(PASS|FAIL)(?:\s+\(failures=(\d+)\s+warnings=(\d+)\)|\s+\(warnings=(\d+)\))", result_line)
if match:
    raw_result = match.group(1)
    if raw_result == "FAIL":
        failures = int(match.group(2) or 0)
        warnings = int(match.group(3) or 0)
    else:
        warnings = int(match.group(4) or 0)
elif exit_code:
    raw_result = "FAIL"
    failures = 1

warning_lines = [line.strip() for line in lines if "⚠" in line]
problem_lines = [line.strip() for line in lines if "✗" in line]
evidence_lines = [line.strip() for line in lines if "✓" in line]

overall_status = "critical" if failures else ("advisory" if warnings else "ok")
joined_problems = "\n".join(problem_lines).lower()
joined_warnings = "\n".join(warning_lines).lower()

if failures:
    if any(token in joined_problems for token in ("route loop", "socks5 unreachable", "xray not running", "x0tta-node.service not active", "singbox_tun not found", "boot validation fail")):
        failure_domain = "local_client"
    elif "critical packet loss" in joined_problems:
        failure_domain = "external_network"
    else:
        failure_domain = "unknown"
elif warnings:
    if "packet loss" in joined_warnings and "no packet loss" not in joined_warnings:
        failure_domain = "external_network"
    elif any(token in joined_warnings for token in ("watchdog", "boot validation", "x0tta-node")):
        failure_domain = "local_client"
    else:
        failure_domain = "none"
else:
    failure_domain = "none"

if overall_status in {"ok", "advisory"}:
    recommended_action = "observe"
elif failure_domain == "local_client":
    recommended_action = "local_soft_heal"
elif failure_domain == "external_network":
    recommended_action = "operator_review"
else:
    recommended_action = "operator_review"

transport_status = "healthy"
if failures:
    transport_status = "unhealthy"
elif warnings:
    transport_status = "advisory"

server_match = re.search(r"Server:\s*([0-9.]+):(\d+)\s+\|\s+SOCKS5:\s*([^:]+):(\d+)\s+\(([^)]+)\)", text)
tcp_match = re.search(r"ESTAB=\s*(\d+)\s+FIN-WAIT-2=\s*(\d+)\s+CLOSE-WAIT=\s*(\d+)", text)
loss_match = re.search(r"(?:Critical packet loss|High packet loss|Packet loss):\s*(\d+)%", text)
exit_ip_match = re.search(r"exit IP (?:is VPN server|differs from VPN server):\s*([0-9.]+)", text)

packet_loss_percent = None
if "No packet loss" in text:
    packet_loss_percent = 0
elif loss_match:
    packet_loss_percent = int(loss_match.group(1))

payload = {
    "schema_version": 1,
    "source": "scripts/vpn_status.sh",
    "raw_result": raw_result,
    "overall_status": overall_status,
    "transport_status": transport_status,
    "application_status": "healthy" if failures == 0 else "unhealthy",
    "provider_status": "not_evaluated",
    "failure_domain": failure_domain,
    "recommended_action": recommended_action,
    "mutation_allowed": False,
    "local_mutation_allowed": False,
    "nl_mutation_allowed": False,
    "exit_code": exit_code,
    "failures": failures,
    "warnings": warnings,
    "problems": problem_lines,
    "warnings_detail": warning_lines,
    "evidence": evidence_lines,
}

if server_match:
    payload.update(
        {
            "vpn_server": server_match.group(1),
            "vpn_port": int(server_match.group(2)),
            "socks_host": server_match.group(3),
            "socks_port": int(server_match.group(4)),
            "socks_port_source": server_match.group(5),
        }
    )

if tcp_match:
    payload["tcp_connections"] = {
        "established": int(tcp_match.group(1)),
        "fin_wait_2": int(tcp_match.group(2)),
        "close_wait": int(tcp_match.group(3)),
    }

if packet_loss_percent is not None:
    payload["packet_loss_percent"] = packet_loss_percent
if exit_ip_match:
    payload["exit_ip"] = exit_ip_match.group(1)

if raw_result == "UNKNOWN" and not failures:
    payload["overall_status"] = "critical"
    payload["failure_domain"] = "unknown"
    payload["recommended_action"] = "operator_review"
    payload["problems"].append("Unable to parse vpn_status result line")

print(json.dumps(payload, indent=2, sort_keys=True))
PY
    exit "$CHILD_STATUS"
fi

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
if [ "$NO_COLOR" -eq 1 ]; then
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

FAIL_COUNT=0
WARN_COUNT=0

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); echo -e "  ${YELLOW}⚠${NC} $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo -e "  ${RED}✗${NC} $*"; }

echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━ VPN Status ━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Server: ${BOLD}$VPN_SERVER:$VPN_PORT${NC}  |  SOCKS5: ${BOLD}$SOCKS_HOST:$SOCKS_PORT${NC} ($SOCKS_PORT_SOURCE)"
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

# 2. x0tta-node health loop
echo -e "\n${BOLD}[2] x0tta-node Health Loop${NC}"
if systemctl is-active --quiet x0tta-node.service 2>/dev/null; then
    ok "x0tta-node.service active"
else
    fail "x0tta-node.service not active"
fi

NODE_LOG=$(journalctl -u x0tta-node.service --no-pager --since "2 minutes ago" -n 40 2>/dev/null | grep "Network OK" | tail -1 || true)
if echo "$NODE_LOG" | grep -q "proxy=OK"; then
    ok "Recent health loop OK: $(sed 's/.*Network OK/Network OK/' <<< "$NODE_LOG")"
elif [ -n "$NODE_LOG" ]; then
    warn "Recent x0tta-node health loop did not confirm proxy OK: $NODE_LOG"
else
    warn "No recent x0tta-node Network OK log found"
fi

# 3. sing-box / TUN interface
echo -e "\n${BOLD}[3] TUN Interface${NC}"
if ip link show singbox_tun &>/dev/null; then
    TUN_ADDR=$(ip addr show singbox_tun 2>/dev/null | grep "inet " | awk '{print $2}' || echo "?")
    ok "singbox_tun up — addr: $TUN_ADDR"
else
    fail "singbox_tun not found"
fi

# 4. TCP connection states
echo -e "\n${BOLD}[4] TCP Connections to $VPN_SERVER${NC}"
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

ROUTE_OUT=$(ip route get "$VPN_SERVER" 2>/dev/null | head -1 || true)
if echo "$ROUTE_OUT" | grep -q "singbox_tun"; then
    fail "Route loop risk: VPN server currently resolves via singbox_tun: $ROUTE_OUT"
elif [ -n "$ROUTE_OUT" ]; then
    ok "Route to VPN server bypasses tunnel: $ROUTE_OUT"
else
    fail "Cannot resolve route to VPN server"
fi

# 5. SOCKS5 proxy health
echo -e "\n${BOLD}[5] SOCKS5 Proxy Health${NC}"
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

# 6. External IP check through proxy
echo -e "\n${BOLD}[6] External Connectivity${NC}"
EXT_IP=$(curl -s --max-time 8 --proxy "socks5h://$SOCKS_HOST:$SOCKS_PORT" https://api.ipify.org 2>/dev/null || true)
if [[ "$EXT_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    if [ "$EXT_IP" = "$VPN_SERVER" ]; then
        ok "Internet reachable via VPN — exit IP is VPN server: ${BOLD}$EXT_IP${NC}"
    else
        warn "Internet reachable, but exit IP differs from VPN server: $EXT_IP"
    fi
else
    fail "Cannot reach internet through proxy"
fi

# 7. Packet loss
echo -e "\n${BOLD}[7] Packet Loss to VPN Server${NC}"
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

# 8. Watchdog metrics (if running)
echo -e "\n${BOLD}[8] Watchdog Metrics${NC}"
WD_OUT=$(curl -s --max-time 2 http://127.0.0.1:9091/metrics 2>/dev/null || true)
if [ -n "$WD_OUT" ]; then
    HEAL_CNT=$(echo "$WD_OUT" | grep "^vpn_heal_total " | awk '{print $2}' || echo "?")
    CHK_CNT=$(echo  "$WD_OUT" | grep "^vpn_checks_total " | awk '{print $2}' || echo "?")
    ok "Watchdog running — checks: $CHK_CNT, heals: $HEAL_CNT"
else
    warn "Watchdog not running (start: python3 src/network/vpn_watchdog.py)"
fi

# 9. Post-boot validation evidence
echo -e "\n${BOLD}[9] Post-Boot Validation${NC}"
if systemctl is-enabled --quiet x0tta-vpn-boot-validate.timer 2>/dev/null; then
    ok "x0tta-vpn-boot-validate.timer enabled"
else
    warn "x0tta-vpn-boot-validate.timer not enabled"
fi

CURRENT_BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo "")
if [ -r "$BOOT_VALIDATION_RESULT" ]; then
    BV_STATUS=$(grep '^status=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
    BV_BOOT_ID=$(grep '^boot_id=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
    BV_TIMESTAMP=$(grep '^timestamp=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
    BV_DETAIL=$(grep '^detail=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)

    if [ "$BV_BOOT_ID" = "$CURRENT_BOOT_ID" ] && [ "$BV_STATUS" = "PASS" ]; then
        ok "Boot validation PASS for current boot — $BV_TIMESTAMP ($BV_DETAIL)"
    elif [ "$BV_BOOT_ID" = "$CURRENT_BOOT_ID" ] && [ "$BV_STATUS" = "FAIL" ]; then
        fail "Boot validation FAIL for current boot — $BV_TIMESTAMP ($BV_DETAIL)"
    elif [ -n "$BV_STATUS" ]; then
        warn "Boot validation result is not for current boot — status=$BV_STATUS timestamp=$BV_TIMESTAMP"
    else
        warn "Boot validation result is unreadable: $BOOT_VALIDATION_RESULT"
    fi
else
    warn "Boot validation result not found: $BOOT_VALIDATION_RESULT"
fi

echo -e "\n${CYAN}──────────────────────────────────────────────────────────────${NC}"
echo -e "  Quick actions:"
echo -e "    ${YELLOW}bash scripts/vpn_heal.sh${NC}           — emergency heal"
echo -e "    ${YELLOW}python3 src/network/vpn_watchdog.py${NC} — start watchdog"
echo -e "    ${YELLOW}curl --proxy socks5h://$SOCKS_HOST:$SOCKS_PORT https://api.ipify.org${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "Result: PASS (warnings=$WARN_COUNT)"
else
    echo "Result: FAIL (failures=$FAIL_COUNT warnings=$WARN_COUNT)"
fi

if [ "$STRICT_CHECK" -eq 1 ] && [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

exit 0
