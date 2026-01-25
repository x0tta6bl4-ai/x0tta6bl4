#!/bin/bash
IP="62.133.60.252"
PASS="13Vbkkbjyjd$"

echo "🔧 Installing dependencies on Node 3..."

# 1. Пробуем через apt (надежнее)
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "apt-get update >/dev/null 2>&1 && apt-get install -y python3-psutil python3-aiohttp >/dev/null 2>&1"

# 2. Если не помогло - pip с флагом
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "pip3 install psutil aiohttp --break-system-packages >/dev/null 2>&1 || true"

# 3. Рестарт
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain && sleep 2 && systemctl status x0tta6bl4-brain --no-pager"

echo "✅ Done."
