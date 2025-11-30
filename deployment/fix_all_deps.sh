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

fix_deps "89.125.1.107" "lhJOTi8vrB01aQ12C0"
fix_deps "77.83.245.27" "13Vbkkbjyjd$"
fix_deps "62.133.60.252" "13Vbkkbjyjd$"

echo "🎉 Dependencies fixed."
