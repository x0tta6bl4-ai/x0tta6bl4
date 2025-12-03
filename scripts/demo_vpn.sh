#!/bin/bash
#
# x0tta6bl4 VPN Demo for Investors
# Shows REAL working VPN functionality
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/mnt/AC74CC2974CBF3DC"
PROXY_PORT=1080

echo ""
echo "============================================================"
echo -e "${BLUE}       x0tta6bl4 MESH VPN - LIVE DEMO${NC}"
echo "============================================================"
echo ""

# Step 1: Show current IP
echo -e "${YELLOW}[STEP 1]${NC} Your current IP address:"
REAL_IP=$(curl -s --max-time 5 https://ifconfig.me || echo "Unable to fetch")
echo -e "   ${GREEN}→ $REAL_IP${NC}"
echo ""

# Step 2: Start VPN proxy in background
echo -e "${YELLOW}[STEP 2]${NC} Starting x0tta6bl4 VPN Proxy..."
cd "$PROJECT_DIR"

# Kill any existing proxy
pkill -f "vpn_proxy" 2>/dev/null || true
sleep 1

# Start proxy in background
python3 -m src.network.vpn_proxy --port $PROXY_PORT &
PROXY_PID=$!
sleep 2

# Check if running
if ps -p $PROXY_PID > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ VPN Proxy running on 127.0.0.1:$PROXY_PORT${NC}"
else
    echo -e "   ${RED}❌ Failed to start proxy${NC}"
    exit 1
fi
echo ""

# Step 3: Test through proxy
echo -e "${YELLOW}[STEP 3]${NC} Testing connection through VPN..."
echo "   Command: curl -x socks5://127.0.0.1:$PROXY_PORT https://ifconfig.me"
echo ""

PROXY_IP=$(curl -s --max-time 10 -x socks5://127.0.0.1:$PROXY_PORT https://ifconfig.me || echo "Connection failed")

if [ "$PROXY_IP" != "Connection failed" ]; then
    echo -e "   ${GREEN}✅ VPN IP: $PROXY_IP${NC}"
    
    if [ "$PROXY_IP" == "$REAL_IP" ]; then
        echo -e "   ${YELLOW}ℹ️  Same IP (direct mode - no exit node configured)${NC}"
        echo -e "   ${YELLOW}   In production, traffic routes through mesh exit nodes${NC}"
    else
        echo -e "   ${GREEN}🎉 IP CHANGED! VPN is working!${NC}"
    fi
else
    echo -e "   ${RED}❌ Connection failed${NC}"
fi
echo ""

# Step 4: Show stats
echo -e "${YELLOW}[STEP 4]${NC} VPN Statistics:"
echo "   • Proxy PID: $PROXY_PID"
echo "   • Port: $PROXY_PORT"
echo "   • Protocol: SOCKS5"
echo ""

# Step 5: Browser test instructions
echo "============================================================"
echo -e "${GREEN}       BROWSER TEST INSTRUCTIONS${NC}"
echo "============================================================"
echo ""
echo "Firefox:"
echo "   1. Settings → Network Settings → Manual proxy"
echo "   2. SOCKS Host: 127.0.0.1, Port: $PROXY_PORT"
echo "   3. Select SOCKS v5"
echo "   4. Visit: https://whatismyipaddress.com"
echo ""
echo "Chrome (command line):"
echo "   google-chrome --proxy-server=\"socks5://127.0.0.1:$PROXY_PORT\""
echo ""
echo "curl:"
echo "   curl -x socks5://127.0.0.1:$PROXY_PORT https://ifconfig.me"
echo ""
echo "============================================================"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the VPN proxy${NC}"
echo ""

# Keep running
wait $PROXY_PID
