#!/bin/bash
# Массовый деплой на 3 узла

# Узлы и пароли
NODE1_IP="89.125.1.107"
NODE1_PASS="${NODE1_PASS:?Set NODE1_PASS in environment}"

NODE2_IP="77.83.245.27"
NODE2_PASS="${NODE23_PASS:?Set NODE23_PASS in environment}"

NODE3_IP="62.133.60.252"
NODE3_PASS="${NODE23_PASS:?Set NODE23_PASS in environment}"

deploy_node() {
    IP=$1
    PASS=$2
    NAME=$3
    
    echo "📦 [$NAME] Deploying to $IP..."
    
    # 1. Создаем структуру
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "mkdir -p /opt/x0tta6bl4/brain_core"
    
    # 2. Заливаем файлы (используем cat метод для надежности)
    cat ../src/core/consciousness.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /opt/x0tta6bl4/brain_core/consciousness.py"
    cat run_brain_mesh.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /opt/x0tta6bl4/run_brain_mesh.py"
    cat systemd/x0tta6bl4-brain.service | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /etc/systemd/system/x0tta6bl4-brain.service"
    
    # 3. Исправляем сервис файл (run_brain_mesh.py)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "sed -i 's/run_brain.py/run_brain_mesh.py/' /etc/systemd/system/x0tta6bl4-brain.service"
    
    # 4. Установка и запуск
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "apt-get update >/dev/null 2>&1 && apt-get install -y python3-pip >/dev/null 2>&1 && pip3 install psutil aiohttp >/dev/null 2>&1"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ufw allow 9091/tcp >/dev/null 2>&1 || true"
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl daemon-reload && systemctl enable x0tta6bl4-brain && systemctl restart x0tta6bl4-brain"
    
    echo "✅ [$NAME] OK"
}

# Параллельный запуск (или последовательный для надежности)
echo "🚀 Starting 3-Node Mesh Deployment"

deploy_node $NODE1_IP $NODE1_PASS "Node-1" &
PID1=$!
deploy_node $NODE2_IP $NODE2_PASS "Node-2" &
PID2=$!
deploy_node $NODE3_IP $NODE3_PASS "Node-3" &
PID3=$!

wait $PID1
wait $PID2
wait $PID3

echo "🎉 All nodes deployed!"
