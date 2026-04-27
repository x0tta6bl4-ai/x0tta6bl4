# 📋 КОПИРУЙ-ВСТАВЛЯЙ: Деплой за 2 минуты

## Шаг 1: Подключись к VPS

```bash
ssh root@89.125.1.107
```

## Шаг 2: Перейди в директорию проекта

```bash
cd /mnt/AC74CC2974CBF3DC
```

(Если директории нет, создай: `mkdir -p /mnt/AC74CC2974CBF3DC && cd /mnt/AC74CC2974CBF3DC`)

## Шаг 3: Загрузи файлы (если их нет на VPS)

**На твоём PC выполни:**

```bash
cd /mnt/AC74CC2974CBF3DC
scp telegram_bot.py database.py vpn_config_generator.py qr_code_generator.py admin_commands.py keyboards.py rate_limiter.py notifications.py requirements_bot.txt root@89.125.1.107:/mnt/AC74CC2974CBF3DC/
```

## Шаг 4: Задеплой бота (на VPS)

**Скопируй и выполни всё это на VPS:**

```bash
export TELEGRAM_BOT_TOKEN="<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>"
cd /mnt/AC74CC2974CBF3DC

# Установить зависимости
pip3 install aiogram==2.25.1 qrcode[pil]==7.4.2 || pip3 install --break-system-packages aiogram==2.25.1 qrcode[pil]==7.4.2

# Инициализировать БД
python3 -c "from database import init_database; init_database()"

# Создать systemd service
cat > /etc/systemd/system/x0tta6bl4-bot.service <<'EOF'
[Unit]
Description=x0tta6bl4 Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mnt/AC74CC2974CBF3DC
Environment="TELEGRAM_BOT_TOKEN=<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>"
ExecStart=/usr/bin/python3 /mnt/AC74CC2974CBF3DC/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Запустить сервис
systemctl daemon-reload
systemctl enable x0tta6bl4-bot
systemctl start x0tta6bl4-bot

# Проверить статус
systemctl status x0tta6bl4-bot
```

## Шаг 5: Проверить работу

```bash
# Посмотреть логи
journalctl -u x0tta6bl4-bot -f
```

**В Telegram:**
- Найди бота (username который указал в @BotFather)
- Отправь `/start`
- Должен ответить!

---

## 🌐 Деплой Landing Page

**На твоём PC:**

```bash
cd /mnt/AC74CC2974CBF3DC
scp deployment/landing_simple.html root@89.125.1.107:/var/www/html/landing.html
```

**На VPS (если нужно настроить nginx):**

```bash
# Проверить nginx
nginx -t

# Если нужно создать конфиг
cat > /etc/nginx/sites-available/x0tta6bl4 <<'EOF'
server {
    listen 80;
    server_name 89.125.1.107;
    
    root /var/www/html;
    index landing.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

ln -s /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

**Проверить:**
```bash
curl http://89.125.1.107/landing.html
```

---

## 🔧 Troubleshooting

### Бот не отвечает:

```bash
# Проверить статус
systemctl status x0tta6bl4-bot

# Посмотреть логи
journalctl -u x0tta6bl4-bot -n 50

# Перезапустить
systemctl restart x0tta6bl4-bot
```

### Ошибки импорта:

```bash
# Установить зависимости
pip3 install aiogram==2.25.1 qrcode[pil]==7.4.2
```

### Файлы не найдены:

```bash
# Проверить что файлы на месте
ls -la /mnt/AC74CC2974CBF3DC/telegram_bot.py
ls -la /mnt/AC74CC2974CBF3DC/database.py
```

---

**Готово! Бот должен работать! 🚀**

