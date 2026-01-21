# 🐳 DOCKER_COMPOSE_ДЛЯ_БАЗИС_ВЕБ.md - Готовый конфиг

**Адаптированный Docker Compose для Базис-Веб + Ollama**  
**Статус:** ✅ ГОТОВ К КОПИРОВАНИЮ И ИСПОЛЬЗОВАНИЮ  
**Дата:** 17 января 2026

---

## 📋 СОДЕРЖАНИЕ

1. [Базовый конфиг (Dev)](#базовый-конфиг-dev)
2. [Расширенный конфиг (Staging)](#расширенный-конфиг-staging)
3. [Production конфиг](#production-конфиг)
4. [Как использовать](#как-использовать)

---

## Базовый конфиг (Dev)

**Файл:** `docker-compose.yml` (для разработки)

```yaml
version: '3.9'

services:
  # ============================================
  # OLLAMA - Local LLM Models
  # ============================================
  ollama:
    image: ollama/ollama:latest
    container_name: bazis-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_NUM_GPU=1
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_MODELS=/models
    volumes:
      - ollama-models:/root/.ollama
      - ./data/ollama:/models
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - bazis-network
    labels:
      - "com.example.description=Local LLM Models (Qwen 32B + Mistral 14B)"

  # ============================================
  # BAZIS-WEB Frontend + Backend
  # ============================================
  bazis-web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: bazis-web-app
    restart: unless-stopped
    ports:
      - "3002:5173"
    environment:
      - NODE_ENV=development
      - VITE_OLLAMA_URL=http://ollama:11434
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
      - LOG_LEVEL=debug
    volumes:
      - ./src:/app/src
      - ./public:/app/public
      - ./components:/app/components
      - ./services:/app/services
    depends_on:
      ollama:
        condition: service_healthy
    networks:
      - bazis-network
    labels:
      - "com.example.description=Базис-Веб furniture design application"

  # ============================================
  # POSTGRES - Project Storage (Optional)
  # ============================================
  postgres:
    image: postgres:15-alpine
    container_name: bazis-postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=bazis
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-bazis123}
      - POSTGRES_DB=bazis_db
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bazis"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bazis-network
    labels:
      - "com.example.description=PostgreSQL for project storage"

  # ============================================
  # REDIS - Caching (Optional)
  # ============================================
  redis:
    image: redis:7-alpine
    container_name: bazis-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bazis-network
    labels:
      - "com.example.description=Redis for caching"

  # ============================================
  # PROMETHEUS - Metrics Collection
  # ============================================
  prometheus:
    image: prom/prometheus:latest
    container_name: bazis-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/alerts.yml:/etc/prometheus/rules.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - bazis-network
    labels:
      - "com.example.description=Prometheus metrics"

  # ============================================
  # GRAFANA - Dashboards
  # ============================================
  grafana:
    image: grafana/grafana:latest
    container_name: bazis-grafana
    restart: unless-stopped
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_SECURITY_ADMIN_USER=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
    networks:
      - bazis-network
    labels:
      - "com.example.description=Grafana dashboards"

volumes:
  ollama-models:
    driver: local
  postgres-data:
    driver: local
  redis-data:
    driver: local
  prometheus-data:
    driver: local
  grafana-data:
    driver: local

networks:
  bazis-network:
    driver: bridge
```

---

## Расширенный конфиг (Staging)

**Файл:** `docker-compose.staging.yml` (для staging окружения)

```yaml
version: '3.9'

services:
  # Все сервисы из базовой конфигурации +

  # ============================================
  # JAEGER - Distributed Tracing
  # ============================================
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: bazis-jaeger
    restart: unless-stopped
    ports:
      - "6831:6831/udp"
      - "16686:16686"
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - bazis-network
    labels:
      - "com.example.description=Jaeger distributed tracing"

  # ============================================
  # ALERTMANAGER - Alert Management
  # ============================================
  alertmanager:
    image: prom/alertmanager:latest
    container_name: bazis-alertmanager
    restart: unless-stopped
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/config.yml:ro
      - alertmanager-data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/config.yml'
      - '--storage.path=/alertmanager'
    networks:
      - bazis-network
    labels:
      - "com.example.description=Alert management"

  # ============================================
  # NGINX - Reverse Proxy
  # ============================================
  nginx:
    image: nginx:alpine
    container_name: bazis-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - nginx-logs:/var/log/nginx
    depends_on:
      - bazis-web
      - prometheus
      - grafana
    networks:
      - bazis-network
    labels:
      - "com.example.description=Nginx reverse proxy"

volumes:
  alertmanager-data:
  nginx-logs:

networks:
  bazis-network:
    driver: bridge
```

---

## Production конфиг

**Файл:** `docker-compose.prod.yml` (для production)

```yaml
version: '3.9'

services:
  # ============================================
  # OLLAMA - Production Setup
  # ============================================
  ollama:
    image: ollama/ollama:latest
    container_name: bazis-ollama-prod
    restart: always
    ports:
      - "11434:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_NUM_GPU=1
      - OLLAMA_KEEP_ALIVE=72h
      - OLLAMA_MODELS=/models
    volumes:
      - ollama-models:/root/.ollama
      - /mnt/data/ollama:/models
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # ============================================
  # BAZIS-WEB - Production Setup
  # ============================================
  bazis-web:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: bazis-web-prod
    restart: always
    environment:
      - NODE_ENV=production
      - VITE_OLLAMA_URL=http://ollama:11434
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - LOG_LEVEL=info
    depends_on:
      ollama:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  # ============================================
  # POSTGRES - Production Setup
  # ============================================
  postgres:
    image: postgres:15-alpine
    container_name: bazis-postgres-prod
    restart: always
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      - POSTGRES_USER=bazis
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=bazis_db
      - POSTGRES_INITDB_ARGS=--encoding=UTF8
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - /mnt/backups/postgres:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bazis"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # REDIS - Production Setup
  # ============================================
  redis:
    image: redis:7-alpine
    container_name: bazis-redis-prod
    restart: always
    ports:
      - "127.0.0.1:6379:6379"
    command: redis-server --appendonly yes --appendfsync everysec
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # PROMETHEUS - Production Setup
  # ============================================
  prometheus:
    image: prom/prometheus:latest
    container_name: bazis-prometheus-prod
    restart: always
    ports:
      - "127.0.0.1:9090:9090"
    volumes:
      - ./monitoring/prometheus.prod.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/alerts.yml:/etc/prometheus/rules.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=90d'
      - '--web.enable-lifecycle'
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # ALERTMANAGER - Production Setup
  # ============================================
  alertmanager:
    image: prom/alertmanager:latest
    container_name: bazis-alertmanager-prod
    restart: always
    ports:
      - "127.0.0.1:9093:9093"
    volumes:
      - ./monitoring/alertmanager.prod.yml:/etc/alertmanager/config.yml:ro
      - alertmanager-data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/config.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://alerts.bazis.local'
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # GRAFANA - Production Setup
  # ============================================
  grafana:
    image: grafana/grafana:latest
    container_name: bazis-grafana-prod
    restart: always
    ports:
      - "127.0.0.1:3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_SECURITY_ADMIN_USER=admin
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
      - GF_SECURITY_COOKIE_SECURE=true
      - GF_SECURITY_COOKIE_SAMESITE=strict
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # NGINX - Production Setup
  # ============================================
  nginx:
    image: nginx:alpine
    container_name: bazis-nginx-prod
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - nginx-logs:/var/log/nginx
    depends_on:
      - bazis-web
    networks:
      - bazis-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"

volumes:
  ollama-models:
    driver: local
  postgres-data:
    driver: local
  redis-data:
    driver: local
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
  alertmanager-data:
    driver: local
  nginx-logs:
    driver: local

networks:
  bazis-network:
    driver: bridge
```

---

## Как использовать

### 1️⃣ Для локальной разработки

```bash
# Скопировать конфиг
cp docker-compose.yml ./базис-веб/

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Логи
docker-compose logs -f ollama
docker-compose logs -f bazis-web

# Остановить
docker-compose down
```

### 2️⃣ Для staging

```bash
# Скопировать конфиги
cp docker-compose.staging.yml ./базис-веб/docker-compose.yml

# Создать .env файл
cat > .env << EOF
GEMINI_API_KEY=your-key-here
POSTGRES_PASSWORD=secure-password
GRAFANA_PASSWORD=secure-password
EOF

# Запустить
docker-compose up -d

# Проверить Ollama
curl http://localhost:11434/api/tags

# Проверить приложение
open http://localhost:3002

# Проверить Grafana
open http://localhost:3001  # admin/admin
```

### 3️⃣ Для production

```bash
# Скопировать конфиги
cp docker-compose.prod.yml ./базис-веб/docker-compose.yml

# Создать .env файл с секретами
cat > .env << EOF
GEMINI_API_KEY=production-key
POSTGRES_PASSWORD=very-secure-password
GRAFANA_PASSWORD=very-secure-password
EOF
chmod 600 .env

# Собрать Docker образ
docker build -f Dockerfile.prod -t bazis-web:prod .

# Запустить production stack
docker-compose up -d

# Проверить логи
docker-compose logs -f bazis-web
docker-compose logs -f ollama

# Мониторинг
watch -n 1 docker-compose ps
```

---

## 📊 Мониторинг доступных сервисов

```
Development:
├─ Базис-Веб Frontend: http://localhost:3002
├─ Ollama API: http://localhost:11434
├─ PostgreSQL: localhost:5432
├─ Redis: localhost:6379
├─ Prometheus: http://localhost:9090
├─ Grafana: http://localhost:3001
└─ Jaeger: http://localhost:16686 (staging only)

Production:
├─ Базис-Веб Frontend: https://bazis.example.com
├─ Ollama API: http://ollama:11434 (internal)
├─ Prometheus: http://localhost:9090 (local only)
├─ Grafana: http://localhost:3001 (local only)
└─ Nginx Reverse Proxy: Port 80/443
```

---

## 🔧 Конфигурационные файлы

Нужно создать эти файлы:

### `./monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - "rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'ollama'
    static_configs:
      - targets: ['ollama:11434']

  - job_name: 'bazis-web'
    static_configs:
      - targets: ['bazis-web:5173']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
```

### `./nginx/nginx.conf` (базовая)

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    '"$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    upstream bazis-web {
        server bazis-web:5173;
    }

    upstream prometheus {
        server prometheus:9090;
    }

    upstream grafana {
        server grafana:3000;
    }

    upstream ollama {
        server ollama:11434;
    }

    server {
        listen 80;
        server_name _;

        client_max_body_size 100M;

        location / {
            proxy_pass http://bazis-web;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /metrics {
            proxy_pass http://prometheus;
            proxy_set_header Host $host;
        }

        location /grafana/ {
            proxy_pass http://grafana/;
            proxy_set_header Host $host;
        }

        location /ollama/ {
            proxy_pass http://ollama/;
            proxy_set_header Host $host;
        }
    }
}
```

---

## ✅ Checklist перед запуском

- [ ] Docker и Docker Compose установлены
- [ ] 30GB+ свободного места для моделей Ollama
- [ ] GPU (RTX 4090) или достаточно RAM если CPU mode
- [ ] `.env` файл создан с необходимыми переменными
- [ ] `./monitoring/` папка создана с конфигами
- [ ] `./nginx/` папка создана с конфигами
- [ ] Порты 3001-3002, 5432, 6379, 9090, 9093, 11434 свободны

---

**✅ ГОТОВО К ИСПОЛЬЗОВАНИЮ**

*Просто скопируйте нужный конфиг (dev/staging/prod) и запустите `docker-compose up -d`*
