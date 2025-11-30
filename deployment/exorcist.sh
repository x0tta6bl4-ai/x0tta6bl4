#!/bin/bash
# Exorcist Protocol: Deep Cleanse

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
for IP in "89.125.1.107" "77.83.245.27" "62.133.60.252"; do
    PASS="lhJOTi8vrB01aQ12C0"
    if [ "$IP" != "89.125.1.107" ]; then PASS="13Vbkkbjyjd$"; fi
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl stop x0tta6bl4-brain"
done

# CLEAN ALL
echo "🧹 Cleaning ALL nodes..."
for IP in "89.125.1.107" "77.83.245.27" "62.133.60.252"; do
    PASS="lhJOTi8vrB01aQ12C0"
    if [ "$IP" != "89.125.1.107" ]; then PASS="13Vbkkbjyjd$"; fi
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "rm -f /opt/x0tta6bl4/peers.json && echo '[]' > /opt/x0tta6bl4/peers.json"
done

# START BOOTSTRAP FIRST
echo "🚀 Starting Bootstrap (Node 1)..."
sshpass -p "lhJOTi8vrB01aQ12C0" ssh -o StrictHostKeyChecking=no root@89.125.1.107 "systemctl start x0tta6bl4-brain"
sleep 5

# START OTHERS
echo "🚀 Starting Workers..."
sshpass -p "13Vbkkbjyjd$" ssh -o StrictHostKeyChecking=no root@77.83.245.27 "systemctl start x0tta6bl4-brain"
sleep 2
sshpass -p "13Vbkkbjyjd$" ssh -o StrictHostKeyChecking=no root@62.133.60.252 "systemctl start x0tta6bl4-brain"

echo "✅ Exorcism Complete."
