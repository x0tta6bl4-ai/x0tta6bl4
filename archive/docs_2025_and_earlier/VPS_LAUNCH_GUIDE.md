# 🚀 VPS LAUNCH GUIDE - Micro Launch (2-3 часа)

**Вариант:** A - Micro Launch на VPS  
**Время:** 2-3 часа  
**Дата:** 27 декабря 2025

---

## 📋 ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

### VPS Requirements
- [ ] VPS с Ubuntu 20.04+ или Debian 11+
- [ ] Минимум 2GB RAM, 2 CPU cores, 20GB disk
- [ ] Root доступ или sudo user
- [ ] Открытые порты: 22 (SSH), 80 (HTTP), 443 (HTTPS, опционально), 8080 (App)

### Local Setup
- [ ] SSH доступ к VPS
- [ ] Docker установлен на VPS (или установим)
- [ ] Локально: Docker image собран

---

## 🚀 ШАГ 1: ПОДГОТОВКА VPS (30 минут)

### 1.1 Подключись к VPS

```bash
ssh root@YOUR_VPS_IP
# или
ssh user@YOUR_VPS_IP
```

### 1.2 Обнови систему

```bash
apt update && apt upgrade -y
```

### 1.3 Установи Docker (если нет)

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Добавить пользователя в docker group (если не root)
usermod -aG docker $USER

# Проверить
docker --version
```

### 1.4 Установи Docker Compose (если нет)

```bash
apt install docker-compose -y
# или
pip3 install docker-compose
```

### 1.5 Настрой Firewall

```bash
# UFW (если используется)
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8080/tcp
ufw enable

# Или iptables
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

---

## 🚀 ШАГ 2: DEPLOYMENT (1-2 часа)

### Вариант A: Автоматический (рекомендуется)

Используй готовый скрипт:

```bash
# На локальной машине
cd /mnt/AC74CC2974CBF3DC
./scripts/vps_deploy.sh YOUR_VPS_IP
```

### Вариант B: Ручной

#### 2.1 Собери Docker image локально

```bash
cd /mnt/AC74CC2974CBF3DC
docker build -t x0tta6bl4-app:staging -f Dockerfile.app .
```

#### 2.2 Сохрани image в tar

```bash
docker save x0tta6bl4-app:staging | gzip > x0tta6bl4-app-staging.tar.gz
```

#### 2.3 Скопируй на VPS

```bash
scp x0tta6bl4-app-staging.tar.gz root@YOUR_VPS_IP:/root/
```

#### 2.4 На VPS: Загрузи image

```bash
ssh root@YOUR_VPS_IP
docker load < x0tta6bl4-app-staging.tar.gz
docker images | grep x0tta6bl4
```

#### 2.5 Создай docker-compose.yml на VPS

```bash
cat > /root/docker-compose.yml <<'EOF'
version: '3.8'

services:
  x0tta6bl4-app:
    image: x0tta6bl4-app:staging
    container_name: x0tta6bl4-production
    ports:
      - "8080:8080"
      - "9090:9090"
    environment:
      - NODE_ID=production-control-plane
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    volumes:
      - ./data:/app/data
    networks:
      - x0tta6bl4-network

networks:
  x0tta6bl4-network:
    driver: bridge
EOF
```

#### 2.6 Запусти контейнер

```bash
cd /root
docker-compose up -d
```

#### 2.7 Проверь статус

```bash
docker ps
docker logs x0tta6bl4-production
```

---

## 🚀 ШАГ 3: NGINX REVERSE PROXY (30 минут)

### 3.1 Установи Nginx

```bash
apt install nginx -y
```

### 3.2 Создай конфигурацию

```bash
cat > /etc/nginx/sites-available/x0tta6bl4 <<'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8080/health;
        access_log off;
    }

    # Metrics endpoint
    location /metrics {
        proxy_pass http://localhost:8080/metrics;
    }
}
EOF
```

### 3.3 Активируй конфигурацию

```bash
ln -s /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # если нужно
nginx -t
systemctl reload nginx
```

### 3.4 SSL (опционально, но рекомендуется)

```bash
# Установи Certbot
apt install certbot python3-certbot-nginx -y

# Получи SSL сертификат
certbot --nginx -d YOUR_DOMAIN

# Автообновление
certbot renew --dry-run
```

---

## 🚀 ШАГ 4: DNS НАСТРОЙКА (15 минут)

### Если есть домен:

```bash
# A record
YOUR_DOMAIN -> YOUR_VPS_IP

# Или через CloudFlare/DNS провайдера
```

### Если нет домена:

Используй IP адрес напрямую: `http://YOUR_VPS_IP`

---

## ✅ ШАГ 5: ПРОВЕРКА (15 минут)

### 5.1 Health Check

```bash
# Прямо на VPS
curl http://localhost:8080/health

# Снаружи
curl http://YOUR_VPS_IP/health
# или
curl http://YOUR_DOMAIN/health
```

### 5.2 Smoke Tests

```bash
# Health
curl http://YOUR_VPS_IP/health

# Metrics
curl http://YOUR_VPS_IP/metrics

# Mesh peers
curl http://YOUR_VPS_IP/mesh/peers
```

### 5.3 Проверь логи

```bash
docker logs x0tta6bl4-production -f
```

---

## 🔧 МОНИТОРИНГ

### System Monitoring

```bash
# CPU и Memory
htop

# Disk usage
df -h

# Docker stats
docker stats x0tta6bl4-production
```

### Application Monitoring

```bash
# Logs
docker logs x0tta6bl4-production -f

# Metrics endpoint
curl http://YOUR_VPS_IP/metrics
```

### Auto-restart при сбое

Docker Compose уже настроен с `restart: unless-stopped`, но можно добавить systemd service:

```bash
cat > /etc/systemd/system/x0tta6bl4.service <<'EOF'
[Unit]
Description=x0tta6bl4 Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/root
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl enable x0tta6bl4
systemctl start x0tta6bl4
```

---

## 🚨 TROUBLESHOOTING

### Проблема: Контейнер не запускается

```bash
# Проверь логи
docker logs x0tta6bl4-production

# Проверь статус
docker ps -a

# Проверь порты
netstat -tulpn | grep 8080
```

### Проблема: Health check fails

```bash
# Проверь внутри контейнера
docker exec -it x0tta6bl4-production curl http://localhost:8080/health

# Проверь порты
docker port x0tta6bl4-production
```

### Проблема: Nginx не проксирует

```bash
# Проверь конфигурацию
nginx -t

# Проверь логи
tail -f /var/log/nginx/error.log

# Проверь что приложение слушает
curl http://localhost:8080/health
```

### Проблема: Высокое использование памяти

```bash
# Проверь использование
docker stats x0tta6bl4-production

# Если нужно, ограничь память в docker-compose.yml
# Добавь:
# mem_limit: 2g
```

---

## 🔄 ОБНОВЛЕНИЕ

### Обновить приложение

```bash
# 1. На локальной машине: собери новый image
docker build -t x0tta6bl4-app:staging -f Dockerfile.app .

# 2. Сохрани и скопируй
docker save x0tta6bl4-app:staging | gzip > x0tta6bl4-app-staging.tar.gz
scp x0tta6bl4-app-staging.tar.gz root@YOUR_VPS_IP:/root/

# 3. На VPS: загрузи и перезапусти
ssh root@YOUR_VPS_IP
docker load < x0tta6bl4-app-staging.tar.gz
cd /root
docker-compose down
docker-compose up -d
```

---

## 💰 СТОИМОСТЬ

```
VPS:           $5-20/month (зависит от провайдера)
Domain:        $10-15/year (опционально)
SSL:           Free (Let's Encrypt)

TOTAL:         ~$5-20/month
```

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

### После запуска:

1. **Monitor 24/7** (первая неделя)
   - Watch logs
   - Check metrics
   - Monitor system resources

2. **Gather feedback**
   - Test all endpoints
   - Get user feedback
   - Fix any issues

3. **Scale if needed**
   - Add more resources
   - Optimize configuration
   - Consider AWS migration

---

## 📊 ОЖИДАЕМАЯ ПРОИЗВОДИТЕЛЬНОСТЬ

```
Concurrent Users:  10-100
Requests/sec:      50-200
Uptime:            99%+ (с auto-restart)
Latency:           <100ms (локально)
```

---

**Дата:** 27 декабря 2025  
**Статус:** ✅ **READY TO DEPLOY**

