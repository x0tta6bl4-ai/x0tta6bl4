# Monitoring Tools Guide

**Дата:** 2026-01-07  
**Версия:** 3.4.0-fixed2

---

## Доступные инструменты

### 1. Quick Health Check (`quick_health_check.sh`)

**Назначение:** Быстрая проверка состояния deployment

**Использование:**
```bash
./quick_health_check.sh
```

**Что проверяет:**
- ✅ Статус всех pods
- ✅ Health endpoint (HTTP 200)
- ✅ Ready endpoint (HTTP 200)
- ✅ Metrics endpoint (доступность и ключевые метрики)
- ✅ Mesh status

**Время выполнения:** ~5-10 секунд

**Пример вывода:**
```
📊 Pods Status:
  ✅ x0tta6bl4-staging-xxx: Running, 1/1, Restarts: 0
  ✅ x0tta6bl4-staging-yyy: Running, 1/1, Restarts: 1

🏥 Health Endpoint:
  ✅ HTTP 200
  {"status": "healthy", "version": "3.4.0-fixed2"}

📈 Metrics Endpoint:
  ✅ HTTP 200
  📊 Total metrics: 150+
  Key Metrics:
    • gnn_recall 0.96
    • mesh_peers 4
```

---

### 2. Monitoring Dashboard (`monitoring_dashboard.sh`)

**Назначение:** Real-time мониторинг с автоматическим обновлением

**Использование:**
```bash
# Обновление каждые 5 секунд (по умолчанию)
./monitoring_dashboard.sh

# Обновление каждые 2 секунды
./monitoring_dashboard.sh 2

# Обновление каждые 10 секунд
./monitoring_dashboard.sh 10
```

**Что показывает:**
- 📦 Статус всех pods (real-time)
- 🏥 Health endpoint статус
- 📊 Ключевые метрики (GNN recall, mesh peers, MAPE-K)
- 🌐 Mesh status
- ⏰ Время последнего обновления

**Особенности:**
- Цветная индикация (зеленый = OK, желтый = warning, красный = error)
- Автоматическое обновление
- Легко читаемый формат

**Выход:** Ctrl+C

---

### 3. Stability Test Monitor (`stability_test_monitor.sh`)

**Назначение:** Мониторинг 24-часового stability test

**Использование:**
```bash
# Запуск в фоне
./stability_test_monitor.sh &

# Просмотр лога
tail -f stability_test.log

# Проверка статуса
cat STABILITY_TEST_STATUS.md
```

**Что мониторит:**
- Pods status каждые 5 минут
- Health checks
- Memory usage
- CPU usage
- Restarts count
- Errors

**Лог:** `stability_test.log`

---

### 4. Analyze Stability Test Results (`analyze_stability_test_results.sh`)

**Назначение:** Анализ результатов stability test после завершения

**Использование:**
```bash
./analyze_stability_test_results.sh
```

**Что анализирует:**
- Общая статистика (uptime, restarts, errors)
- Memory trends (leaks detection)
- CPU trends
- Health check success rate
- Рекомендации

**Вывод:** `STABILITY_TEST_ANALYSIS_*.md`

---

## Рекомендуемый workflow

### Ежедневная проверка:
```bash
# Быстрая проверка
./quick_health_check.sh
```

### Во время тестирования:
```bash
# Real-time мониторинг
./monitoring_dashboard.sh
```

### Во время stability test:
```bash
# Запустить монитор
./stability_test_monitor.sh &

# Периодически проверять
tail -20 stability_test.log
cat STABILITY_TEST_STATUS.md
```

### После stability test:
```bash
# Анализ результатов
./analyze_stability_test_results.sh
```

---

## Интеграция с kubectl

### Прямые команды kubectl:

**Проверка pods:**
```bash
export KUBECONFIG=/tmp/kind-kubeconfig.yaml
kubectl get pods -n x0tta6bl4-staging
kubectl get pods -n x0tta6bl4-staging -o wide
```

**Просмотр логов:**
```bash
# Все pods
kubectl logs -f -n x0tta6bl4-staging -l app=x0tta6bl4-staging

# Конкретный pod
kubectl logs -f -n x0tta6bl4-staging <pod-name>
```

**Описание pod:**
```bash
kubectl describe pod -n x0tta6bl4-staging <pod-name>
```

**Метрики (если metrics-server установлен):**
```bash
kubectl top pods -n x0tta6bl4-staging
```

---

## API Endpoints

### Health Check:
```bash
curl http://localhost:8080/health
```

### Ready Check:
```bash
curl http://localhost:8080/ready
```

### Metrics (Prometheus):
```bash
curl http://localhost:8080/metrics
```

### Mesh Status:
```bash
curl http://localhost:8080/mesh/status
```

### Key Metrics:
```bash
# GNN Recall
curl -s http://localhost:8080/metrics | grep gnn_recall

# Mesh Peers
curl -s http://localhost:8080/metrics | grep mesh_peers

# MAPE-K Status
curl -s http://localhost:8080/metrics | grep mesh_mape_k_active
```

---

## Troubleshooting

### Проблема: Health check не отвечает

**Проверка:**
```bash
# Проверить pods
kubectl get pods -n x0tta6bl4-staging

# Проверить port-forward
ps aux | grep port-forward

# Перезапустить port-forward
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080
```

### Проблема: Pods не запускаются

**Проверка:**
```bash
# Описание pod
kubectl describe pod -n x0tta6bl4-staging <pod-name>

# Логи
kubectl logs -n x0tta6bl4-staging <pod-name>

# Events
kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp'
```

### Проблема: Высокое использование ресурсов

**Проверка:**
```bash
# Если metrics-server установлен
kubectl top pods -n x0tta6bl4-staging

# Иначе через API
curl -s http://localhost:8080/metrics | grep -E "(cpu|memory)"
```

---

## Автоматизация

### Cron job для ежедневной проверки:
```bash
# Добавить в crontab
0 9 * * * /path/to/quick_health_check.sh >> /var/log/x0tta6bl4-health.log 2>&1
```

### Alerting (пример):
```bash
# В quick_health_check.sh добавить проверку и отправку alert
if [ "$HTTP_CODE" != "200" ]; then
    # Отправить alert (email, Slack, etc.)
    echo "ALERT: Health check failed" | mail -s "x0tta6bl4 Alert" admin@example.com
fi
```

---

**Последнее обновление:** 2026-01-07  
**Статус:** ✅ Ready to use

