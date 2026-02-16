# 🚀 ДЕПЛОЙ ПРЯМО СЕЙЧАС

**Токен:** `7841762852:AAEJGXwCbhSh4yGGz0F_qQv_wUprDnGnorE`  
**VPS:** `89.125.1.107`  
**Статус:** Готов к деплою

---

## ⚡ БЫСТРЫЙ ДЕПЛОЙ (5 минут)

### Вариант A: Если файлы уже на VPS

```bash
# 1. Подключись к VPS
ssh root@89.125.1.107

# 2. Перейди в директорию проекта
cd /mnt/AC74CC2974CBF3DC

# 3. Задеплой бота
export TELEGRAM_BOT_TOKEN="7841762852:AAEJGXwCbhSh4yGGz0F_qQv_wUprDnGnorE"
sudo ./deploy_bot.sh

# 4. Проверь статус
sudo systemctl status x0tta6bl4-bot
```

### Вариант B: Если нужно загрузить файлы на VPS

```bash
# 1. На твоём PC - загрузи файлы
cd /mnt/AC74CC2974CBF3DC
scp telegram_bot.py database.py vpn_config_generator.py qr_code_generator.py admin_commands.py keyboards.py rate_limiter.py notifications.py requirements_bot.txt deploy_bot.sh root@89.125.1.107:/root/x0tta6bl4/

# 2. Подключись к VPS
ssh root@89.125.1.107

# 3. Задеплой
cd /root/x0tta6bl4
export TELEGRAM_BOT_TOKEN="7841762852:AAEJGXwCbhSh4yGGz0F_qQv_wUprDnGnorE"
sudo ./deploy_bot.sh
```

---

## 🌐 ДЕПЛОЙ LANDING PAGE

```bash
# На твоём PC
cd /mnt/AC74CC2974CBF3DC
./deploy_landing.sh
```

Или вручную:
```bash
scp deployment/landing_simple.html root@89.125.1.107:/var/www/html/landing.html
```

---

## ✅ ПРОВЕРКА

### 1. Проверить бота в Telegram:
- Найди бота (username который указал в @BotFather)
- Отправь `/start`
- Должен ответить с кнопками

### 2. Проверить landing page:
```bash
curl http://89.125.1.107/landing.html
```

Или открой: `http://89.125.1.107/landing.html`

### 3. Проверить логи:
```bash
ssh root@89.125.1.107 'journalctl -u x0tta6bl4-bot -f'
```

---

## 🔧 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Бот не отвечает:
```bash
# Проверить статус
ssh root@89.125.1.107 'systemctl status x0tta6bl4-bot'

# Посмотреть логи
ssh root@89.125.1.107 'journalctl -u x0tta6bl4-bot -n 50'

# Перезапустить
ssh root@89.125.1.107 'systemctl restart x0tta6bl4-bot'
```

### Ошибки зависимостей:
```bash
ssh root@89.125.1.107 'pip3 install aiogram==2.25.1 qrcode[pil]==7.4.2'
```

---

## 📊 ПОСЛЕ ДЕПЛОЯ

1. ✅ Бот работает → протестируй `/start`, `/trial`, `/help`
2. ✅ Landing page доступен → проверь ссылки
3. ⏳ Пости в каналы → используй `marketing_post_template.md`
4. ⏳ Отслеживай signups → `/admin_stats` в боте

---

**Всё готово! Запускай деплой! 🚀**

