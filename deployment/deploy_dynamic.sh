#!/bin/bash
# Динамический деплой. Мы просто говорим узлу: "Твой адрес такой-то, иди к Маяку".

deploy_dynamic_node() {
    IP=$1
    PASS=$2
    MY_URL="http://$IP:9091"
    
    echo "📦 Updating $IP (Dynamic Mode)..."
    
    # Заливаем новый код
    cat run_brain_dynamic.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /opt/x0tta6bl4/run_brain_dynamic.py"
    
    # Прописываем "Кто я?"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "echo '$MY_URL' > /opt/x0tta6bl4/my_url.txt"
    
    # Обновляем сервис
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "sed -i 's/run_brain_mesh.py/run_brain_dynamic.py/' /etc/systemd/system/x0tta6bl4-brain.service"
    
    # Рестарт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl daemon-reload && systemctl restart x0tta6bl4-brain"
    
    echo "✅ $IP is now Dynamic."
}

# Обновляем всех
deploy_dynamic_node "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
deploy_dynamic_node "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
deploy_dynamic_node "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Network upgraded to Dynamic Discovery!"
