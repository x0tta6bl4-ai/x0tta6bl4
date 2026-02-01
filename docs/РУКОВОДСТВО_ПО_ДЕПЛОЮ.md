# Руководство по развертыванию Residential Proxy Infrastructure

## Содержание
1. [Быстрый старт](#быстрый-старт)
2. [Требования](#требования)
3. [Конфигурация](#конфигурация)
4. [Запуск](#запуск)
5. [Мониторинг](#мониторинг)
6. [Устранение неполадок](#устранение-неполадок)

## Быстрый старт

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Создание конфигурации
export PROXY_ENV=production
export PROXY_CONFIG_PATH=/etc/proxy/config.yaml
export PROXY_CONFIG_MASTER_KEY=$(openssl rand -hex 32)

# 3. Запуск
python -m src.network.proxy_orchestrator
```

## Требования

### Системные
- Python 3.10+
- RAM: 2GB минимум, 4GB рекомендуется
- Диск: 10GB для логов и метрик

### Python зависимости
```
aiohttp>=3.8.0
aiohttp-cors>=0.7.0
PyYAML>=6.0
cryptography>=40.0.0
PyJWT>=2.6.0
```

## Конфигурация

### Базовая конфигурация (config.yaml)

```yaml
environment: production
version: "1.0.0"

providers:
  - name: oxylabs
    enabled: true
    host_template: pr.oxylabs.io
    port: 7777
    username: "${OXYLABS_USERNAME}"
    password: "${OXYLABS_PASSWORD}"
    regions:
      - us
      - uk
      - de
    priority: 100
    max_failures: 3
    health_check_interval: 60
    rate_limit_per_minute: 100

selection:
  strategy: weighted_score
  latency_weight: 0.3
  success_weight: 0.4
  stability_weight: 0.2
  geographic_weight: 0.1
  enable_predictive: true

health_check:
  enabled: true
  interval_seconds: 60
  timeout_seconds: 10
  max_retries: 3
  check_urls:
    - https://www.google.com
    - https://www.cloudflare.com

metrics:
  enabled: true
  retention_hours: 24
  prometheus_enabled: true
  prometheus_port: 9090
  alert_thresholds:
    failure_rate: 0.1
    p95_latency_ms: 2000

security:
  api_key_required: true
  rate_limit_enabled: true
  rate_limit_requests_per_minute: 100
  jwt_secret: "${JWT_SECRET}"
  tls_enabled: true
  tls_cert_path: /etc/proxy/cert.pem
  tls_key_path: /etc/proxy/key.pem

control_plane:
  host: 0.0.0.0
  port: 8081
  workers: 4

xray:
  config_path: /usr/local/etc/xray/config.json
  reload_command: "systemctl reload xray"

logging:
  level: INFO
  format: json
```

### Переменные окружения

```bash
# Обязательные
export PROXY_ENV=production
export PROXY_CONFIG_MASTER_KEY="your-secure-master-key"

# API Keys (формат: ключ:роль)
export PROXY_API_KEY_ADMIN="pk_xxx:ADMIN"
export PROXY_API_KEY_OPERATOR="pk_yyy:OPERATOR"
export PROXY_API_KEY_VIEWER="pk_zzz:VIEWER"

# Провайдеры
export OXYLABS_USERNAME="your-username"
export OXYLABS_PASSWORD="your-password"

# JWT
export PROXY_JWT_SECRET="your-jwt-secret-min-32-chars"
```

## Запуск

### Systemd сервис

Создайте файл `/etc/systemd/system/proxy-orchestrator.service`:

```ini
[Unit]
Description=Residential Proxy Orchestrator
After=network.target

[Service]
Type=simple
User=proxy
Group=proxy
WorkingDirectory=/opt/proxy
Environment=PROXY_ENV=production
Environment=PROXY_CONFIG_PATH=/etc/proxy/config.yaml
EnvironmentFile=/etc/proxy/environment
ExecStart=/opt/proxy/venv/bin/python -m src.network.proxy_orchestrator
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl daemon-reload
sudo systemctl enable proxy-orchestrator
sudo systemctl start proxy-orchestrator
```

### Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/

ENV PROXY_ENV=production
ENV PYTHONPATH=/app

EXPOSE 8081 9090

CMD ["python", "-m", "src.network.proxy_orchestrator"]
```

```bash
docker build -t proxy-orchestrator .
docker run -d \
  -p 8081:8081 \
  -p 9090:9090 \
  -v /etc/proxy:/etc/proxy:ro \
  --env-file /etc/proxy/environment \
  proxy-orchestrator
```

## Мониторинг

### Prometheus метрики

Доступны на `http://localhost:9090/metrics`:

```
# Запросы
proxy_requests_total{proxy_id="oxylabs-us"}
proxy_requests_success{proxy_id="oxylabs-us"}
proxy_requests_failed{proxy_id="oxylabs-us",error_type="timeout"}

# Задержка
proxy_latency_ms{proxy_id="oxylabs-us"}

# Здоровье
proxy_health_check{proxy_id="oxylabs-us"}
```

### Health Check

```bash
curl http://localhost:8081/health
```

Ответ:
```json
{
  "status": "healthy",
  "proxies": {
    "total": 5,
    "healthy": 4,
    "unhealthy": 1
  },
  "timestamp": "2026-01-30T08:30:00Z"
}
```

### Grafana Dashboard

Импортируйте dashboard ID: `proxy-infrastructure-001`

Основные панели:
- Success Rate by Proxy
- P95 Latency
- Active Connections
- Error Rate
- Geographic Distribution

## Устранение неполадок

### Проблема: Нет здоровых прокси

**Симптомы:**
- `/health` показывает 0 healthy прокси
- Все запросы возвращают 503

**Решение:**
```bash
# Проверить конфигурацию провайдеров
python -c "
from src.network.proxy_config_manager import ProxyConfigManager
mgr = ProxyConfigManager()
import asyncio
asyncio.run(mgr.load())
print([p.to_dict() for p in mgr.config.providers])
"

# Проверить сетевую доступность
curl -x http://username:password@proxy-host:port https://www.google.com
```

### Проблема: Высокая задержка

**Симптомы:**
- P95 latency > 2000ms
- Медленные ответы

**Решение:**
1. Проверить geographic routing:
```bash
curl "http://localhost:8081/proxies?region=us"
```

2. Увеличить вес географии:
```yaml
selection:
  geographic_weight: 0.3  # было 0.1
```

### Проблема: Rate limiting

**Симптомы:**
- 429 Too Many Requests
- X-RateLimit-Remaining: 0

**Решение:**
```bash
# Проверить текущие лимиты
curl http://localhost:8081/metrics | grep rate_limit

# Увеличить лимиты в конфиге
security:
  rate_limit_requests_per_minute: 200  # было 100
```

### Проблема: Ошибки аутентификации

**Симптомы:**
- 401 Unauthorized
- "Authentication required"

**Решение:**
```bash
# Проверить API ключ
curl -H "X-API-Key: your-key" http://localhost:8081/proxies

# Или использовать JWT
curl -H "Authorization: Bearer your-jwt" http://localhost:8081/proxies
```

### Логи

```bash
# Просмотр логов
sudo journalctl -u proxy-orchestrator -f

# JSON формат для анализа
sudo journalctl -u proxy-orchestrator -o json | jq
```

## API Endpoints

### Прокси
- `GET /proxies` - Список прокси
- `GET /proxies/{id}` - Информация о прокси
- `POST /proxies/{id}/health-check` - Ручная проверка
- `POST /proxies/pool` - Добавить пул

### Домены
- `GET /domains` - Список доменов
- `GET /domains/{domain}` - Репутация домена

### Запросы
- `POST /request` - Проксировать запрос

### Метрики
- `GET /metrics` - Prometheus формат
- `GET /metrics/json` - JSON формат

### Xray
- `POST /xray/sync` - Синхронизация конфигурации

## Безопасность

### Ротация ключей

```bash
# Создать новый API ключ
python -c "
from src.network.proxy_auth_middleware import APIKeyStore
store = APIKeyStore()
new_key = store.rotate_key('admin')
print(f'New key: {new_key}')
"
```

### Аудит

Все действия логируются:
```json
{
  "timestamp": "2026-01-30T08:30:00Z",
  "level": "INFO",
  "event": "proxy_selected",
  "proxy_id": "oxylabs-us",
  "domain": "example.com",
  "client_id": "apikey:admin"
}
```

## Поддержка

При возникновении проблем:
1. Проверьте логи: `journalctl -u proxy-orchestrator`
2. Проверьте конфигурацию: `python -m src.network.proxy_config_manager --validate`
3. Проверьте метрики: `curl http://localhost:8081/metrics/json`
4. Создайте issue с:
   - Версией ПО
   - Конфигурацией (без секретов)
   - Логами ошибок
   - Шагами воспроизведения
