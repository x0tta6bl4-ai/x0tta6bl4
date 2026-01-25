#!/bin/bash
# Скрипт для исправления ошибки geosite:ru
# Запустить на сервере: ssh root@89.125.1.107

set -euo pipefail

CONFIG_FILE="/usr/local/etc/xray/config.json"
BACKUP="${CONFIG_FILE}.backup_fix_$(date +%Y%m%d_%H%M%S)"

echo "🔧 Исправление ошибки geosite:ru..."

# Бэкап
cp "$CONFIG_FILE" "$BACKUP"
echo "✅ Backup: $BACKUP"

# Исправление через Python
python3 << 'PYTHON'
import json

CONFIG_FILE = '/usr/local/etc/xray/config.json'

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# Исправляем routing rules
if 'routing' in config and 'rules' in config['routing']:
    rules = config['routing']['rules']
    fixed_rules = []
    
    for rule in rules:
        if rule.get('type') == 'field' and rule.get('outboundTag') == 'direct':
            domains = rule.get('domain', [])
            if 'geosite:ru' in domains:
                russian_domains = [
                    'sber.ru', 'sberbank-online.ru', 'sberbusiness.ru',
                    'vtb.ru', 'alfabank.ru', 'gazprombank.ru',
                    'gosuslugi.ru', 'mos.ru', 'spb.ru',
                    'yandex.ru', 'mail.ru', 'vk.com', 'vkontakte.ru',
                    'ok.ru', 'odnoklassniki.ru', 'avito.ru',
                    'ozon.ru', 'wildberries.ru'
                ]
                rule['domain'] = russian_domains
                print(f'✅ Заменено geosite:ru на {len(russian_domains)} доменов')
        fixed_rules.append(rule)
    
    config['routing']['rules'] = fixed_rules

with open(CONFIG_FILE, 'w') as f:
    json.dump(config, f, indent=2)

print('✅ Конфигурация исправлена')
PYTHON

# Валидация
echo ""
echo "🔍 Валидация конфигурации..."
if XRAY_LOCATION_ASSET=/usr/local/share/xray xray run -test -config "$CONFIG_FILE" 2>&1 | grep -q "Configuration OK"; then
    echo "✅ Конфигурация валидна"
    
    # Перезапуск
    echo ""
    echo "🔄 Перезапуск Xray..."
    systemctl restart xray
    sleep 3
    
    if systemctl is-active --quiet xray; then
        echo "✅ Xray запущен"
        ss -tlnp | grep 39829 && echo "✅ Порт 39829 слушается"
        echo ""
        echo "✅ Проблема исправлена! VPN работает."
    else
        echo "❌ Xray не запустился, откат..."
        cp "$BACKUP" "$CONFIG_FILE"
        systemctl restart xray
        exit 1
    fi
else
    echo "❌ Конфигурация невалидна, откат..."
    cp "$BACKUP" "$CONFIG_FILE"
    exit 1
fi

