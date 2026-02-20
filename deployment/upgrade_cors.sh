#!/bin/bash
# Install CORS support

fix_cors() {
    IP=$1
    PASS=$2
    echo "💊 Installing CORS on $IP..."
    
    # pip с флагом break-system-packages (так как мы в виртуалке или контейнере или просто надо)
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "pip3 install aiohttp-cors --break-system-packages >/dev/null 2>&1 || apt-get install -y python3-aiohttp-cors >/dev/null 2>&1"
    
    # Заливаем обновленный код
    cat run_brain_dynamic.py | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "cat > /opt/x0tta6bl4/run_brain_dynamic.py"

    # Рестарт
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain"
    echo "✅ Updated $IP"
}

fix_cors "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
fix_cors "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
fix_cors "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🎉 Network upgraded with CORS support."
