# Stability Test Plan (24+ hours)

**Дата:** 2026-01-07  
**Цель:** Проверить долгосрочную стабильность системы, выявить утечки памяти, проблемы с ресурсами

---

## Текущий статус

**Pods:** 5/5 (4 Ready, 1 starting)  
**Версия:** 3.4.0-fixed2  
**Окружение:** Staging (kind cluster)

---

## Тестовая конфигурация

**Параметры:**
- Duration: 24+ hours
- Pods: 5 replicas
- Load: Continuous light load (health checks every 5s)
- Monitoring: Metrics collection every 1 minute

---

## Метрики для мониторинга

### 1. Memory Usage

**Цель:** Выявить утечки памяти

**Метрики:**
- `process_resident_memory_bytes` - отслеживать тренд
- Pod memory usage (через kubectl top, если metrics-server доступен)

**Ожидаемое поведение:**
- Memory стабильна или медленно растет (не более 10% за 24 часа)
- Нет резких скачков памяти
- Нет OOM kills

**Проверка:**
```bash
# Каждый час проверять memory usage
kubectl top pods -n x0tta6bl4-staging
```

---

### 2. CPU Usage

**Цель:** Проверить стабильность CPU под постоянной нагрузкой

**Метрики:**
- CPU usage per pod
- CPU throttling (если доступно)

**Ожидаемое поведение:**
- CPU стабилен (не более 80% в нормальном режиме)
- Нет резких скачков
- Нет CPU throttling

---

### 3. Pod Restarts

**Цель:** Выявить нестабильность pods

**Метрики:**
- Restart count per pod
- CrashLoopBackOff events

**Ожидаемое поведение:**
- Restart count = 0 (или стабилен)
- Нет CrashLoopBackOff
- Все pods в состоянии Running

**Проверка:**
```bash
# Каждый час проверять restart count
kubectl get pods -n x0tta6bl4-staging
```

---

### 4. Error Rate

**Цель:** Выявить накопление ошибок со временем

**Метрики:**
- HTTP error rate (5xx responses)
- Application errors в логах
- Failed health checks

**Ожидаемое поведение:**
- Error rate < 1%
- Нет накопления ошибок
- Health checks всегда успешны

**Проверка:**
```bash
# Проверять health endpoint каждые 5 минут
curl -s http://localhost:8080/health | jq .status
```

---

### 5. GNN Recall Score

**Цель:** Проверить стабильность GNN модели

**Метрики:**
- `gnn_recall_score` - должен оставаться ~0.96
- GraphSAGE accuracy

**Ожидаемое поведение:**
- Recall score стабилен (0.96 ± 0.01)
- Нет деградации при изменении топологии
- Нет деградации при наполнении RAG pipeline

**Проверка:**
```bash
# Каждый час проверять GNN метрики
curl -s http://localhost:8080/metrics | grep gnn_recall_score
```

---

### 6. Mesh Network Stability

**Цель:** Проверить стабильность mesh networking

**Метрики:**
- `mesh_mape_k_packet_drop_rate` - должен оставаться низким
- `mesh_mape_k_route_discovery_success_rate`
- Mesh peers count

**Ожидаемое поведение:**
- Packet drop rate < 1%
- Route discovery success rate > 95%
- Peers count стабилен

---

### 7. Log Growth

**Цель:** Выявить проблемы с переполнением логов

**Метрики:**
- Log file size growth
- Log rotation

**Ожидаемое поведение:**
- Логи ротируются корректно
- Нет переполнения диска
- Размер логов стабилен

**Проверка:**
```bash
# Проверять размер логов
kubectl exec -n x0tta6bl4-staging <pod-name> -- du -sh /var/log
```

---

## Скрипт для автоматического мониторинга

```bash
#!/bin/bash
# stability_test_monitor.sh

DURATION=86400  # 24 hours in seconds
INTERVAL=300    # 5 minutes
LOG_FILE="stability_test_$(date +%Y%m%d_%H%M%S).log"

echo "Starting stability test monitoring at $(date)" | tee -a $LOG_FILE

for ((i=0; i<$DURATION; i+=$INTERVAL)); do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    
    echo "=== $TIMESTAMP ===" | tee -a $LOG_FILE
    
    # Check pods status
    echo "Pods status:" | tee -a $LOG_FILE
    kubectl get pods -n x0tta6bl4-staging | tee -a $LOG_FILE
    
    # Check health
    echo "Health check:" | tee -a $LOG_FILE
    curl -s http://localhost:8080/health | jq . | tee -a $LOG_FILE
    
    # Check metrics
    echo "GNN recall:" | tee -a $LOG_FILE
    curl -s http://localhost:8080/metrics | grep gnn_recall_score | tee -a $LOG_FILE
    
    # Check memory (if metrics-server available)
    echo "Resource usage:" | tee -a $LOG_FILE
    kubectl top pods -n x0tta6bl4-staging 2>&1 | tee -a $LOG_FILE
    
    echo "" | tee -a $LOG_FILE
    
    sleep $INTERVAL
done

echo "Stability test monitoring completed at $(date)" | tee -a $LOG_FILE
```

---

## Критерии успеха

**Через 24 часа:**
- ✅ Memory usage: рост < 10%
- ✅ CPU usage: стабилен, < 80%
- ✅ Pod restarts: 0 (или стабилен)
- ✅ Error rate: < 1%
- ✅ GNN recall: 0.96 ± 0.01
- ✅ Mesh network: стабилен
- ✅ Logs: нет переполнения
- ✅ Health checks: 100% success

---

## Если что-то пошло не так

**Проблема:** Memory leak
- Проверить логи на утечки
- Проверить Python garbage collection
- Проверить кэширование

**Проблема:** Pod restarts
- Проверить logs pods
- Проверить resource limits
- Проверить health checks

**Проблема:** GNN degradation
- Проверить RAG pipeline
- Проверить топологию mesh
- Проверить данные для обучения

---

**Время выполнения:** 24+ hours  
**Статус:** ⏳ Ready to start

