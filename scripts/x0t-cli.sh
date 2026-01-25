#!/bin/bash
# x0tta6bl4 VPN CLI

PROJECT_DIR="/mnt/AC74CC2974CBF3DC"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

case "$1" in
    start)
        echo -e "${BLUE}🚀 Starting x0tta6bl4 VPN...${NC}"
        cd "$PROJECT_DIR"
        
        # Start bridge in background
        nohup python3 -m src.network.mesh_vpn_bridge > /tmp/x0t_vpn.log 2>&1 &
        echo $! > /tmp/x0t_vpn.pid
        sleep 2
        
        if ps -p $(cat /tmp/x0t_vpn.pid) > /dev/null; then
            echo -e "${GREEN}✅ VPN Bridge active (PID: $(cat /tmp/x0t_vpn.pid))${NC}"
            echo "   SOCKS5: 127.0.0.1:10809"
            echo "   Web Dashboard: http://127.0.0.1:8080 (need to start dashboard separately)"
        else
            echo "❌ Failed to start VPN bridge. Check /tmp/x0t_vpn.log"
        fi
        ;;
    
    stop)
        echo -e "${BLUE}🛑 Stopping x0tta6bl4 VPN...${NC}"
        if [ -f /tmp/x0t_vpn.pid ]; then
            kill $(cat /tmp/x0t_vpn.pid)
            rm /tmp/x0t_vpn.pid
            echo -e "${GREEN}✅ VPN stopped.${NC}"
        else
            echo "VPN is not running."
        fi
        ;;
    
    status)
        echo -e "${BLUE}📊 VPN Status:${NC}"
        if [ -f /tmp/x0t_vpn.pid ] && ps -p $(cat /tmp/x0t_vpn.pid) > /dev/null; then
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
        # In real CLI, we would query the dashboard API or local DB
        # For demo, we grep the logs
        if [ -f /tmp/x0t_vpn.log ]; then
            grep "Reward queued" /tmp/x0t_vpn.log | tail -n 5
        else
            echo "No earnings logs found."
        fi
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
