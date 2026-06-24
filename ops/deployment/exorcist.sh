#!/bin/bash
set -euo pipefail

# Exorcist Protocol: Deep Cleanse
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

clean_node() {
    IP=$1
    PASS=$2
    echo "✝️ Exorcising $IP..."
    
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "bash -s" << 'EOF'
        systemctl stop x0tta6bl4-brain
        pkill -f run_brain_dynamic.py
        
        # Kill ALL python processes related to our app just in case
        # (Be careful not to kill system python scripts, but usually safe here)
        
        rm -f /opt/x0tta6bl4/peers.json
        rm -f /opt/x0tta6bl4/peers.json.bak
        
        # Check if config file itself is corrupted? No, we checked grep.
        
        echo "[]" > /opt/x0tta6bl4/peers.json
        
        # Start fresh
        systemctl start x0tta6bl4-brain
EOF
}

# STOP ALL FIRST (Isolation)
echo "🛑 Stopping ALL nodes..."
for IP in "$NODE1_IP" "$NODE2_IP" "$NODE3_IP"; do
    PASS="$(pass_for_ip "$IP")"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl stop x0tta6bl4-brain"
done

# CLEAN ALL
echo "🧹 Cleaning ALL nodes..."
for IP in "$NODE1_IP" "$NODE2_IP" "$NODE3_IP"; do
    PASS="$(pass_for_ip "$IP")"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "rm -f /opt/x0tta6bl4/peers.json && echo '[]' > /opt/x0tta6bl4/peers.json"
done

# START BOOTSTRAP FIRST
echo "🚀 Starting Bootstrap (Node 1)..."
sshpass -p "$NODE1_PASS" ssh -o StrictHostKeyChecking=no root@$NODE1_IP "systemctl start x0tta6bl4-brain"
sleep 5

# START OTHERS
echo "🚀 Starting Workers..."
sshpass -p "$NODE23_PASS" ssh -o StrictHostKeyChecking=no root@$NODE2_IP "systemctl start x0tta6bl4-brain"
sleep 2
sshpass -p "$NODE23_PASS" ssh -o StrictHostKeyChecking=no root@$NODE3_IP "systemctl start x0tta6bl4-brain"

echo "✅ Exorcism Complete."
