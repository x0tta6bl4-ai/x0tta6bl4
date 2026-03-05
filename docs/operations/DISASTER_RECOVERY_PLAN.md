# 🚨 Disaster Recovery Plan for x0tta6bl4

**Версия:** 1.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Обзор

Полный план восстановления после катастроф для x0tta6bl4. Охватывает все сценарии отказов и процедуры восстановления.

---

## 🎯 Цели Disaster Recovery

- **RTO (Recovery Time Objective):** < 1 час для критических сервисов
- **RPO (Recovery Point Objective):** < 15 минут (максимальная потеря данных)
- **Availability Target:** 99.9% (8.76 часов downtime в год)

---

## 📊 Классификация инцидентов

### SEV-1: Критический (Полный отказ системы)
- **RTO:** 15 минут
- **RPO:** 0 минут (zero data loss)
- **Примеры:** Полный отказ региона, потеря всех узлов

### SEV-2: Высокий (Частичный отказ)
- **RTO:** 1 час
- **RPO:** 5 минут
- **Примеры:** Отказ одного региона, потеря 50% узлов

### SEV-3: Средний (Деградация сервиса)
- **RTO:** 4 часа
- **RPO:** 15 минут
- **Примеры:** Высокая латентность, потеря 25% узлов

---

## 🔄 Сценарии восстановления

### Сценарий 1: Полный отказ региона (us-east-1)

**Симптомы:**
- Все узлы в регионе недоступны
- Нет ответа от API
- Метрики не поступают

**Процедура восстановления:**

1. **Обнаружение (0-5 минут)**
   ```bash
   # Проверить статус региона
   kubectl get nodes --context=us-east-1
   
   # Проверить health checks
   curl https://api-us-east.x0tta6bl4.com/health
   
   # Проверить мониторинг
   # Grafana должен показать все узлы down
   ```

2. **Активация failover (5-10 минут)**
   ```bash
   # Переключить DNS на backup регион
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z123456789 \
     --change-batch file://failover-to-eu-west.json
   
   # Проверить failover
   curl https://api.x0tta6bl4.com/health
   ```

3. **Восстановление сервисов (10-30 минут)**
   ```bash
   # Масштабировать backup регион
   kubectl scale deployment/x0tta6bl4 --replicas=10 --context=eu-west-1
   
   # Проверить статус
   kubectl get pods --context=eu-west-1
   ```

4. **Восстановление данных (30-60 минут)**
   ```bash
   # Восстановить из backup
   python scripts/backup_restore.py --restore \
     --backup-id=latest \
     --region=eu-west-1
   
   # Проверить целостность данных
   python scripts/validate_data_integrity.py
   ```

5. **Восстановление основного региона (после устранения проблемы)**
   ```bash
   # Развернуть в основном регионе
   kubectl apply -f k8s/production/us-east-1/ --context=us-east-1
   
   # Постепенное переключение трафика обратно
   # Canary deployment: 10% → 50% → 100%
   ```

**RTO:** 30-60 минут  
**RPO:** 0-15 минут (зависит от последнего backup)

---

### Сценарий 2: Потеря данных (Database corruption)

**Симптомы:**
- Ошибки чтения из базы данных
- Несоответствие данных между узлами
- CRDT sync failures

**Процедура восстановления:**

1. **Остановить запись (0-2 минуты)**
   ```bash
   # Перевести в read-only режим
   kubectl patch deployment/x0tta6bl4 \
     --patch '{"spec":{"template":{"spec":{"containers":[{"name":"app","env":[{"name":"READ_ONLY","value":"true"}]}]}}}}'
   ```

2. **Восстановить из backup (2-15 минут)**
   ```bash
   # Найти последний валидный backup
   python scripts/backup_restore.py --list-backups
   
   # Восстановить
   python scripts/backup_restore.py --restore \
     --backup-id=<backup-id> \
     --verify-integrity
   ```

3. **Проверить целостность (15-30 минут)**
   ```bash
   # Проверить CRDT sync
   curl http://localhost:8080/api/v1/crdt/status
   
   # Проверить данные
   python scripts/validate_data_integrity.py
   ```

4. **Восстановить запись (30-45 минут)**
   ```bash
   # Вернуть write режим
   kubectl patch deployment/x0tta6bl4 \
     --patch '{"spec":{"template":{"spec":{"containers":[{"name":"app","env":[{"name":"READ_ONLY","value":"false"}]}]}}}}'
   ```

**RTO:** 30-45 минут  
**RPO:** 0-15 минут (зависит от backup frequency)

---

### Сценарий 3: Security breach (Compromised nodes)

**Симптомы:**
- Неавторизованный доступ
- Anomalous network traffic
- SPIFFE authentication failures

**Процедура восстановления:**

1. **Изоляция (0-5 минут)**
   ```bash
   # Изолировать скомпрометированные узлы
   kubectl delete pod <compromised-pod>
   
   # Заблокировать сетевой доступ
   kubectl apply -f k8s/network-policies/isolate-node.yaml
   ```

2. **Ротация credentials (5-15 минут)**
   ```bash
   # Ротация SPIFFE SVIDs
   kubectl rollout restart daemonset/spire-agent
   
   # Ротация PQC keys
   curl -X POST http://localhost:8080/api/v1/security/pqc/rotate-keys
   ```

3. **Аудит и анализ (15-60 минут)**
   ```bash
   # Собрать логи
   kubectl logs <compromised-pod> > security-audit.log
   
   # Анализ инцидента
   python scripts/security_audit.py --incident-id=<id>
   ```

4. **Восстановление (60+ минут)**
   ```bash
   # Развернуть новые узлы
   kubectl scale deployment/x0tta6bl4 --replicas=5
   
   # Проверить безопасность
   python scripts/security_audit_checklist.py
   ```

**RTO:** 60+ минут  
**RPO:** N/A (security incident)

---

## 💾 Backup стратегия

### Ежедневные backups
- **Расписание:** 05:00 UTC ежедневно
- **Хранение:** 30 дней локально, 90 дней в backup регионе
- **Компоненты:**
  - Database state
  - CRDT state
  - Configuration files
  - SPIFFE trust bundles

### Еженедельные backups
- **Расписание:** Воскресенье 06:00 UTC
- **Хранение:** 90 дней локально, 365 дней в backup регионе
- **Компоненты:**
  - Полный snapshot системы
  - Все метрики и логи
  - Knowledge base

### Backup процедура
```bash
# Создать backup
python scripts/backup_restore.py --backup \
  --type=full \
  --destination=s3://x0tta6bl4-backups/

# Проверить backup
python scripts/backup_restore.py --verify \
  --backup-id=<backup-id>

# Список backups
python scripts/backup_restore.py --list-backups
```

---

## 🔄 Failover процедуры

### Multi-region failover

**Автоматический failover:**
- Health check каждые 30 секунд
- Автоматическое переключение при 3 последовательных failures
- DNS failover через Route53 health checks

**Ручной failover:**
```bash
# Переключить на backup регион
aws route53 change-resource-record-sets \
  --hosted-zone-id <zone-id> \
  --change-batch file://failover-to-backup.json

# Проверить статус
curl https://api.x0tta6bl4.com/health
```

### Mesh network failover

**Batman-adv автоматический failover:**
- Multi-path routing (до 3 путей)
- AODV fallback при отказе основного пути
- Автоматическое переключение маршрутов

**Ручное переключение:**
```bash
# Переключить маршрут
curl -X POST http://localhost:8080/api/v1/recovery/switch-route \
  -d '{"target_node": "node-id", "alternative_route": "backup-route"}'
```

---

## 📊 Мониторинг и алертинг

### Критические метрики для мониторинга

1. **System Health**
   - Node availability
   - Service uptime
   - Error rates

2. **Data Integrity**
   - CRDT sync status
   - Backup success rate
   - Data consistency checks

3. **Security**
   - SPIFFE authentication failures
   - PQC handshake failures
   - Zero Trust enforcement denials

### Alerting thresholds

- **SEV-1:** Node availability < 50%
- **SEV-2:** Error rate > 5%
- **SEV-3:** Latency p95 > 200ms

---

## 🧪 Тестирование DR плана

### Ежемесячные DR тесты

1. **Тест failover (1-й понедельник месяца)**
   - Симуляция отказа региона
   - Проверка автоматического failover
   - Время восстановления

2. **Тест backup восстановления (3-й понедельник месяца)**
   - Восстановление из backup
   - Проверка целостности данных
   - Время восстановления

3. **Тест security инцидента (по необходимости)**
   - Симуляция security breach
   - Проверка изоляции
   - Время восстановления

### DR Test Checklist

- [ ] Failover работает автоматически
- [ ] Backup восстановление успешно
- [ ] Данные целостны после восстановления
- [ ] RTO в пределах целевых значений
- [ ] RPO в пределах целевых значений
- [ ] Документация актуальна

### Reliability Drill Automation

Быстрый reliability drill для staging:

```bash
scripts/ops/run_reliability_drill.sh
```

Опциональные параметры:

```bash
COMPOSE_FILE=staging/docker-compose.quick.yml \
API_BASE_URL=http://localhost:8000 \
REPORT_DIR=/tmp \
scripts/ops/run_reliability_drill.sh
```

Критерии успеха:

- `docker compose ps` отрабатывает без ошибок.
- `/health` отвечает `200`.
- `/metrics` отвечает `200` и отдает payload.
- При деградации зависимостей API может вернуть `X-Degraded-Dependencies`.

---

## 📞 Контакты и эскалация

### On-Call Rotation
- **Primary:** DevOps Engineer
- **Secondary:** SRE Engineer
- **Escalation:** CTO

### Коммуникация
- **Slack:** #x0tta6bl4-incidents
- **PagerDuty:** Critical alerts
- **Email:** incidents@x0tta6bl4.com

---

## 📚 Связанные документы

- **Runbooks:** `docs/operations/RUNBOOKS_COMPLETE.md`
- **Emergency Procedures:** `docs/EMERGENCY_PROCEDURES.md`
- **On-Call Runbook:** `docs/team/ON_CALL_RUNBOOK.md`
- **Incident Response Plan:** `docs/team/INCIDENT_RESPONSE_PLAN.md`

---

**Последнее обновление:** 2026-03-04  
**Версия:** 1.0  
**Статус:** ✅ Production-ready
