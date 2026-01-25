# Deployment Guide: Causal Analysis Demo

**Quick Reference** для развёртывания интерактивного demo dashboard.

---

## 🎯 Выбор варианта deployment

| Вариант | Время | Стоимость | Рекомендация |
|---------|-------|-----------|--------------|
| **VPS** | 1-2 часа | $5-15/месяц | ✅ Production |
| **Ngrok** | 5 минут | Бесплатно | ✅ Quick test |
| **GitHub Pages** | 30 минут | Бесплатно | ⚠️ Только статика |

---

## 📦 Вариант 1: VPS Deployment (Production)

### Требования

- VPS с Ubuntu/Debian (DigitalOcean, Hetzner, AWS, etc)
- SSH доступ
- Доменное имя (опционально, но рекомендуется)
- 1GB RAM минимум

### Быстрый старт

```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/deploy_vps.sh
```

Скрипт спросит:
- VPS host (user@hostname)
- Deployment path
- Domain name (для SSL)

### Пошаговая инструкция

#### Шаг 1: Подготовка VPS

```bash
# На вашем компьютере
ssh user@your-vps-ip

# На VPS
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx certbot
```

#### Шаг 2: Deploy приложения

```bash
# На вашем компьютере
./scripts/deploy_vps.sh
```

Или вручную:

```bash
# На вашем компьютере
cd /mnt/AC74CC2974CBF3DC
scp -r src web pyproject.toml user@vps:/opt/x0tta6bl4-demo/

# На VPS
cd /opt/x0tta6bl4-demo
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

#### Шаг 3: Systemd Service

```bash
# На VPS
sudo tee /etc/systemd/system/x0tta6bl4-demo.service > /dev/null <<EOF
[Unit]
Description=x0tta6bl4 Causal Analysis Demo
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=/opt/x0tta6bl4-demo
Environment="PATH=/opt/x0tta6bl4-demo/venv/bin"
ExecStart=/opt/x0tta6bl4-demo/venv/bin/python -m src.core.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable x0tta6bl4-demo
sudo systemctl start x0tta6bl4-demo
```

#### Шаг 4: Nginx + SSL

```bash
# На VPS
sudo tee /etc/nginx/sites-available/x0tta6bl4-demo > /dev/null <<EOF
server {
    listen 80;
    server_name demo.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/x0tta6bl4-demo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# SSL certificate
sudo certbot --nginx -d demo.yourdomain.com
```

#### Шаг 5: Проверка

```bash
# Проверить статус
sudo systemctl status x0tta6bl4-demo

# Посмотреть логи
sudo journalctl -u x0tta6bl4-demo -f

# Открыть в браузере
https://demo.yourdomain.com/demo/causal-dashboard.html
```

### Troubleshooting

**Проблема**: Service не запускается
```bash
# Проверить логи
sudo journalctl -u x0tta6bl4-demo -n 50

# Проверить порт
sudo netstat -tlnp | grep 8000
```

**Проблема**: Nginx 502 Bad Gateway
```bash
# Проверить что app работает
curl http://127.0.0.1:8000/health

# Проверить nginx config
sudo nginx -t
```

**Проблема**: SSL certificate не устанавливается
```bash
# Проверить DNS
dig demo.yourdomain.com

# Убедиться что порт 80 открыт
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 🚀 Вариант 2: Ngrok (Quick Test)

### Быстрый старт

```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/deploy_ngrok.sh
```

### Пошаговая инструкция

#### Шаг 1: Установка ngrok

```bash
# Linux
curl -L https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o ngrok.tgz
tar -xzf ngrok.tgz
sudo mv ngrok /usr/local/bin/

# macOS
brew install ngrok/ngrok/ngrok
```

#### Шаг 2: Аутентификация

```bash
# 1. Зарегистрируйтесь на https://dashboard.ngrok.com
# 2. Получите authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN
```

#### Шаг 3: Запуск

```bash
# В терминале 1: Запустить app
cd /mnt/AC74CC2974CBF3DC
python -m src.core.app

# В терминале 2: Запустить ngrok
ngrok http 8000
```

#### Шаг 4: Получить URL

Ngrok покажет public URL:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

Используйте: `https://xxxxx.ngrok.io/demo/causal-dashboard.html`

### Ограничения

- ⚠️ Free tier: 24 часа, затем URL меняется
- ⚠️ Rate limits на free tier
- ⚠️ Не для production email

---

## 📄 Вариант 3: GitHub Pages (Static Only)

### Быстрый старт

```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/deploy_demo.sh github-pages
```

### Ограничения

- ❌ Только статичный HTML (без API)
- ❌ "Load Demo" кнопка не работает полностью
- ✅ Бесплатно, HTTPS автоматически

---

## 🔧 Локальный тест (перед deployment)

```bash
# 1. Запустить сервер
cd /mnt/AC74CC2974CBF3DC
python -m src.core.app

# 2. Открыть в браузере
http://localhost:8000/demo/causal-dashboard.html

# 3. Нажать "Load Demo Incident"
# 4. Проверить:
#    - Timeline анимируется
#    - Dependency graph отображается
#    - Root causes показываются
#    - Metrics обновляются
```

---

## 📧 Интеграция с Email

### После deployment

1. **Скопируйте demo URL**
   ```
   https://demo.yourdomain.com/demo/causal-dashboard.html
   ```

2. **Откройте EMAIL_TEMPLATE_V3.md**

3. **Замените переменные**:
   - `[DEMO_LINK]` → ваш URL
   - `[Name]` → имя получателя
   - `[SCHEDULE_LINK]` → ссылка на календарь

4. **Добавьте UTM параметры**:
   ```
   https://demo.yourdomain.com/demo/causal-dashboard.html?utm_source=email&utm_medium=wave3&utm_campaign=causal_demo
   ```

5. **Отправьте email**

---

## ✅ Pre-Deployment Checklist

- [ ] Локальный тест пройден
- [ ] VPS доступен (или ngrok установлен)
- [ ] Доменное имя настроено (для VPS)
- [ ] SSL сертификат установлен (для VPS)
- [ ] Service запущен и работает
- [ ] Demo URL открывается в браузере
- [ ] "Load Demo" кнопка работает
- [ ] Animations работают
- [ ] Mobile-friendly проверено
- [ ] Email template обновлён с demo URL

---

## 🆘 Troubleshooting Guide

### Общие проблемы

**Проблема**: "Connection refused"
- Проверьте что сервер запущен: `sudo systemctl status x0tta6bl4-demo`
- Проверьте порт: `netstat -tlnp | grep 8000`

**Проблема**: "Load Demo" не работает
- Проверьте API endpoint: `curl http://localhost:8000/api/causal-analysis/demo`
- Проверьте логи: `sudo journalctl -u x0tta6bl4-demo -f`

**Проблема**: Dashboard не загружается
- Проверьте что файлы на месте: `ls -la web/demo/`
- Проверьте nginx config: `sudo nginx -t`

### Логи и отладка

```bash
# Application logs
sudo journalctl -u x0tta6bl4-demo -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log

# Test API
curl http://localhost:8000/api/causal-analysis/demo -X POST

# Test health
curl http://localhost:8000/health
```

---

## 📊 Мониторинг

### Health Check

```bash
# Добавить в cron или monitoring
curl -f http://localhost:8000/health || alert "Demo down!"
```

### Uptime Monitoring

Используйте:
- UptimeRobot (бесплатно)
- Pingdom
- StatusCake

---

**Дата создания**: 2025-01-XX  
**Версия**: 1.0.0  
**Статус**: Production Ready ✅

