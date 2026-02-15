# 🚀 Week 1 Deployment Plan: Первые пользователи

**Цель:** 10 trial users к выходным

---

## ✅ Что уже готово:

1. **Landing page** — `deployment/landing_simple.html` (создан)
2. **Telegram bot** — `telegram_bot.py` (создан)
3. **VPN сервер** — 89.125.1.107:39829 (работает)
4. **Docker compose** — `docker-compose.yml` (есть)

---

## 📋 Day 1-2: Setup Telegram Bot

### 1. Создать бота через @BotFather

```bash
# В Telegram:
1. Напиши @BotFather
2. /newbot
3. Имя: x0tta6bl4 VPN
4. Username: x0tta6bl4_bot
5. Скопируй токен
```

### 2. Настроить платежи (опционально, можно позже)

```bash
# В Telegram:
1. @BotFather → /mybots → выбери бота
2. Bot Settings → Payments
3. Выбери провайдера (Stripe, YooMoney, etc.)
4. Скопируй Provider Token
```

### 3. Установить зависимости

```bash
cd /mnt/AC74CC2974CBF3DC
pip install aiogram
```

### 4. Запустить бота

```bash
export TELEGRAM_BOT_TOKEN="твой_токен_от_BotFather"
export TELEGRAM_PAYMENT_TOKEN="токен_провайдера"  # опционально

python3 telegram_bot.py
```

**Или через systemd:**

```bash
sudo nano /etc/systemd/system/x0tta6bl4-bot.service
```

```ini
[Unit]
Description=x0tta6bl4 Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mnt/AC74CC2974CBF3DC
Environment="TELEGRAM_BOT_TOKEN=твой_токен"
ExecStart=/usr/bin/python3 /mnt/AC74CC2974CBF3DC/telegram_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable x0tta6bl4-bot
sudo systemctl start x0tta6bl4-bot
sudo systemctl status x0tta6bl4-bot
```

---

## 📋 Day 3-4: Deploy Landing Page на VPS

### 1. Загрузить landing page на 89.125.1.107

```bash
# На твоём PC
scp deployment/landing_simple.html root@89.125.1.107:/var/www/html/index.html

# Или через nginx
scp deployment/landing_simple.html root@89.125.1.107:/var/www/html/landing.html
```

### 2. Настроить nginx (если нужно)

```bash
# На VPS (89.125.1.107)
sudo nano /etc/nginx/sites-available/x0tta6bl4
```

```nginx
server {
    listen 80;
    server_name 89.125.1.107;
    
    root /var/www/html;
    index landing.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Проверить доступность

```bash
curl http://89.125.1.107/landing.html
# Должен вернуть HTML
```

---

## 📋 Day 5-7: User Acquisition

### 1. Telegram каналы про VPN

**Где постить:**
- Каналы про VPN в Крыму/России
- IT-комьюнити
- Privacy-focused каналы

**Текст поста:**

```
🔥 Новый VPN который НЕ ПАДАЕТ

Проблема: Обычные VPN тормозят и ломаются. Один сервер упал — всё не работает.

Решение: x0tta6bl4 — self-healing mesh network. Если один узел падает — автопереключение за 3 минуты.

✅ Ping <80ms из Крыма
✅ Локальное шифрование (твои данные в безопасности)
✅ Безлимитный трафик

Попробуй 7 дней БЕСПЛАТНО:
👉 https://t.me/x0tta6bl4_bot?start=trial

Landing: http://89.125.1.107/landing.html
```

### 2. Reddit / VC.ru / Habr

**Reddit:**
- r/privacy
- r/VPN
- r/selfhosted

**VC.ru:**
- Пост в раздел "Стартапы" или "IT"

**Habr:**
- Статья "Как я построил self-healing VPN mesh network"

### 3. Pikabu (если есть аккаунт)

**Пост:**
```
TL;DR: Сделал VPN который сам чинится. Даю 7 дней бесплатно.

Длинная версия: [ссылка на landing]
```

---

## 📊 Метрики для отслеживания:

| Метрика | Цель Week 1 |
|---------|-------------|
| Trial signups | 10 |
| Telegram bot users | 10+ |
| Landing page views | 100+ |
| Conversions (trial → paid) | 0-2 (нормально) |

---

## 🔧 Troubleshooting:

### Бот не отвечает:
```bash
# Проверить логи
sudo journalctl -u x0tta6bl4-bot -f

# Проверить токен
echo $TELEGRAM_BOT_TOKEN
```

### Landing page не открывается:
```bash
# Проверить nginx
sudo systemctl status nginx
sudo nginx -t

# Проверить файл
ls -la /var/www/html/landing.html
```

### VPN не работает:
```bash
# Проверить Xray
sudo systemctl status xray

# Проверить порт
netstat -tulpn | grep 39829
```

---

## ✅ Checklist перед запуском:

- [ ] Telegram bot создан через @BotFather
- [ ] `TELEGRAM_BOT_TOKEN` установлен
- [ ] Бот запущен и отвечает на /start
- [ ] Landing page загружен на VPS
- [ ] Landing page открывается в браузере
- [ ] Ссылки на бота работают
- [ ] VPN сервер работает (89.125.1.107:39829)
- [ ] Готов пост для Telegram каналов

---

## 🎯 Next Steps (Week 2):

1. Автоматизация генерации VPN конфигов
2. Интеграция с Xray API
3. Dashboard для пользователей
4. Payment gateway (если не сделано)

---

**Главное:** Не жди идеального продукта. Запускай с тем что есть. Первые пользователи дадут feedback.

