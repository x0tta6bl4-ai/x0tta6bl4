#!/bin/bash
# Полная санитарная очистка mesh-сети (Sanitary Clean)

clean_node() {
    IP=$1
    PASS=$2
    echo "🧹 Cleaning $IP..."
    
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "bash -s" << 'EOF'
        # 1. Stop service
        systemctl stop x0tta6bl4-brain
        
        # 2. Remove peer DB and backups
        rm -f /opt/x0tta6bl4/peers.json
        rm -f /opt/x0tta6bl4/peers.json.bak
        rm -f /tmp/x0tta6bl4_peers*
        
        # 3. Clear empty list
        echo "[]" > /opt/x0tta6bl4/peers.json
        
        # 4. Start service
        systemctl start x0tta6bl4-brain
        
        echo "✅ Cleaned and restarted"
EOF
}

echo "🧹 SANITATION MODE: Purging ghost peers..."

clean_node "89.125.1.107" "lhJOTi8vrB01aQ12C0"
clean_node "77.83.245.27" "13Vbkkbjyjd$"
clean_node "62.133.60.252" "13Vbkkbjyjd$"

echo ""
echo "🎉 Sanitation complete!"
echo "⏳ Waiting 30 seconds for discovery..."
sleep 30

echo ""
echo "📡 Checking Bootstrap Node..."
curl -s -m 5 http://89.125.1.107:9092/peers
