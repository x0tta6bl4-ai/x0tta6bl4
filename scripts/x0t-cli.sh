#!/usr/bin/env bash
# x0tta6bl4 VPN CLI

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${X0T_PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RUNTIME_DIR="${X0T_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
PID_FILE="${X0T_VPN_PID_FILE:-$RUNTIME_DIR/x0t_vpn.pid}"
LOG_FILE="${X0T_VPN_LOG_FILE:-$RUNTIME_DIR/x0t_vpn.log}"
STATS_FILE="${X0T_VPN_STATS_FILE:-$PROJECT_DIR/node_stats.json}"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

is_running() {
    [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1
}

show_earnings() {
    if [ -f "$STATS_FILE" ]; then
        python3 - "$STATS_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open(encoding="utf-8") as f:
    stats = json.load(f)

print(f"Node: {stats.get('node_id', 'unknown')}")
print(f"Earnings Today: {stats.get('earnings_today', '0.0')} X0T")
print(f"Balance: {stats.get('balance', '0.0')} X0T")
print(f"Packets Relayed: {stats.get('packets', 0)}")
print(f"Bytes Relayed: {stats.get('bytes', 0)}")
PY
        return
    fi

    if [ -f "$LOG_FILE" ]; then
        echo "Structured stats not found at $STATS_FILE."
        echo "Recent reward events from $LOG_FILE:"
        grep "Reward queued" "$LOG_FILE" | tail -n 5 || echo "No reward entries found."
        return
    fi

    echo "No earnings data found."
    echo "Expected structured stats at: $STATS_FILE"
}

case "${1:-}" in
    start)
        echo -e "${BLUE}🚀 Starting x0tta6bl4 VPN...${NC}"
        cd "$PROJECT_DIR"
        
        # Start bridge in background
        nohup python3 -m src.network.mesh_vpn_bridge > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        sleep 2
        
        if is_running; then
            echo -e "${GREEN}✅ VPN Bridge active (PID: $(cat "$PID_FILE"))${NC}"
            echo "   SOCKS5: 127.0.0.1:10809"
            echo "   Web Dashboard: http://127.0.0.1:8080 (need to start dashboard separately)"
        else
            echo "❌ Failed to start VPN bridge. Check $LOG_FILE"
        fi
        ;;
    
    stop)
        echo -e "${BLUE}🛑 Stopping x0tta6bl4 VPN...${NC}"
        if [ -f "$PID_FILE" ]; then
            kill "$(cat "$PID_FILE")" 2>/dev/null || true
            rm "$PID_FILE"
            echo -e "${GREEN}✅ VPN stopped.${NC}"
        else
            echo "VPN is not running."
        fi
        ;;
    
    status)
        echo -e "${BLUE}📊 VPN Status:${NC}"
        if is_running; then
            echo -e "${GREEN}● Active (Running)${NC}"
            echo "   IP Check:"
            curl -s --max-time 5 -x socks5://127.0.0.1:10809 http://ifconfig.me || echo "   (Connection failed)"
            echo ""
            python3 -m src.dao.check_balance
        else
            echo "● Inactive"
        fi
        ;;
    
    earnings)
        echo -e "${BLUE}💰 Operator Earnings:${NC}"
        show_earnings
        ;;
        
    dashboard)
        echo -e "${BLUE}📊 Starting Dashboard...${NC}"
        cd "$PROJECT_DIR"
        python3 -m src.web.operator_dashboard
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status|earnings|dashboard}"
        exit 1
        ;;
esac
exit 0
