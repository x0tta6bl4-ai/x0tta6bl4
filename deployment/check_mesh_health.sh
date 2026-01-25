#!/bin/bash
# Multi-Node Health Check for x0tta6bl4 Mesh
# Checks status of all nodes in the network

NODES=(
    "89.125.1.107:Node-1-EU-Central"
    "77.83.245.27:Node-2-EU-West"
    "62.133.60.252:Node-3-New"
)

echo "🌐 x0tta6bl4 Mesh Network Health Check"
echo "========================================"
echo ""

for node_info in "${NODES[@]}"; do
    IFS=':' read -r ip name <<< "$node_info"
    
    echo "📍 Checking $name ($ip)"
    echo "─────────────────────────────────────"
    
    # 1. Service status
    # Используем sshpass для автоматизации (предполагаем, что вы знаете пароль или ключи, 
    # но в скрипте проверки лучше ключи. Пока просто curl снаружи для скорости)
    
    # 2. API endpoint (новый порт 9091)
    # Таймаут 2 секунды
    api_response=$(curl -s -m 2 http://$ip:9091/metrics 2>/dev/null)
    
    if [ -n "$api_response" ]; then
        echo "   ✅ API: Alive"
        # Парсим JSON
        phi=$(echo "$api_response" | jq -r '.phi_ratio' 2>/dev/null)
        state=$(echo "$api_response" | jq -r '.state' 2>/dev/null)
        peers=$(echo "$api_response" | jq -r '.peers_online' 2>/dev/null)
        
        if [ "$phi" != "null" ]; then
            echo "   📊 Phi: $phi"
            echo "   🧠 State: $state"
            echo "   🕸️ Mesh Peers: $peers"
        else
             echo "   ⚠️  API OK but bad JSON"
        fi
    else
        echo "   ❌ API: DOWN (No response on :9091)"
    fi
    echo ""
done

echo "========================================"
echo "✅ Check complete"
