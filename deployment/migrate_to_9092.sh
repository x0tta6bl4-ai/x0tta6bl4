#!/bin/bash
# Миграция на порт 9092

migrate_port() {
    IP=$1
    PASS=$2
    echo "🚢 Migrating $IP to port 9092..."
    
    # Заливаем обновленный код
    cat run_brain_dynamic.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /opt/x0tta6bl4/run_brain_dynamic.py"
    
    # Открываем новый порт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ufw allow 9092/tcp >/dev/null 2>&1 || true"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "iptables -A INPUT -p tcp --dport 9092 -j ACCEPT >/dev/null 2>&1 || true"
    
    # Обновляем файл 'my_url.txt'
    MY_URL="http://$IP:9092"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "echo '$MY_URL' > /opt/x0tta6bl4/my_url.txt"

    # Рестарт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain"
    
    echo "✅ $IP migrated."
}

migrate_port "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
migrate_port "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
migrate_port "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Migration Complete (Port 9092)"
