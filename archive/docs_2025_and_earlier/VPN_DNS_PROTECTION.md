# ⚠️ VPN DNS - Защита от Удаления

## 🔴 Проблема:

**x-ui постоянно удаляет DNS конфигурацию** при перезапуске, вызывая:
- DNS таймауты 6-10 секунд
- Высокий ping
- Connection refused

## 🔍 Причина:

1. **protect_config.sh** запускается через `ExecStartPost` в systemd service
2. **x-ui** может перезаписывать `config.json` из своей базы данных
3. Конфигурация не синхронизирована между x-ui панелью и файлом

## ✅ Решение:

### 1. Отключен protect_config.sh ✅

```bash
# /etc/systemd/system/x-ui.service.d/apply-config.conf
# Отключено:
# ExecStartPost=/bin/bash -c "sleep 3 && /usr/local/x-ui/protect_config.sh"

# Включено восстановление DNS:
ExecStartPost=/bin/bash -c "sleep 5 && python3 /root/fix_dns_final.py"
```

### 2. protect_config.sh исправлен ✅

Отключен вызов `x0tta6bl4-mesh apply`:
```bash
# DISABLED: /usr/local/bin/x0tta6bl4-mesh apply
```

### 3. Автоматическое восстановление DNS ✅

Скрипт `/root/fix_dns_final.py` автоматически восстанавливает DNS после каждого перезапуска x-ui.

---

## 🛠️ Ручное восстановление DNS:

Если DNS снова пропал, выполните на сервере:

```bash
# Восстановить DNS
python3 /root/fix_dns_final.py

# Перезапустить x-ui
systemctl restart x-ui

# Проверить
cat /usr/local/x-ui/bin/config.json | python3 -c 'import sys, json; d=json.load(sys.stdin); print("DNS:", "✅ есть" if d.get("dns") else "❌ нет")'
```

---

## 📝 Альтернативное решение:

### Обновить конфигурацию через x-ui панель:

1. Откройте: http://89.125.1.107:628/LiiqMSLWV8cM2MMlFA/
2. Перейдите в настройки
3. Добавьте DNS конфигурацию вручную
4. Сохраните

**Но это может не работать**, если x-ui не поддерживает DNS в UI.

---

## 🔄 Постоянное решение:

Создать systemd timer который будет проверять и восстанавливать DNS каждые 5 минут:

```bash
# На сервере:
cat > /etc/systemd/system/restore-dns.service << 'EOF'
[Unit]
Description=Restore DNS in x-ui config
After=x-ui.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /root/fix_dns_final.py
EOF

cat > /etc/systemd/system/restore-dns.timer << 'EOF'
[Unit]
Description=Restore DNS every 5 minutes
Requires=restore-dns.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable restore-dns.timer
systemctl start restore-dns.timer
```

---

## ✅ Текущий статус:

```
✅ protect_config.sh: исправлен
✅ apply-config.conf: обновлен (восстанавливает DNS)
✅ fix_dns_final.py: готов к использованию
⚠️ x-ui: может перезаписывать конфигурацию
```

---

## 🎯 Рекомендация:

**Используйте автоматическое восстановление DNS** через systemd timer (см. выше) для гарантированной работы DNS.

**Или обновите конфигурацию через x-ui панель**, если она поддерживает DNS настройки.

