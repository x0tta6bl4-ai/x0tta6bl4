# Failure Injection Execution Plan

**Дата:** 2026-01-07  
**Версия:** 3.4.0-fixed2  
**Статус:** ⏳ Ready after stability test

---

## Когда запускать

**После завершения stability test:**
- Дата: Jan 8, 2026, ~00:58 CET
- Условие: Stability test успешно завершен
- Проверка: Все критерии успеха выполнены

---

## Порядок выполнения

### Подготовка (5 минут)

1. Проверить, что stability test завершен
2. Проверить финальное состояние pods (5/5 Running)
3. Проверить, что нет критичных ошибок
4. Создать backup текущего состояния (опционально)

**Команды:**
```bash
# Проверить статус
kubectl get pods -n x0tta6bl4-staging

# Проверить health
curl -s http://localhost:8080/health | jq .status

# Проверить метрики
curl -s http://localhost:8080/metrics | grep -E "(gnn_recall|mesh_mape_k_)"
```

---

### Test 1: Pod Failure (10-15 минут)

**Цель:** Проверить MTTR < 3min, MTTD < 20s

**Шаги:**
1. Запустить скрипт: `./failure_injection_test.sh`
2. Или вручную:
   ```bash
   # Выбрать pod для удаления
   POD_TO_KILL=$(kubectl get pods -n x0tta6bl4-staging -o jsonpath='{.items[0].metadata.name}')
   
   # Записать время начала
   START_TIME=$(date +%s)
   
   # Удалить pod
   kubectl delete pod $POD_TO_KILL -n x0tta6bl4-staging
   
   # Мониторить восстановление
   watch -n 2 'kubectl get pods -n x0tta6bl4-staging'
   
   # Когда pod восстановился, записать время
   END_TIME=$(date +%s)
   MTTR=$((END_TIME - START_TIME))
   echo "MTTR: ${MTTR}s"
   ```

**Ожидаемые результаты:**
- MTTD: < 20 секунд
- MTTR: < 3 минуты
- Mesh network: Реконвергирует < 2.3 секунды
- MAPE-K: Обнаруживает проблему автоматически

**Метрики для проверки:**
```bash
# Проверить MAPE-K метрики
curl -s http://localhost:8080/metrics | grep mesh_mape_k_

# Проверить mesh status
curl -s http://localhost:8080/mesh/status | jq .

# Проверить MTTD
curl -s http://localhost:8080/metrics | grep mesh_mttd
```

---

### Test 2: High Load (5-10 минут)

**Цель:** Проверить поведение под высокой нагрузкой

**Шаги:**
```bash
# Запустить высокую нагрузку (1000 запросов)
for i in {1..1000}; do
  curl -s http://localhost:8080/health > /dev/null &
done
wait

# Проверить состояние после нагрузки
kubectl get pods -n x0tta6bl4-staging
curl -s http://localhost:8080/health | jq .
```

**Ожидаемые результаты:**
- Система справляется с нагрузкой
- Нет pod restarts
- Latency остается приемлемой
- MAPE-K адаптируется

---

### Test 3: Resource Exhaustion (10-15 минут)

**Цель:** Проверить graceful degradation

**Шаги:**
```bash
# Уменьшить resource limits
kubectl patch deployment x0tta6bl4-staging -n x0tta6bl4-staging \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"x0tta6bl4","resources":{"limits":{"cpu":"100m","memory":"256Mi"}}}]}}}}'

# Подождать применения изменений
sleep 30

# Проверить поведение
kubectl get pods -n x0tta6bl4-staging
kubectl top pods -n x0tta6bl4-staging 2>&1

# Восстановить limits
kubectl patch deployment x0tta6bl4-staging -n x0tta6bl4-staging \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"x0tta6bl4","resources":{"limits":{"cpu":"2000m","memory":"2Gi"}}}]}}}}'
```

**Ожидаемые результаты:**
- Система обнаруживает нехватку ресурсов
- MAPE-K принимает меры
- GraphSAGE идентифицирует проблему
- Система работает в degraded mode

---

## Документирование результатов

**Для каждого теста записать:**
- Время начала теста
- MTTD (если применимо)
- MTTR (если применимо)
- Действия MAPE-K
- Root cause от GraphSAGE
- Финальное состояние системы
- Проблемы (если есть)

**Файл:** `FAILURE_INJECTION_RESULTS_2026_01_08.md`

---

## Критерии успеха

**После всех тестов:**
- ✅ Все тесты пройдены
- ✅ MTTR < 3 минуты для всех сценариев
- ✅ MTTD < 20 секунд
- ✅ Mesh network реконвергирует < 2.3 секунды
- ✅ MAPE-K обнаруживает все проблемы
- ✅ GraphSAGE идентифицирует root cause
- ✅ Нет permanent failures
- ✅ Нет data loss

---

## Если что-то пошло не так

**Проблема:** Pod не восстанавливается
- Проверить deployment configuration
- Проверить resource limits
- Проверить health checks
- Проверить logs

**Проблема:** MTTR > 3 минуты
- Проверить MAPE-K configuration
- Проверить mesh network settings
- Проверить resource availability

**Проблема:** MAPE-K не обнаруживает проблему
- Проверить MAPE-K loop status
- Проверить thresholds
- Проверить metrics collection

---

**Время выполнения:** ~30-60 минут (все тесты)  
**Статус:** ⏳ Ready after stability test

