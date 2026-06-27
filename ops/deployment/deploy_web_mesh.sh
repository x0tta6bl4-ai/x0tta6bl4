#!/bin/bash
# Sync Web Content to ALL Nodes
# Превращаем каждый узел в веб-сервер

sync_node() {
    IP=$1
    PASS=$2
    echo "🌐 Syncing Web to $IP..."
    
    # 1. Заливаем файлы
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v2.html root@$IP:/opt/x0tta6bl4/landing.html
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no dashboard_v2.html root@$IP:/opt/x0tta6bl4/dashboard.html
    
    # 2. Открываем порт 8080
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ufw allow 8080/tcp >/dev/null 2>&1 || true"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "iptables -A INPUT -p tcp --dport 8080 -j ACCEPT >/dev/null 2>&1 || true"

    # 3. Запускаем HTTP сервер (если не запущен)
    # Используем pkill чтобы убить старый и запустить новый (для обновления файлов в памяти если что)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "pkill -f 'http.server 8080' || true"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cd /opt/x0tta6bl4 && nohup python3 -m http.server 8080 > /dev/null 2>&1 &"
    
    echo "✅ $IP serving Web."
}

sync_node "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
sync_node "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
sync_node "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Decentralized Hosting Active. Access site from ANY node."
