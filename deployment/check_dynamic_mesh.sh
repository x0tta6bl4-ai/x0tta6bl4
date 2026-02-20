#!/bin/bash
set -euo pipefail

# Dynamic Mesh Network Health Check
# Проверяет работу динамического обнаружения узлов

NODE1_IP="89.125.1.107"
NODE2_IP="77.83.245.27"
NODE3_IP="62.133.60.252"

: "${NODE1_PASS:?Set NODE1_PASS in environment}"
: "${NODE23_PASS:?Set NODE23_PASS in environment}"

pass_for_ip() {
    local ip="$1"
    if [ "$ip" = "$NODE1_IP" ]; then
        printf '%s' "$NODE1_PASS"
    else
        printf '%s' "$NODE23_PASS"
    fi
}

NODES=(
    "$NODE1_IP:Node-1-Bootstrap"
    "$NODE2_IP:Node-2-EU-West"
    "$NODE3_IP:Node-3-RU-North"
)

echo "🌐 x0tta6bl4 Dynamic Mesh Health Check"
echo "========================================="
echo ""

echo "📡 Checking Dynamic Discovery..."
echo ""

# Проверяем Маяк (Bootstrap Node)
echo "🗼 Bootstrap Node Status ($NODE1_IP)"
echo "─────────────────────────────────────────"
bootstrap_peers=$(curl -s -m 5 http://$NODE1_IP:9092/peers 2>/dev/null)

if [ -n "$bootstrap_peers" ]; then
    echo " ✅ Bootstrap responding"
    # Используем python для парсинга JSON если jq нет, или jq
    peer_count=$(echo "$bootstrap_peers" | grep -o "http" | wc -l)
    echo " 📊 Known peers: $peer_count"
    
    if [ "$peer_count" != "0" ]; then
        echo " 📋 Raw Peer List:"
        echo "$bootstrap_peers"
    fi
else
    echo " ❌ Bootstrap not responding"
    echo " ⚠️ Dynamic discovery will not work!"
fi

echo ""
echo "─────────────────────────────────────────"
echo ""

# Проверяем каждый узел
for node_info in "${NODES[@]}"; do
    IFS=':' read -r ip name <<< "$node_info"
    echo "📍 $name ($ip)"
    echo "─────────────────────────────────────────"
    
    # Выбираем пароль
    PASS="$(pass_for_ip "$ip")"
    
    # 1. SSH check
    if ! timeout 3 sshpass -p "$PASS" ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no root@$ip "echo 'OK'" &>/dev/null; then
        echo " ❌ SSH: Not accessible"
        echo ""
        continue
    fi
    echo " ✅ SSH: Connected"

    # 2. Service status
    service_status=$(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$ip "systemctl is-active x0tta6bl4-brain 2>/dev/null" || echo "unknown")
    if [ "$service_status" = "active" ]; then
        echo " ✅ Service: Running"
    else
        echo " ⚠️ Service: $service_status"
    fi

    # 3. API Health
    health=$(curl -s -m 3 http://$ip:9092/health 2>/dev/null)
    if [ -n "$health" ]; then
        echo " ✅ API: Responding"
        
        # Parse health data simple grep
        phi=$(echo "$health" | grep -o '"phi_ratio": [0-9.]*' | cut -d' ' -f2)
        state=$(echo "$health" | grep -o '"state": "[^"]*"' | cut -d'"' -f4)
        
        echo " 📊 Phi: $phi | State: $state"
    else
        echo " ❌ API: No response (Check Port 9092)"
    fi

    # 4. Dynamic Peers Discovery
    peers=$(curl -s -m 3 http://$ip:9092/peers 2>/dev/null)
    if [ -n "$peers" ]; then
        peer_count=$(echo "$peers" | grep -o "http" | wc -l)
        echo " 🔗 Discovered peers: $peer_count"
    else
        echo " ⚠️ Peers: Unknown (API not responding)"
    fi

    echo ""
done

echo "========================================="
echo "🔬 Cross-Node Connectivity Test"
echo ""

# Test if nodes can see each other
echo "Testing Node-2 -> Node-3..."
node2_to_3=$(sshpass -p "$NODE23_PASS" ssh -o StrictHostKeyChecking=no root@$NODE2_IP "curl -s -m 3 http://$NODE3_IP:9092/health 2>/dev/null")
if [ -n "$node2_to_3" ]; then
    echo "✅ Node-2 can reach Node-3 directly"
else
    echo "⚠️ Node-2 cannot reach Node-3 (may need bootstrap relay)"
fi

echo "Testing Node-3 -> Node-2..."
node3_to_2=$(sshpass -p "$NODE23_PASS" ssh -o StrictHostKeyChecking=no root@$NODE3_IP "curl -s -m 3 http://$NODE2_IP:9092/health 2>/dev/null")
if [ -n "$node3_to_2" ]; then
    echo "✅ Node-3 can reach Node-2 directly"
else
    echo "⚠️ Node-3 cannot reach Node-2 (may need bootstrap relay)"
fi

echo ""
echo "========================================="
echo "🎉 Dynamic mesh health check complete!"
