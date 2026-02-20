#!/bin/bash
set -euo pipefail

# Web Health Check
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

check_node() {
    local IP=$1
    local PASS
    PASS="$(pass_for_ip "$IP")"
    echo "🌍 Checking $IP:8080..."
    
    # 1. HTTP Check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://$IP:8080/landing.html)
    echo "   HTTP Code: $HTTP_CODE"
    
    if [ "$HTTP_CODE" != "200" ]; then
        echo "   ❌ FAIL. Diagnosing..."
        # 2. Process Check (кто слушает порт?)
        sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "netstat -tulpn | grep 8080" 2>/dev/null
    else
        echo "   ✅ OK"
    fi
    echo ""
}

echo "=== WEB CHECK ==="
check_node "$NODE1_IP" # Node 1
check_node "$NODE2_IP" # Node 2
check_node "$NODE3_IP" # Node 3 (Problematic)
