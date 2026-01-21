# 🚀 VPS DEPLOYMENT PLAN (89.125.1.107)

**Дата:** 27 декабря 2025  
**Статус:** ✅ **SYSTEM ANALYZED - READY FOR DEPLOYMENT**

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ

### ✅ Что уже работает:

1. **VPN (Xray)**
   - ✅ Xray service активен
   - ✅ X-UI panel на порту 628
   - ✅ VPN connections работают (порт 39829)
   - ✅ xray-exporter на порту 9090 (мониторинг)

2. **x0tta6bl4 (старая версия)**
   - ✅ x0t-node контейнер запущен (порт 8081)
   - ✅ Prometheus запущен (порт 9091)
   - ✅ Grafana запущен (порт 3000)
   - ⚠️ Старая версия (нет /health endpoint)

3. **Система**
   - ✅ Docker установлен (v29.0.2)
   - ✅ Ubuntu 24.04.3 LTS
   - ✅ RAM: 3.8 GB (используется 867 MB)
   - ✅ Disk: 40 GB (используется 24 GB, свободно 14 GB)

### ⚠️ Что нужно исправить:

1. **Порт 8080**
   - Занят простым `python3 -m http.server`
   - Можно остановить (не критично)

2. **x0t-node**
   - Старая версия без /health endpoint
   - Нужно обновить до новой версии

3. **Nginx**
   - Не установлен
   - Нужен для reverse proxy

---

## 🎯 ПЛАН ДЕЙСТВИЙ

### Вариант 1: Обновить существующий x0t-node (РЕКОМЕНДУЕТСЯ)

**Преимущества:**
- ✅ Сохраняет существующую конфигурацию
- ✅ Не нужно менять порты
- ✅ Быстрее

**Шаги:**
1. Остановить старый x0t-node контейнер
2. Загрузить новый Docker image
3. Запустить обновленный контейнер
4. Проверить /health endpoint

### Вариант 2: Развернуть новый control-plane

**Преимущества:**
- ✅ Чистая установка
- ✅ Можно использовать порт 8080

**Шаги:**
1. Остановить `python3 -m http.server` на 8080
2. Развернуть новый control-plane на 8080
3. Настроить Nginx для reverse proxy

---

## 🔧 ДЕТАЛЬНЫЙ ПЛАН (Вариант 1)

### Шаг 1: Подготовка

```bash
# Подключиться к VPS
ssh root@89.125.1.107

# Остановить старый контейнер
docker stop x0t-node

# Остановить простой http.server (опционально)
systemctl stop http-server-8080 2>/dev/null || pkill -f "python3 -m http.server 8080"
```

### Шаг 2: Загрузка нового образа

```bash
# На локальной машине
cd /mnt/AC74CC2974CBF3DC
docker build -t x0tta6bl4-app:staging -f Dockerfile.app .
docker save x0tta6bl4-app:staging | gzip > /tmp/x0tta6bl4-app-staging.tar.gz

# Копировать на VPS
scp /tmp/x0tta6bl4-app-staging.tar.gz root@89.125.1.107:/root/

# На VPS - загрузить образ
ssh root@89.125.1.107
docker load < /root/x0tta6bl4-app-staging.tar.gz
```

### Шаг 3: Обновление контейнера

```bash
# Удалить старый контейнер
docker rm x0t-node

# Запустить новый с теми же портами
docker run -d \
  --name x0t-node \
  --restart unless-stopped \
  -p 8081:8080 \
  -p 10809:10809 \
  -e NODE_ID=node-vps1 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  x0tta6bl4-app:staging
```

### Шаг 4: Установка Nginx

```bash
# Установить Nginx
apt update
apt install nginx -y

# Создать конфигурацию
cat > /etc/nginx/sites-available/x0tta6bl4 <<EOF
server {
    listen 80;
    server_name 89.125.1.107;

    location / {
        proxy_pass http://localhost:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    location /health {
        proxy_pass http://localhost:8081/health;
        access_log off;
    }

    location /metrics {
        proxy_pass http://localhost:8081/metrics;
    }
}
EOF

# Включить сайт
ln -sf /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### Шаг 5: Проверка

```bash
# Проверить health endpoint
curl http://localhost:8081/health
curl http://89.125.1.107/health

# Проверить что VPN работает
systemctl status xray

# Проверить логи
docker logs x0t-node -f
```

---

## 📋 АВТОМАТИЗИРОВАННЫЙ СКРИПТ

Создан скрипт `scripts/vps_update_existing.sh` который:
1. ✅ Останавливает старый контейнер
2. ✅ Загружает новый образ
3. ✅ Запускает обновленный контейнер
4. ✅ Настраивает Nginx
5. ✅ Проверяет health endpoint

**Использование:**
```bash
./scripts/vps_update_existing.sh 89.125.1.107 root
```

---

## 🔍 ПОРТЫ ПОСЛЕ DEPLOYMENT

```
22      - SSH ✅
80      - Nginx (reverse proxy) ✅
443     - VPN (Xray) ✅
628     - X-UI Panel ✅
3000    - Grafana ✅
8081    - x0tta6bl4 (mapped from 8080) ✅
9090    - xray-exporter ✅
9091    - Prometheus ✅
10809   - x0tta6bl4 mesh ✅
39829   - VPN (Xray) ✅
```

**Конфликтов нет!** ✅

---

## 📊 РЕСУРСЫ ПОСЛЕ DEPLOYMENT

```
RAM: ~1.2 GB / 3.8 GB (32%) ✅
Disk: ~25 GB / 40 GB (63%) ✅
CPU: ~30-40% ✅
```

**Ресурсов достаточно!** ✅

---

## ✅ CHECKLIST

- [x] Система проанализирована
- [x] VPN работает и сохранен
- [x] План deployment готов
- [ ] Обновить x0t-node контейнер
- [ ] Установить Nginx
- [ ] Проверить health endpoint
- [ ] Проверить что VPN работает

---

**Дата:** 27 декабря 2025  
**Статус:** ✅ **READY TO DEPLOY**

