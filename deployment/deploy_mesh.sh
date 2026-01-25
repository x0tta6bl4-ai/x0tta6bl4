#!/bin/bash
NODE1="root@89.125.1.107"
NODE2="root@77.83.245.27"

echo "🚀 ЗАПУСК MESH-СЕТИ x0tta6bl4"
echo "================================="

# Функция деплоя на узел
deploy_to_node() {
    SERVER=$1
    PASS=$2
    echo "📦 Деплой на $SERVER..."
    
    # Создаем папки
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "mkdir -p /opt/x0tta6bl4/brain_core"
    
    # Копируем ядро
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no ../src/core/consciousness.py $SERVER:/opt/x0tta6bl4/brain_core/
    
    # Копируем НОВЫЙ мозг (с API)
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no run_brain_mesh.py $SERVER:/opt/x0tta6bl4/
    
    # Ставим aiohttp
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "apt-get update >/dev/null 2>&1 && apt-get install -y python3-pip >/dev/null 2>&1 && pip3 install psutil aiohttp >/dev/null 2>&1"
    
    # Обновляем systemd (команда запуска изменилась на run_brain_mesh.py)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "sed -i 's/run_brain.py/run_brain_mesh.py/' /etc/systemd/system/x0tta6bl4-brain.service || true"
    
    # Если файла сервиса нет - копируем
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no systemd/x0tta6bl4-brain.service $SERVER:/etc/systemd/system/
    
    # Перезапуск
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "systemctl daemon-reload && systemctl enable x0tta6bl4-brain && systemctl restart x0tta6bl4-brain"
    
    echo "✅ $SERVER обновлен."
}

# Деплой на NODE 1 (обновление)
deploy_to_node $NODE1 "lhJOTi8vrB01aQ12C0"

# Деплой на NODE 2 (новый)
deploy_to_node $NODE2 "13Vbkkbjyjd$"

echo "================================="
echo "🌐 MESH-СЕТЬ ЗАПУЩЕНА!"
echo "Проверка статуса:"
echo "Node 1: curl http://89.125.1.107:9090/metrics"
echo "Node 2: curl http://77.83.245.27:9090/metrics"
