# Redis Sentinel для x0tta6bl4

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Sentinel Cluster                    │
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │Sentinel │    │Sentinel │    │Sentinel │                │
│  │   #1    │    │   #2    │    │   #3    │                │
│  └────┬────┘    └────┬────┘    └────┬────┘                │
│       │              │              │                       │
│       └──────────────┼──────────────┘                       │
│                      │                                       │
│              ┌───────▼───────┐                              │
│              │  Redis Master │ ◄── Writes                  │
│              │   (Primary)   │                              │
│              └───────┬───────┘                              │
│                      │                                       │
│         ┌───────────┴───────────┐                          │
│         │                       │                           │
│  ┌──────▼──────┐        ┌──────▼──────┐                   │
│  │Redis Replica│        │Redis Replica│ ◄── Reads         │
│  │    #1       │        │    #2       │                   │
│  └─────────────┘        └─────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Установка

### 1. Создание секрета

```bash
# Генерация пароля
REDIS_PASSWORD=$(openssl rand -base64 32)

# Создание секрета
kubectl create secret generic redis-secret \
  --namespace x0tta6bl4 \
  --from-literal=redis-password="${REDIS_PASSWORD}"
```

### 2. Установка через Helm

```bash
# Добавление репозитория Bitnami
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Установка Redis с Sentinel
helm install redis bitnami/redis \
  -f values.yaml \
  -n x0tta6bl4 \
  --create-namespace
```

### 3. Проверка установки

```bash
# Проверка подов
kubectl get pods -n x0tta6bl4 -l app.kubernetes.io/name=redis

# Проверка Sentinel
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -a $REDIS_PASSWORD -p 26379 SENTINEL master mymaster

# Проверка репликации
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -a $REDIS_PASSWORD INFO replication
```

## Конфигурация приложения

### Environment Variables

```yaml
# В deployment.yaml
env:
  - name: REDIS_SENTINEL_HOSTS
    value: "redis-node-0.redis-headless:26379,redis-node-1.redis-headless:26379,redis-node-2.redis-headless:26379"
  - name: REDIS_SENTINEL_MASTER
    value: "mymaster"
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: redis-secret
        key: redis-password
```

### Python код

```python
import os
from src.core.cache import get_cache

# Sentinel автоматически используется если установлены переменные
cache = get_cache()

# Health check
status = await cache.health_check()
print(f"Redis mode: {status['mode']}")  # "sentinel"
print(f"Master: {status.get('master')}")
print(f"Replicas: {status.get('replicas')}")
```

## Тестирование Failover

### Ручной failover

```bash
# Инициировать failover через Sentinel
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -a $REDIS_PASSWORD -p 26379 SENTINEL failover mymaster
```

### Симуляция отказа мастера

```bash
# Удалить под мастера
kubectl delete pod redis-node-0 -n x0tta6bl4

# Наблюдать за failover (в другом терминале)
kubectl exec -it redis-node-1 -n x0tta6bl4 -- \
  redis-cli -a $REDIS_PASSWORD -p 26379 SENTINEL master mymaster
```

## Мониторинг

### Prometheus метрики

- `redis_up` - статус Redis
- `redis_sentinel_sentinels` - количество sentinel
- `redis_connected_slaves` - количество реплик
- `redis_memory_used_bytes` - использование памяти
- `redis_commands_processed_total` - обработанные команды

### Grafana Dashboard

ID: 11835 (Redis Dashboard for Prometheus)

## Troubleshooting

### Проверка Sentinel

```bash
# Информация о мастере
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -p 26379 SENTINEL master mymaster

# Информация о репликах
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -p 26379 SENTINEL slaves mymaster

# Информация о других Sentinel
kubectl exec -it redis-node-0 -n x0tta6bl4 -- \
  redis-cli -p 26379 SENTINEL sentinels mymaster
```

### Логи

```bash
# Логи Redis
kubectl logs redis-node-0 -n x0tta6bl4 -c redis

# Логи Sentinel
kubectl logs redis-node-0 -n x0tta6bl4 -c sentinel
```

## SLA и восстановление

| Метрика | Значение |
|---------|----------|
| Время обнаружения отказа | 5 секунд |
| Время failover | < 30 секунд |
| RPO (Recovery Point Objective) | 0 (синхронная репликация) |
| RTO (Recovery Time Objective) | < 1 минута |
