#!/bin/bash
# Обновляем код на обоих узлах

update_node() {
    SERVER=$1
    PASS=$2
    echo "🛠️ Патч порта (9091) на $SERVER..."
    
    # Копируем новый код
    cat run_brain_mesh.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "cat > /opt/x0tta6bl4/run_brain_mesh.py"
    
    # Открываем порт (если есть ufw)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "ufw allow 9091/tcp >/dev/null 2>&1 || true"
    
    # Рестарт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "systemctl restart x0tta6bl4-brain && echo 'RESTARTED'"
}

update_node "root@89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
update_node "root@77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
