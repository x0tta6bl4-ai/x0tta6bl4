#!/bin/bash
# x0tta6bl4 Node Auto-Deploy Script
# Usage: ./deploy_node.sh root@IP PASSWORD [NODE_NAME]

set -e

HOST=$1
PASS=$2
NODE_NAME=${3:-"node-$(date +%s)"}

if [ -z "$HOST" ] || [ -z "$PASS" ]; then
    echo "Usage: ./deploy_node.sh user@IP PASSWORD [NODE_NAME]"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/x0tta6bl4"

echo "🚀 Deploying x0tta6bl4 node to $HOST..."
echo "   Node ID: $NODE_NAME"

# 1. Create remote directory
echo "[1/5] Creating remote directory..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $HOST "mkdir -p $REMOTE_DIR/src $REMOTE_DIR/scripts"

# 2. Copy files
echo "[2/5] Copying files..."
sshpass -p "$PASS" scp -o StrictHostKeyChecking=no -r \
    "$PROJECT_DIR/src/network" \
    "$PROJECT_DIR/src/crypto" \
    "$PROJECT_DIR/src/dao" \
    "$PROJECT_DIR/src/web" \
    $HOST:$REMOTE_DIR/src/

sshpass -p "$PASS" scp -o StrictHostKeyChecking=no \
    "$PROJECT_DIR/Dockerfile.vpn" \
    "$PROJECT_DIR/requirements.txt" \
    $HOST:$REMOTE_DIR/

# 3. Check if Docker is available
echo "[3/5] Checking Docker..."
HAS_DOCKER=$(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $HOST "which docker 2>/dev/null || echo 'none'")

if [ "$HAS_DOCKER" != "none" ]; then
    echo "   Docker found. Building container..."
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $HOST << EOF
cd $REMOTE_DIR
docker build -f Dockerfile.vpn -t x0t-node . 2>/dev/null || true
docker stop x0t-node 2>/dev/null || true
docker rm x0t-node 2>/dev/null || true
docker run -d --name x0t-node --restart unless-stopped \
    -p 10809:10809 -p 8081:8080 \
    -e NODE_ID=$NODE_NAME \
    x0t-node
EOF
else
    echo "   Docker not found. Installing dependencies and running directly..."
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $HOST << EOF
cd $REMOTE_DIR
pip3 install flask cryptography web3 --break-system-packages --ignore-installed blinker 2>/dev/null || true
pkill -f mesh_vpn_bridge 2>/dev/null || true
pkill -f operator_dashboard 2>/dev/null || true
nohup python3 -u -m src.network.mesh_vpn_bridge > bridge.log 2>&1 &
nohup python3 -u -m src.web.operator_dashboard > dashboard.log 2>&1 &
EOF
fi

# 4. Open firewall ports
echo "[4/5] Opening firewall ports..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $HOST << 'EOF'
ufw allow 10809/tcp 2>/dev/null || iptables -I INPUT -p tcp --dport 10809 -j ACCEPT 2>/dev/null || true
ufw allow 8081/tcp 2>/dev/null || iptables -I INPUT -p tcp --dport 8081 -j ACCEPT 2>/dev/null || true
EOF

# 5. Verify
echo "[5/5] Verifying deployment..."
sleep 3

# Extract IP from HOST (user@IP format)
IP=$(echo $HOST | cut -d'@' -f2)

# Test VPN
VPN_TEST=$(curl -s --max-time 5 -x socks5://$IP:10809 http://ifconfig.me 2>/dev/null || echo "FAILED")
DASH_TEST=$(curl -s --max-time 5 http://$IP:8081/api/stats 2>/dev/null || echo "FAILED")

echo ""
echo "============================================"
if [ "$VPN_TEST" != "FAILED" ]; then
    echo "✅ VPN PROXY: socks5://$IP:10809"
    echo "   Exit IP: $VPN_TEST"
else
    echo "⚠️  VPN PROXY: Not responding yet (may need more time)"
fi

if [ "$DASH_TEST" != "FAILED" ]; then
    echo "✅ DASHBOARD: http://$IP:8081"
else
    echo "⚠️  DASHBOARD: Not responding yet"
fi
echo "============================================"
echo ""
echo "🎉 Node $NODE_NAME deployed to $IP"
