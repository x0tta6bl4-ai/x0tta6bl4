# P0 Security Foundation: Исполняемый план (2-4 недели)

**Дата создания:** 2025-11-11  
**Статус:** 🟢 READY FOR EXECUTION  
**Цель:** Security 3.0 → 7.0/10 (Foundation ready)

> ⚠️ **ВАЖНО:** Этот план привязан к конкретным файлам в репо. Каждая задача имеет путь к коду и критерий верификации.

---

## 📋 Исполнительное резюме

**Текущее состояние:**
- SPIFFE/SPIRE: 3/10 (архитектура есть, реализация TODO)
- mTLS: 2/10 (заглушки)
- Security Scanning: 8/10 (работает, но не блокирует)

**Целевое состояние (4 недели):**
- SPIFFE/SPIRE: 7/10 (работает в staging)
- mTLS: 6/10 (базовая реализация)
- Security Scanning: 9/10 (блокирует на critical/high)

---

## 🎯 Неделя 1-2: SPIFFE/SPIRE Real Integration

### Задача 1.1: Заменить TODO в Workload API Client

**Файл:** `src/security/spiffe/workload/api_client.py`

**Текущее состояние:**
```python
# Строки 83-87: TODO
# Строки 116-119: TODO
# Строка 159: TODO: Actual certificate validation
```

**Что сделать:**
1. Реализовать gRPC call к SPIRE Agent Workload API
2. Парсить X509SVIDResponse protobuf
3. Реализовать certificate validation

**Критерий успеха:**
- ✅ `grep -r "TODO" src/security/spiffe/workload/api_client.py` = 0
- ✅ `pytest tests/unit/security/spiffe/test_workload_api_client.py -v` все тесты проходят
- ✅ Coverage `src/security/spiffe/workload/api_client.py` >80%

**Зависимости:**
- Установить `spiffe-python` или реализовать gRPC client вручную
- SPIRE Agent должен быть запущен (локально или в K8s)

**Оценка:** 2-3 дня

---

### Задача 1.2: Заменить TODO в SPIRE Agent Manager

**Файл:** `src/security/spiffe/agent/manager.py`

**Текущее состояние:**
```python
# Строки 85-100: TODO: Actual process launch
# Строки 111-114: TODO: Graceful shutdown
# Строка 155: TODO: Implement join token attestation
# Строка 177: TODO: Actual registration via SPIRE Agent API
```

**Что сделать:**
1. Реализовать запуск SPIRE Agent процесса
2. Реализовать graceful shutdown
3. Реализовать join token attestation
4. Реализовать workload registration

**Критерий успеха:**
- ✅ `grep -r "TODO" src/security/spiffe/agent/manager.py` = 0
- ✅ `pytest tests/unit/security/spiffe/test_spire_agent_manager.py -v` все тесты проходят
- ✅ Integration test: Agent запускается и аттестуется

**Зависимости:**
- SPIRE binary должен быть доступен в PATH или контейнере
- SPIRE Server должен быть доступен

**Оценка:** 3-4 дня

---

### Задача 1.3: Реализовать mTLS connection

**Файл:** `src/security/spiffe/controller/spiffe_controller.py`

**Текущее состояние:**
```python
# Строка 175: TODO: Implement actual mTLS connection
```

**Что сделать:**
1. Создать TLS context с SVID certificate
2. Настроить mutual TLS handshake
3. Валидировать peer SPIFFE ID

**Критерий успеха:**
- ✅ `grep "TODO" src/security/spiffe/controller/spiffe_controller.py` = 0
- ✅ `pytest tests/integration/test_mtls.py -v` e2e тесты проходят
- ✅ Все сервис-сервис вызовы используют TLS 1.3

**Зависимости:**
- Задача 1.1 (Workload API должен работать)
- SVID должен быть доступен

**Оценка:** 2-3 дня

---

### Задача 1.4: Развернуть SPIRE в Kubernetes (staging)

**Файлы:**
- `infra/security/spiffe-spire/helm-charts/spire-optimization/`
- `infra/security/spiffe-spire/helm-charts/spire-optimization/templates/spire-server-statefulset.yaml`
- `infra/security/spiffe-spire/helm-charts/spire-optimization/templates/spire-agent-daemonset.yaml`

**Что сделать:**
1. Проверить Helm charts
2. Развернуть SPIRE Server в staging namespace
3. Развернуть SPIRE Agent как DaemonSet
4. Настроить workload registration

**Критерий успеха:**
- ✅ `kubectl get pods -n spire` показывает running pods
- ✅ `kubectl logs -n spire -l app=spire-server` без ошибок
- ✅ `kubectl logs -n spire -l app=spire-agent` без ошибок
- ✅ Workload может получить SVID через Workload API

**Зависимости:**
- Kubernetes cluster (staging)
- Helm 3.x установлен

**Оценка:** 1-2 дня

---

## 🎯 Неделя 3-4: mTLS + Security Scanning Hardening

### Задача 2.1: Certificate Validation

**Файл:** `src/security/spiffe/workload/api_client.py:159`

**Текущее состояние:**
```python
# TODO: Actual certificate validation
```

**Что сделать:**
1. Валидация certificate chain против trust bundle
2. Проверка SPIFFE ID authorization policy
3. Валидация certificate expiry
4. Обработка federated trust domains

**Критерий успеха:**
- ✅ `grep "TODO" src/security/spiffe/workload/api_client.py:159` = 0
- ✅ Test `test_certificate_validation` проходит
- ✅ Expired certificates автоматически отклоняются

**Зависимости:**
- Trust bundle должен быть доступен
- Задача 1.1 (Workload API должен работать)

**Оценка:** 2 дня

---

### Задача 2.2: Security Scanning Hardening

**Файл:** `.github/workflows/security-scan.yml`

**Текущее состояние:**
```yaml
continue-on-error: true  # Не блокирует на ошибках
```

**Что сделать:**
1. Убрать `continue-on-error: true` для critical/high
2. Добавить fail-on для Bandit (critical, high)
3. Добавить Semgrep integration
4. Блокировать PR на critical/high findings

**Критерий успеха:**
- ✅ `.github/workflows/security-scan.yml` блокирует на critical/high
- ✅ PR с critical vulnerability не может быть merged
- ✅ `jq '.results[] | select(.severity=="CRITICAL" or .severity=="HIGH")' bandit-report.json | wc -l` = 0

**Зависимости:**
- Нет

**Оценка:** 1 день

---

### Задача 2.3: Добавить SPIFFE integration tests в CI

**Файл:** `.github/workflows/ci.yml`

**Текущее состояние:**
```yaml
- run: pytest tests/unit/ -v
# Нет integration tests для SPIFFE
```

**Что сделать:**
1. Создать `tests/integration/test_spire_integration.py`
2. Добавить job в CI для integration tests
3. Настроить test environment с SPIRE

**Критерий успеха:**
- ✅ `.github/workflows/ci.yml` включает `pytest tests/integration/test_spire_integration.py`
- ✅ CI job `spiffe-integration` проходит
- ✅ Coverage SPIFFE модулей >80%

**Зависимости:**
- Задачи 1.1-1.4 (SPIFFE должен работать)

**Оценка:** 2 дня

---

## 📊 Верификация прогресса

### Еженедельный чеклист

**Неделя 1-2:**
- [ ] `grep -r "TODO" src/security/spiffe/ | wc -l` < 5 (было ~15)
- [ ] `pytest tests/unit/security/spiffe/ -v` все тесты проходят
- [ ] `kubectl get pods -n spire` показывает running pods
- [ ] Coverage `src/security/spiffe/` >70%

**Неделя 3-4:**
- [ ] `grep -r "TODO" src/security/spiffe/ | wc -l` = 0
- [ ] `pytest tests/integration/test_spire_integration.py -v` проходит
- [ ] `.github/workflows/security-scan.yml` блокирует на critical/high
- [ ] Coverage `src/security/spiffe/` >80%

### Финальная верификация (4 недели)

**Машиночитаемые проверки:**
```bash
# 1. Нет TODO в SPIFFE коде
grep -r "TODO" src/security/spiffe/ | wc -l
# Ожидается: 0

# 2. Все тесты проходят
pytest tests/unit/security/spiffe/ tests/integration/test_spire_integration.py -v
# Ожидается: все passed

# 3. Coverage >80%
pytest --cov=src/security/spiffe --cov-report=term-missing
# Ожидается: coverage >80%

# 4. SPIRE развернут в staging
kubectl get pods -n spire
# Ожидается: spire-server-* и spire-agent-* running

# 5. Security scanning блокирует
# Проверить: .github/workflows/security-scan.yml не имеет continue-on-error для critical
grep -A 5 "continue-on-error" .github/workflows/security-scan.yml
# Ожидается: нет continue-on-error для critical/high

# 6. Нет critical/high vulnerabilities
# После запуска security-scan:
jq '.results[] | select(.severity=="CRITICAL" or .severity=="HIGH")' bandit-report.json | wc -l
# Ожидается: 0
```

---

## 🚨 Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| SPIRE Server недоступен | Medium | Использовать mock для unit tests, реальный SPIRE только для integration |
| gRPC сложность | Medium | Использовать `spiffe-python` библиотеку вместо raw gRPC |
| K8s deployment issues | Low | Протестировать Helm charts локально перед staging |
| Время на debugging | High | Заложить буфер 20% времени на каждую задачу |

---

## 📝 Следующие шаги после P0

После завершения P0 Security Foundation (4 недели):

1. **P1: Reliability Enhancement** (6-8 недель)
   - MAPE-K реальные действия
   - Mesh реальная интеграция

2. **P2: Observability** (4-6 недель)
   - OpenTelemetry tracing
   - Grafana dashboards

---

**Владелец:** Security Team  
**Последнее обновление:** 2025-11-11  
**Следующий review:** Еженедельно

---

*Этот план привязан к конкретным файлам и имеет машиночитаемые критерии верификации. Каждая задача может быть проверена автоматически.*

