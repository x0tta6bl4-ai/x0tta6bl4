#!/bin/bash
# Sync Dashboard to ALL nodes

sync_dash() {
    IP=$1
    PASS=$2
    echo "🎨 Updating Dashboard on $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no dashboard_v2_debug.html root@$IP:/opt/x0tta6bl4/dashboard.html
}

sync_dash "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
sync_dash "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
sync_dash "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ All nodes updated to v2.2"
