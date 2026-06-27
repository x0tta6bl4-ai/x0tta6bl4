#!/bin/bash
# Fix dependencies on all nodes

fix_deps() {
    IP=$1
    PASS=$2
    echo "💉 Fixing dependencies on $IP..."
    
    # Ставим системные пакеты (они точно будут видны всем)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "apt-get update >/dev/null 2>&1 && apt-get install -y python3-aiohttp python3-psutil >/dev/null 2>&1"
    
    # Рестарт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain"
    echo "✅ Fixed $IP"
}

fix_deps "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
fix_deps "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
fix_deps "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Dependencies fixed."
