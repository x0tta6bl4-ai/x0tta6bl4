#!/bin/bash
# Emergency Repair: Kill Zombie Xray Processes

fix_node() {
    IP=$1
    PASS=$2
    echo "🚑 Fixing Xray on $IP..."
    
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "bash -s" << 'EOF'
        # 1. Find PID using the port
        fuser -k 62789/tcp >/dev/null 2>&1
        fuser -k 39829/tcp >/dev/null 2>&1
        
        # 2. Kill all xray processes
        pkill -9 -f xray-linux
        pkill -9 -f xray
        
        # 3. Restart X-UI
        systemctl restart x-ui
        
        # 4. Check status
        sleep 2
        if netstat -tulpn | grep -E '62789|39829'; then
            echo "✅ Ports are listening (Xray restarted successfully)"
        else
            echo "⚠️ Ports are NOT listening (Check logs)"
        fi
EOF
}

echo "=== XRAY EMERGENCY FIX ==="
# Fix ALL nodes just in case
fix_node "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
fix_node "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
fix_node "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"
