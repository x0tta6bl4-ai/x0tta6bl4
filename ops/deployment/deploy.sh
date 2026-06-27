#!/bin/bash
SERVER=$1

if [ -z "$SERVER" ]; then
    echo "❌ Ошибка: Укажи сервер (например: root@89.125.1.107)"
    exit 1
fi

echo "🚀 Начинаю деплой Мозга на $SERVER..."

# 1. Создаем папку на сервере
ssh -o StrictHostKeyChecking=no $SERVER "mkdir -p /opt/x0tta6bl4/brain_core"

# 2. Копируем ядро (consciousness.py)
echo "📦 Копирую ядро..."
scp -o StrictHostKeyChecking=no ../src/core/consciousness.py $SERVER:/opt/x0tta6bl4/brain_core/

# 3. Копируем запускатор
echo "📦 Копирую скрипт запуска..."
scp -o StrictHostKeyChecking=no run_brain.py $SERVER:/opt/x0tta6bl4/

# 4. Устанавливаем зависимости на сервере
echo "🔧 Ставлю библиотеки (psutil)..."
ssh -o StrictHostKeyChecking=no $SERVER "apt-get update && apt-get install -y python3-pip && pip3 install psutil"

# 5. Настраиваем автозапуск
echo "⚙️ Настраиваю systemd..."
scp -o StrictHostKeyChecking=no systemd/x0tta6bl4-brain.service $SERVER:/etc/systemd/system/
ssh -o StrictHostKeyChecking=no $SERVER "systemctl daemon-reload && systemctl enable x0tta6bl4-brain && systemctl restart x0tta6bl4-brain"

echo "✅ Готово! Мозг запущен."
echo "📊 Проверить статус: ssh $SERVER 'systemctl status x0tta6bl4-brain'"
echo "📝 Смотреть логи: ssh $SERVER 'journalctl -u x0tta6bl4-brain -f'"
