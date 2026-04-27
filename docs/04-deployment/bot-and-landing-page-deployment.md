# 🚀 Инструкции по деплою с токеном

**Токен получен:** `<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>`

---

## Вариант 1: Деплой на VPS (89.125.1.107)

### Шаг 1: Подключиться к VPS
```bash
ssh root@89.125.1.107
```

### Шаг 2: Загрузить файлы (если нужно)
```bash
# На твоём PC
cd /mnt/AC74CC2974CBF3DC
scp -r telegram_bot.py database.py vpn_config_generator.py qr_code_generator.py admin_commands.py keyboards.py rate_limiter.py notifications.py requirements_bot.txt deploy_bot.sh root@89.125.1.107:/root/x0tta6bl4/
```

### Шаг 3: Задеплоить бота на VPS
```bash
# На VPS
cd /root/x0tta6bl4  # или /mnt/AC74CC2974CBF3DC если там
export TELEGRAM_BOT_TOKEN="<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>"
sudo ./deploy_bot.sh
```

### Шаг 4: Проверить статус
```bash
sudo systemctl status x0tta6bl4-bot
sudo journalctl -u x0tta6bl4-bot -f
```

---

## Вариант 2: Деплой с локального PC (если есть SSH доступ)

### Если файлы уже на VPS:
```bash
ssh root@89.125.1.107 "cd /mnt/AC74CC2974CBF3DC && export TELEGRAM_BOT_TOKEN='<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>' && sudo ./deploy_bot.sh"
```

---

## Деплой Landing Page

```bash
cd /mnt/AC74CC2974CBF3DC
./deploy_landing.sh
```

Или вручную:
```bash
scp deployment/landing_simple.html root@89.125.1.107:/var/www/html/landing.html
```

---

## Проверка работы

### 1. Проверить бота в Telegram:
- Найди бота по username (который указал в @BotFather)
- Отправь `/start`
- Должен ответить с кнопками

### 2. Проверить landing page:
```bash
curl http://89.125.1.107/landing.html
```

Или открой в браузере: `http://89.125.1.107/landing.html`

### 3. Проверить логи бота:
```bash
ssh root@89.125.1.107 'journalctl -u x0tta6bl4-bot -n 50'
```

---

## Troubleshooting

### Бот не отвечает:
```bash
# Проверить что сервис запущен
ssh root@89.125.1.107 'systemctl status x0tta6bl4-bot'

# Проверить логи
ssh root@89.125.1.107 'journalctl -u x0tta6bl4-bot -n 100'

# Перезапустить
ssh root@89.125.1.107 'systemctl restart x0tta6bl4-bot'
```

### Ошибки импорта:
```bash
# Установить зависимости вручную
ssh root@89.125.1.107 'pip3 install aiogram==2.25.1 qrcode[pil]==7.4.2'
```

---

## Следующие шаги после деплоя:

1. ✅ Бот работает
2. ✅ Landing page доступен
3. ⏳ Постить в Telegram каналы (использовать `marketing_post_template.md`)
4. ⏳ Постить на Reddit (r/privacy, r/VPN)
5. ⏳ Отслеживать signups: `/admin_stats` в боте

---

**Готово к деплою! 🚀**

