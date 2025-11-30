# 🔴 СРОЧНОЕ ИСПРАВЛЕНИЕ VPN

## ❌ Проблема

**Ошибка:** `list not found in geosite.dat: RU`

**Причина:** Правило `geosite:ru` не может быть обработано, так как в geosite.dat нет списка "RU".

**Результат:** Xray не запускается, VPN не работает.

---

## ✅ Решение

### Вариант 1: Автоматический (рекомендуется)

**На сервере выполните:**

```bash
ssh root@89.125.1.107

# Скачать и запустить скрипт
curl -o /tmp/fix_vpn.sh https://raw.githubusercontent.com/.../fix_vpn_geosite_error.sh
# ИЛИ скопировать содержимое файла fix_vpn_geosite_error.sh

chmod +x /tmp/fix_vpn.sh
/tmp/fix_vpn.sh
```

### Вариант 2: Ручной

**На сервере выполните:**

```bash
ssh root@89.125.1.107

# 1. Бэкап
cp /usr/local/etc/xray/config.json /usr/local/etc/xray/config.json.backup

# 2. Исправление
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
        fixed_rules.append(rule)
    
    config['routing']['rules'] = fixed_rules

with open(CONFIG_FILE, 'w') as f:
    json.dump(config, f, indent=2)

print('✅ Конфигурация исправлена')
PYTHON

# 3. Валидация
XRAY_LOCATION_ASSET=/usr/local/share/xray xray run -test -config /usr/local/etc/xray/config.json

# 4. Перезапуск
systemctl restart xray
sleep 3
systemctl status xray
ss -tlnp | grep 39829
```

---

## 🔧 Что Делает Исправление

1. **Находит правило** с `geosite:ru`
2. **Заменяет** на конкретные домены (18 российских доменов)
3. **Валидирует** конфигурацию
4. **Перезапускает** Xray

---

## ✅ После Исправления

**Проверьте:**

```bash
# Статус Xray
systemctl status xray

# Порт слушается
ss -tlnp | grep 39829

# Конфигурация валидна
XRAY_LOCATION_ASSET=/usr/local/share/xray xray run -test -config /usr/local/etc/xray/config.json
```

**Ожидается:**
- ✅ Xray: active (running)
- ✅ Порт 39829: LISTEN
- ✅ Configuration OK

---

## 📋 Список Доменов

После исправления split tunneling будет работать для:

**Банки:**
- sber.ru, sberbank-online.ru, sberbusiness.ru
- vtb.ru, alfabank.ru, gazprombank.ru

**Госуслуги:**
- gosuslugi.ru, mos.ru, spb.ru

**Сервисы:**
- yandex.ru, mail.ru, vk.com, vkontakte.ru
- ok.ru, odnoklassniki.ru, avito.ru
- ozon.ru, wildberries.ru

---

## ⚠️ Важно

Если после исправления VPN все еще не работает:

1. Проверьте логи: `journalctl -u xray -n 50`
2. Проверьте конфигурацию: `cat /usr/local/etc/xray/config.json | jq .`
3. Откатитесь к бэкапу: `cp /usr/local/etc/xray/config.json.backup /usr/local/etc/xray/config.json`

---

## ✅ Статус

**Проблема:** 🔴 Требует исправления
**Решение:** ✅ Готово (скрипт создан)
**Действие:** ⏳ Требуется выполнить на сервере

**После исправления VPN снова заработает!** 🚀

