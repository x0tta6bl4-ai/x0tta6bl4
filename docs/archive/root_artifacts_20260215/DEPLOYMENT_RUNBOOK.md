# 🚀 Deployment Runbook - Security Fixes

**Дата:** 28 ноября 2025  
**Версия:** 2.0.0-secure  
**Статус:** Ready for Production

---

## 📋 Pre-Flight Checklist

### Перед запуском деплоя:

```bash
# 1. Verify you're on correct server
hostname
# Expected: ваш VPS hostname

# 2. Check current bot status
systemctl status x0tta6bl4-bot
# Expected: active (running)

# 3. Verify disk space
df -h
# Should have >1GB free

# 4. Check current users count
sqlite3 x0tta6bl4_users.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0"
# Note the number

# 5. Run pre-deployment checks
chmod +x pre_deploy_check.sh
./pre_deploy_check.sh
# Must pass all checks!
```

---

## 🔧 Deployment Steps

### Step 1: Pre-Deployment Check

```bash
cd /mnt/AC74CC2974CBF3DC
./pre_deploy_check.sh
```

**Ожидаемый результат:** ✅ All pre-deployment checks PASSED

---

### Step 2: Backup Database

```bash
# Backup создается автоматически в pre_deploy_check.sh
# Или вручную:
timestamp=$(date +%Y%m%d_%H%M%S)
cp x0tta6bl4_users.db "x0tta6bl4_users.db.backup_pre_security_${timestamp}"
echo "✅ Backup created: x0tta6bl4_users.db.backup_pre_security_${timestamp}"
```

---

### Step 3: Update Environment Variables

```bash
# Проверить что .env существует
if [ ! -f .env ]; then
    echo "Creating .env file..."
    touch .env
    chmod 600 .env
fi

# Добавить секреты (если еще не добавлены)
if ! grep -q "REALITY_PRIVATE_KEY" .env; then
    echo "REALITY_PRIVATE_KEY=sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw" >> .env
fi

if ! grep -q "ADMIN_USER_IDS" .env && ! grep -q "ADMIN_USER_ID" .env; then
    echo "ADMIN_USER_IDS=YOUR_ADMIN_USER_ID" >> .env
    echo "⚠️  IMPORTANT: Replace YOUR_ADMIN_USER_ID with your actual Telegram user ID!"
fi

# Проверить
source .env
echo "REALITY_PRIVATE_KEY length: ${#REALITY_PRIVATE_KEY}"
echo "ADMIN_USER_IDS: $ADMIN_USER_IDS"
```

---

### Step 4: Upload Fixed Files

```bash
# Если деплоишь с локальной машины:
scp vpn_config_generator.py telegram_bot.py admin_commands.py root@89.125.1.107:/mnt/AC74CC2974CBF3DC/

# Или если уже на VPS:
# Файлы должны быть уже обновлены через git pull или вручную
```

---

### Step 5: Restart Bot

```bash
# Graceful restart
systemctl restart x0tta6bl4-bot

# Wait for startup
sleep 5

# Check status
systemctl status x0tta6bl4-bot
# Expected: active (running)
```

---

### Step 6: Post-Deployment Tests

```bash
chmod +x post_deploy_security_tests.sh
./post_deploy_security_tests.sh
```

**Ожидаемый результат:** ✅ All post-deployment security tests PASSED

---

### Step 7: Monitor (5 minutes)

```bash
chmod +x monitor_post_deploy.sh
./monitor_post_deploy.sh
```

**Что смотреть:**
- Bot status: ✅ Running
- Errors: 0 (или минимальное количество)
- Logs: нет критических ошибок

---

## 🧪 Manual Testing

### Test 1: Trial Activation

```
1. Открой бота в Telegram
2. Отправь /start
3. Нажми "Trial" или отправь /trial
4. Ожидаемое: Trial активирован, UUID уникальный
5. Отправь /config
6. Ожидаемое: Конфиг с уникальным UUID
```

### Test 2: Admin Commands

```
1. Открой бота как админ
2. Отправь /admin_stats
3. Ожидаемое: Статистика показана

4. Открой бота как НЕ админ
5. Отправь /admin_stats
6. Ожидаемое: "❌ Доступ запрещён"
7. Проверь логи: должна быть запись "admin_access_denied"
```

### Test 3: UUID Uniqueness

```bash
# Проверить что все UUID уникальны
sqlite3 x0tta6bl4_users.db "
SELECT 
    COUNT(*) as total_users,
    COUNT(DISTINCT vpn_uuid) as unique_uuids
FROM users 
WHERE vpn_uuid IS NOT NULL;
"

# Ожидаемое: total_users == unique_uuids
```

---

## 📊 Success Metrics (первые 24 часа)

| Метрика | Target | Check Command |
|---------|--------|---------------|
| **Bot uptime** | >99.9% | `systemctl status x0tta6bl4-bot` |
| **Unique UUIDs** | 100% | `sqlite3 x0tta6bl4_users.db "SELECT COUNT(DISTINCT vpn_uuid) = COUNT(*) FROM users WHERE vpn_uuid IS NOT NULL;"` |
| **No secret leaks** | 0 | `journalctl -u x0tta6bl4-bot | grep -i "REALITY_PRIVATE_KEY.*=" \| wc -l` (должно быть 0) |
| **Error rate** | <1% | `journalctl -u x0tta6bl4-bot --since "1 hour ago" \| grep -iE "ERROR\|CRITICAL" \| wc -l` |
| **Admin auth working** | 100% | Тест вручную через бота |

---

## 🔄 Rollback Plan

Если что-то пошло не так:

```bash
#!/bin/bash
# rollback_security_fixes.sh

echo "🔄 Rolling back security fixes..."

# 1. Restore database
latest_backup=$(ls -t x0tta6bl4_users.db.backup_pre_security_* | head -1)
if [ -f "$latest_backup" ]; then
    cp "$latest_backup" x0tta6bl4_users.db
    echo "✅ Database restored from: $latest_backup"
else
    echo "❌ No backup found!"
    exit 1
fi

# 2. Restore code (if using git)
# git reset --hard HEAD~1

# 3. Restart bot
systemctl restart x0tta6bl4-bot

# 4. Verify rollback
sleep 5
if systemctl is-active --quiet x0tta6bl4-bot; then
    echo "✅ Rollback successful"
else
    echo "❌ Rollback failed - check logs"
    journalctl -u x0tta6bl4-bot -n 50
    exit 1
fi
```

---

## 📝 Post-Deployment Checklist

После успешного деплоя:

- [ ] Все тесты пройдены
- [ ] Bot работает (systemctl status)
- [ ] UUID уникальны (проверка в БД)
- [ ] Admin команды работают
- [ ] Trial активация работает
- [ ] Нет ошибок в логах
- [ ] Мониторинг 5 минут завершен
- [ ] Пользователи не пострадали (count совпадает)

---

## 🎯 Next Steps

### Week 1: Monitoring & Stability
- Проверять логи 2 раза в день
- Собирать feedback от пользователей
- Отслеживать метрики

### Week 2: Enhanced Security
- Redis-based rate limiting (P1)
- Database encryption для PII (P1)
- Error message sanitization (P0 - pending)

### Month 1: Advanced Features
- Prometheus metrics integration
- Grafana dashboards
- Post-quantum cryptography POC

---

**Готово к deployment! 🚀**

