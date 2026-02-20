#!/bin/bash
# Purge Peer Database (Reset Network State)

purge_node() {
    IP=$1
    PASS=$2
    echo "🧹 Purging peers on $IP..."
    
    # Удаляем файл базы
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "rm -f /opt/x0tta6bl4/peers.json"
    
    # Рестарт сервиса (он создаст чистую базу и найдет соседей заново)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain"
    
    echo "✅ $IP reset."
}

purge_node "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
purge_node "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
purge_node "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Network Reset Complete. Nodes will rediscover each other in ~30 seconds."
