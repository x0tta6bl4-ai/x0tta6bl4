# 🚀 Staging Deployment: Quick Start

**Время:** 15-30 минут  
**Сложность:** Средняя  
**Требования:** Docker, 4GB RAM, 20GB disk

---

## Быстрый старт (Local)

### 1. Клонировать и подготовить

```bash
cd /mnt/AC74CC2974CBF3DC
git checkout main
```

### 2. Запустить deployment

```bash
# Local deployment (Docker Compose)
./staging/deploy_staging.sh local

# Или для конкретного облака
./staging/deploy_staging.sh aws 50
./staging/deploy_staging.sh azure 50
./staging/deploy_staging.sh gcp 50

# Или все сразу
./staging/deploy_staging.sh all 50
```

### 3. Проверить здоровье

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Smoke tests
./staging/smoke_tests.sh
```

### 4. Открыть дашборды

- **Control Plane:** http://localhost:8080
- **Prometheus:** http://localhost:9091
- **Grafana:** http://localhost:3000 (admin/admin)

---

## Что дальше?

1. **Мониторинг:** Проверьте Grafana dashboards
2. **Метрики:** Соберите baseline за 24 часа
3. **Тестирование:** Запустите E2E тесты
4. **Документация:** Задокументируйте результаты

---

## Troubleshooting

### Проблема: Сервисы не стартуют

```bash
# Проверить логи
docker-compose -f staging/docker-compose.staging.yml logs

# Перезапустить
docker-compose -f staging/docker-compose.staging.yml restart
```

### Проблема: Health check fails

```bash
# Проверить порты
netstat -tulpn | grep -E "8080|9091|3000"

# Проверить контейнеры
docker ps -a
```

### Проблема: Rollback нужен

```bash
# Автоматический rollback
./staging/rollback.sh auto

# Ручной rollback
./staging/rollback.sh manual
```

---

## Поддержка

- **Telegram:** @x0tta6bl4_ops
- **Документация:** `staging/STAGING_DEPLOYMENT_PLAN.md`
- **Логи:** `docker-compose -f staging/docker-compose.staging.yml logs`

---

**Готово! Staging deployment запущен.** ✅

