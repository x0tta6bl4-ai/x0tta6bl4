# ⚡ Quick Deploy Steps - Минимальный набор команд

**Для быстрого деплоя security fixes**

---

## 🚀 Быстрый деплой (5 минут)

```bash
# На VPS (89.125.1.107):
cd /mnt/AC74CC2974CBF3DC

# 1. Backup
cp x0tta6bl4_users.db x0tta6bl4_users.db.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "No DB to backup"

# 2. Update .env (если еще не сделано)
cat >> .env << 'EOF'
REALITY_PRIVATE_KEY=sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw
ADMIN_USER_IDS=YOUR_ADMIN_USER_ID
EOF

# ⚠️ ВАЖНО: Замените YOUR_ADMIN_USER_ID на ваш реальный Telegram user ID!

# 3. Upload files (с локальной машины)
# scp vpn_config_generator.py telegram_bot.py admin_commands.py root@89.125.1.107:/mnt/AC74CC2974CBF3DC/

# 4. Restart
systemctl restart x0tta6bl4-bot

# 5. Check
sleep 3
systemctl status x0tta6bl4-bot
journalctl -u x0tta6bl4-bot -n 20 --no-pager
```

---

## ✅ Быстрая проверка

```bash
# 1. Bot работает?
systemctl is-active x0tta6bl4-bot && echo "✅ Bot running" || echo "❌ Bot not running"

# 2. Нет ошибок?
journalctl -u x0tta6bl4-bot --since "2 minutes ago" | grep -i error | wc -l
# Ожидаемо: 0

# 3. UUID уникальны?
sqlite3 x0tta6bl4_users.db "SELECT COUNT(*) = COUNT(DISTINCT vpn_uuid) FROM users WHERE vpn_uuid IS NOT NULL;" 2>/dev/null
# Ожидаемо: 1 (true)
```

---

## 🧪 Тест в боте

1. Открой бота в Telegram
2. Отправь `/start`
3. Нажми "Trial" или отправь `/trial`
4. Ожидаемое: Trial активирован
5. Отправь `/config`
6. Ожидаемое: Конфиг с уникальным UUID

---

**Готово! 🎉**

