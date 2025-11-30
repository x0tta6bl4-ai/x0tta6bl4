#!/bin/bash
# Проверка динамической сети

BOOTSTRAP="http://89.125.1.107:9092"

echo "🌐 x0tta6bl4 Dynamic Mesh Check"
echo "=================================="

# 1. Спрашиваем Маяк
echo "🗼 Asking Bootstrap Node ($BOOTSTRAP)..."
PEERS_JSON=$(curl -s -m 5 $BOOTSTRAP/peers)

if [ -z "$PEERS_JSON" ]; then
    echo "❌ Bootstrap DEAD"
    exit 1
fi

echo "✅ Bootstrap ALIVE"
PEERS_LIST=$(echo $PEERS_JSON | jq -r '.peers[]')
PEER_COUNT=$(echo $PEERS_JSON | jq '.peers | length')

echo "📊 Total Peers Known: $PEER_COUNT"
echo "📋 Peer List:"
echo "$PEERS_LIST"
echo ""

# 2. Опрашиваем каждого пира
for PEER in $PEERS_LIST; do
    echo "📍 Checking Peer: $PEER"
    
    # Если это локальный туннель (localhost), проверяем через curl
    if [[ "$PEER" == *"localhost"* ]] || [[ "$PEER" == *"127.0.0.1"* ]]; then
        # Это сложно проверить снаружи, пропускаем или пробуем через Node 1
        echo "   ⚠️  Skipping Tunnel Peer (check manually via Node 1)"
        continue
    fi
    
    # Проверяем метрики
    METRICS=$(curl -s -m 3 $PEER/metrics)
    if [ -n "$METRICS" ]; then
        PHI=$(echo $METRICS | jq -r '.phi_ratio')
        CPU=$(echo $METRICS | jq -r '.cpu')
        STATE=$(echo $METRICS | jq -r '.state')
        PEERS_SEEN=$(echo $METRICS | jq -r '.peers_count')
        
        echo "   ✅ Alive"
        echo "   🧠 State: $STATE (Phi: $PHI)"
        echo "   💻 CPU: $CPU%"
        echo "   👀 Sees Peers: $PEERS_SEEN"
    else
        echo "   ❌ DOWN or Firewall blocked"
    fi
    echo ""
done

echo "=================================="
echo "🎉 Dynamic Check Complete"
