#!/bin/bash
# x0tta6bl4 Zero-Config Client
# Automates mesh connection and resource access

set -e

# Configuration
PROJECT_DIR="/mnt/projects"
PROXY_PORT=1080
EXIT_NODE="89.125.1.107:10809"
REMOTE_API="http://89.125.1.107:8081"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}       x0tta6bl4 AUTO-PILOT | ZERO-CONFIG CLIENT${NC}"
echo -e "${BLUE}============================================================${NC}"

# 1. Start/Check Proxy
check_proxy() {
    if netstat -tuln | grep -q ":$PROXY_PORT "; then
        echo -e "${GREEN}✅ Mesh Proxy is already running on port $PROXY_PORT${NC}"
    else
        echo -e "${YELLOW}🚀 Starting Production Mesh Bridge...${NC}"
        export PYTHONPATH=$PYTHONPATH:$PROJECT_DIR
        # Configure bootstrap to point to our remote VPS Exit Node
        export BOOTSTRAP_NODES="89.125.1.107:10809:node-vps1"
        export ENVIRONMENT="production"
        
        python3 -m src.network.mesh_vpn_bridge --port $PROXY_PORT > /tmp/x0t_client_bridge.log 2>&1 &
        sleep 5
        if netstat -tuln | grep -q ":$PROXY_PORT "; then
            echo -e "${GREEN}✅ Production Mesh Bridge started successfully.${NC}"
            echo -e "${BLUE}🔗 Bootstrapped from 89.125.1.107 (node-vps1)${NC}"
        else
            echo -e "${RED}❌ Failed to start Bridge. Check /tmp/x0t_client_bridge.log${NC}"
            exit 1
        fi
    fi
}

show_menu() {
    echo ""
    echo -e "${YELLOW}--- MAIN MENU ---${NC}"
    echo "1. 🧠 AI Prediction (GraphSAGE Anomaly Check)"
    echo "2. 🏛️ DAO Governance (Cast Vote)"
    echo "3. 🛡️ PQC Security (Quantum Handshake)"
    echo "4. 📊 Open Lotus Dashboard (Browser)"
    echo "5. 📈 Check Connection Stats"
    echo "6. 🛑 Stop Proxy & Exit"
    echo "q. Exit (Keep Proxy Running)"
    echo ""
    read -p "Select option: " opt
}

# --- Actions ---

do_ai_predict() {
    echo -e "${BLUE}📡 Querying GraphSAGE AI...${NC}"
    curl -s -x socks5://127.0.0.1:$PROXY_PORT $REMOTE_API/ai/predict/master | python3 -m json.tool || echo -e "${RED}Error fetching AI result${NC}"
}

do_dao_vote() {
    echo -e "${BLUE}🏛️ Participating in Governance...${NC}"
    read -p "Enter Proposal ID (default 1): " pid
    pid=${pid:-1}
    curl -s -x socks5://127.0.0.1:$PROXY_PORT -X POST $REMOTE_API/dao/vote \
         -H "Content-Type: application/json" \
         -d "{\"proposal_id\": \"$pid\", \"voter_id\": \"user_pc\", \"vote\": true, \"tokens\": 100}" | python3 -m json.tool || echo -e "${RED}Vote failed${NC}"
}

do_pqc_handshake() {
    echo -e "${BLUE}🛡️ Performing Quantum Handshake (Kyber768)...${NC}"
    curl -s -x socks5://127.0.0.1:$PROXY_PORT -X POST $REMOTE_API/security/handshake \
         -H "Content-Type: application/json" \
         -d "{\"node_id\": \"user_pc\", \"algorithm\": \"Kyber768\"}" | python3 -m json.tool || echo -e "${RED}Handshake failed${NC}"
}

do_open_dashboard() {
    echo -e "${GREEN}🌍 Opening Lotus Blossom Dashboard...${NC}"
    echo -e "${YELLOW}Ensure your system proxy is set to 127.0.0.1:$PROXY_PORT${NC}"
    # Using xdg-open if in desktop env, otherwise just print URL
    if command -v xdg-open > /dev/null; then
        xdg-open "$REMOTE_API"
    else
        echo -e "Copy this URL to your proxied browser: ${BLUE}$REMOTE_API${NC}"
    fi
}

do_stats() {
    echo -e "${BLUE}📊 Connection Health:${NC}"
    curl -s -x socks5://127.0.0.1:$PROXY_PORT $REMOTE_API/health | python3 -m json.tool
    echo -e "${YELLOW}Your current Exit IP:${NC}"
    curl -s -x socks5://127.0.0.1:$PROXY_PORT https://ifconfig.me && echo ""
}

# --- Execution ---
chmod +x $PROJECT_DIR/scripts/x0t-sysproxy.sh
check_proxy

# Auto-enable system proxy on start
$PROJECT_DIR/scripts/x0t-sysproxy.sh on

while true; do
    show_menu
    case $opt in
        1) do_ai_predict ;;
        2) do_dao_vote ;;
        3) do_pqc_handshake ;;
        4) do_open_dashboard ;;
        5) do_stats ;;
        6) 
            $PROJECT_DIR/scripts/x0t-sysproxy.sh off
            pkill -f "mesh_vpn_bridge" && echo "Proxy stopped." && exit 0 
            ;;
        q) 
            echo -e "${YELLOW}Exiting UI... Proxy and System-wide routing remain ACTIVE.${NC}"
            exit 0 
            ;;
        *) echo "Invalid option." ;;
    esac
    read -p "Press Enter to continue..."
done
