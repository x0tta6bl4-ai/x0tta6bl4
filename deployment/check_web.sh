#!/bin/bash
# Web Health Check

check_node() {
    IP=$1
    echo "🌍 Checking $IP:8080..."
    
    # 1. HTTP Check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://$IP:8080/landing.html)
    echo "   HTTP Code: $HTTP_CODE"
    
    if [ "$HTTP_CODE" != "200" ]; then
        echo "   ❌ FAIL. Diagnosing..."
        # 2. Process Check (кто слушает порт?)
        sshpass -p '13Vbkkbjyjd$' ssh -o StrictHostKeyChecking=no root@$IP "netstat -tulpn | grep 8080" 2>/dev/null
    else
        echo "   ✅ OK"
    fi
    echo ""
}

echo "=== WEB CHECK ==="
check_node "89.125.1.107" # Node 1
check_node "77.83.245.27" # Node 2
check_node "62.133.60.252" # Node 3 (Problematic)
