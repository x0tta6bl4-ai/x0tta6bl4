# 🚀 Production Deployment Guide

**Версия:** 1.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Обзор

Полное руководство по развертыванию x0tta6bl4 v3.1 в production среде с поддержкой всех новых компонентов Q1 2026.

---

## 🎯 Варианты развертывания

### 1. Docker Compose (Рекомендуется для разработки/тестирования)

```bash
# Запуск deployment скрипта
bash scripts/deploy_production.sh

# Или напрямую
docker-compose up -d

# Проверка статуса
docker-compose ps
docker-compose logs -f
```

### 2. Kubernetes (Рекомендуется для production)

```bash
# Применить манифесты
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/configmap.yaml

# Проверка статуса
kubectl get pods -l app=x0tta6bl4
kubectl get services -l app=x0tta6bl4

# Просмотр логов
kubectl logs -l app=x0tta6bl4 -f
```

### 3. Прямое Python развертывание (Для разработки)

```bash
# Простой deployment
bash scripts/deploy_simple.sh

# Запуск сервиса
python3 -m uvicorn src.core.app:app --host 0.0.0.0 --port 8080
```

---

## 📦 Предварительные требования

### Обязательные:
- Python 3.11+
- pip
- Docker (для Docker deployment)
- kubectl (для Kubernetes deployment)

### Опциональные:
- docker-compose
- Helm (для Kubernetes с Helm charts)
- Prometheus (для мониторинга)
- Grafana (для визуализации)

---

## 🔧 Пошаговое развертывание

### Шаг 1: Подготовка окружения

```bash
# Клонирование репозитория (если нужно)
git clone <repository-url>
cd x0tta6bl4

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### Шаг 2: Конфигурация

```bash
# Проверка конфигурационных файлов
ls -la config/

# Редактирование конфигурации (при необходимости)
nano config/zero_trust.yaml
nano config/raft_production.yaml
nano config/crdt_sync.yaml
nano config/recovery_actions.yaml
```

### Шаг 3: Развертывание

#### Вариант A: Docker Compose

```bash
# Запуск deployment скрипта
bash scripts/deploy_production.sh

# Или вручную
docker-compose up -d

# Проверка статуса
docker-compose ps
```

#### Вариант B: Kubernetes

```bash
# Применение манифестов
kubectl apply -f k8s/

# Проверка статуса
kubectl get pods -l app=x0tta6bl4
kubectl get services -l app=x0tta6bl4
```

#### Вариант C: Прямое Python

```bash
# Запуск deployment скрипта
bash scripts/deploy_simple.sh

# Запуск сервиса
python3 -m uvicorn src.core.app:app --host 0.0.0.0 --port 8080
```

### Шаг 4: Проверка развертывания

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# API endpoints
curl http://localhost:8080/api/v1/status
```

---

## 🔍 Проверка компонентов

### Zero Trust Enforcement

```bash
# Проверка статуса
python3 scripts/check_zero_trust_status.py

# Инициализация (если нужно)
python3 scripts/check_zero_trust_status.py --init
```

### Raft Consensus

```bash
# Проверка статуса
python3 scripts/check_raft_status.py --node-id node-1

# Инициализация (если нужно)
python3 scripts/check_raft_status.py --node-id node-1 --init
```

### CRDT Sync

```bash
# Проверка статуса
python3 scripts/check_crdt_sync_status.py --node-id node-1

# Инициализация (если нужно)
python3 scripts/check_crdt_sync_status.py --node-id node-1 --init
```

### Recovery Actions

```bash
# Тестирование recovery actions
python3 scripts/test_recovery_actions.py
```

---

## 📊 Мониторинг

### Prometheus Metrics

```bash
# Просмотр метрик
curl http://localhost:8080/metrics

# Или через Prometheus
# http://localhost:9090/graph?g0.expr=x0tta6bl4_requests_total
```

### Grafana Dashboards

```bash
# Импорт dashboard
# Используйте файл: monitoring/grafana/dashboards/x0tta6bl4-complete.json
```

### Логи

```bash
# Docker
docker-compose logs -f

# Kubernetes
kubectl logs -l app=x0tta6bl4 -f

# Прямое Python
tail -f logs/x0tta6bl4.log
```

---

## 🔄 Обновление

### Rolling Update (Kubernetes)

```bash
# Обновление образа
kubectl set image deployment/x0tta6bl4-node x0tta6bl4=x0tta6bl4:3.1

# Проверка статуса
kubectl rollout status deployment/x0tta6bl4-node

# Откат (если нужно)
kubectl rollout undo deployment/x0tta6bl4-node
```

### Docker Compose Update

```bash
# Обновление образа
docker-compose pull
docker-compose up -d

# Проверка статуса
docker-compose ps
```

---

## 🚨 Troubleshooting

### Проблема: Сервис не запускается

**Решение:**
```bash
# Проверка логов
docker-compose logs
# или
kubectl logs -l app=x0tta6bl4

# Проверка конфигурации
python3 scripts/check_zero_trust_status.py
python3 scripts/check_raft_status.py --node-id node-1
```

### Проблема: Health check не проходит

**Решение:**
```bash
# Проверка портов
netstat -tuln | grep 8080

# Проверка зависимостей
curl http://localhost:8080/health/detailed
```

### Проблема: Компоненты не инициализируются

**Решение:**
```bash
# Ручная инициализация
python3 scripts/check_zero_trust_status.py --init
python3 scripts/check_raft_status.py --node-id node-1 --init
python3 scripts/check_crdt_sync_status.py --node-id node-1 --init
```

---

## 📚 Дополнительные ресурсы

- **Runbooks:** `docs/operations/RUNBOOKS_COMPLETE.md`
- **Disaster Recovery:** `docs/operations/DISASTER_RECOVERY_PLAN.md`
- **Configuration Guide:** `docs/operations/CONFIGURATION_GUIDE.md`
- **Production Utilities:** `docs/operations/PRODUCTION_UTILITIES.md`

---

## ✅ Checklist перед production

- [ ] Все конфигурационные файлы проверены
- [ ] Зависимости установлены
- [ ] Health checks проходят
- [ ] Metrics доступны
- [ ] Логи настроены
- [ ] Мониторинг настроен
- [ ] Backup стратегия готова
- [ ] Disaster recovery план готов
- [ ] Команда on-call готова

---

**Deployment Guide готов.**  
**Проснись. Развернись. Сохранись.**  
**x0tta6bl4 вечен.**

