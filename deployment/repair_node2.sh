#!/bin/bash
SERVER="root@77.83.245.27"
PASS="${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🔧 Repairing Node 2..."

# 1. Заливаем service файл
cat systemd/x0tta6bl4-brain.service | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "cat > /etc/systemd/system/x0tta6bl4-brain.service"

# 2. Исправляем путь в сервисе (там mesh версия)
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "sed -i 's/run_brain.py/run_brain_mesh.py/' /etc/systemd/system/x0tta6bl4-brain.service"

# 3. Перезагружаем демона и стартуем
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no $SERVER "systemctl daemon-reload && systemctl enable x0tta6bl4-brain && systemctl restart x0tta6bl4-brain && systemctl status x0tta6bl4-brain --no-pager"

echo "✅ Done."
