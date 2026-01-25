# WEST-0105-2 КАРТОЧКА ДЕЙСТВИЙ (ЧТО ДЕЛАТЬ ПРЯМО СЕЙЧАС)

**Статус**: Готов к развёртыванию  
**Время**: 4-5 часов  
**Начало**: Сейчас  

---

## 🎯 ТРИ СТАДИИ РАЗВЁРТЫВАНИЯ

### Стадия 1: Prometheus Alert Rules (30 минут)

**Шаг 1.1**: Скопировать файл alert rules
```bash
cp prometheus/alerts/charter-alerts.yml /etc/prometheus/rules/
```

**Шаг 1.2**: Обновить prometheus.yml
```yaml
# Добавить в файл /etc/prometheus/prometheus.yml:
rule_files:
  - '/etc/prometheus/rules/charter-alerts.yml'
```

**Шаг 1.3**: Перезагрузить Prometheus
```bash
curl -X POST http://localhost:9090/-/reload
```

**Шаг 1.4**: Проверить alert rules загрузились
```bash
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules | length'
# Должно быть: 11
```

---

### Стадия 2: AlertManager Configuration (30 минут)

**Шаг 2.1**: Установить Slack webhook переменные
```bash
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
```

**Шаг 2.2**: Скопировать AlertManager config
```bash
cp alertmanager/config.yml /etc/alertmanager/
```

**Шаг 2.3**: Перезагрузить AlertManager
```bash
curl -X POST http://localhost:9093/-/reload
```

**Шаг 2.4**: Проверить AlertManager запущен
```bash
curl http://localhost:9093
# Должен вернуть status 200
```

**Шаг 2.5**: Отправить test alert в Slack
```bash
# Go to http://alertmanager:9093
# Click on "Send Alert" button manually
# Check #charter-monitoring for notification
```

---

### Стадия 3: Grafana Dashboards (2-3 часа)

#### Dashboard 1: Violations & Threats

**Шаг 3.1**: Создать новый dashboard в Grafana
- Name: `Violations & Threats`
- Folder: `Charter Observability`
- Refresh: 30s

**Шаг 3.2**: Добавить 7 панелей

**Панель 1**: Violations Timeline
```
Type: Graph
Query: sum by(severity) (rate(westworld_charter_violations_total[5m]))
Legend: {{ severity }}
Colors: CRITICAL=Red, SUSPENSION=Orange, WARNING=Yellow
```

**Панель 2**: Top 10 Nodes
```
Type: Heatmap
Query: topk(10, sum by(node_or_service, violation_type) (westworld_charter_violations_total))
```

**Панель 3**: Violation Types
```
Type: Pie Chart
Query: sum by(violation_type) (westworld_charter_violations_total)
```

**Панель 4**: Forbidden Metrics
```
Type: Heatmap
Query: rate(westworld_charter_forbidden_metric_attempts_total[1m])
```

**Панель 5**: Investigations
```
Type: Gauge
Query: sum by(severity) (westworld_charter_violations_under_investigation)
Thresholds: 0-2=Green, 3-5=Orange, 6+=Red
```

**Панель 6**: Emergency Status
```
Type: Stat
Query: westworld_charter_emergency_override_active_count
Thresholds: 0=Green ✓, 1=Orange ⚠️, 2+=Red 🚨
```

**Панель 7**: Recent Events Table
```
Type: Table
Query: topk(20, increase(westworld_charter_violations_total[1h]))
```

#### Dashboard 2: Enforcement Performance

**Шаг 3.3**: Создать второй dashboard
- Name: `Enforcement Performance`
- Folder: `Charter Observability`
- Refresh: 30s

**Шаг 3.4**: Добавить 7 панелей

**Панель 1**: Validation Latency SLA
```
Type: Graph
Query A (p50): histogram_quantile(0.50, rate(..._latency_ns_bucket[5m])) / 1000
Query B (p95): histogram_quantile(0.95, rate(..._latency_ns_bucket[5m])) / 1000
Query C (p99): histogram_quantile(0.99, rate(..._latency_ns_bucket[5m])) / 1000
Y-axis: Latency (µs)
Threshold: 10µs (SLA line)
```

**Панель 2**: Policy Load
```
Type: Graph (dual axis)
Left Y: rate(policy_load_duration_ms_count[1h]) = Reloads/hour
Right Y: histogram_quantile(0.99, policy_load_duration_ms) = Duration ms
```

**Панель 3**: Committee Notification Latency
```
Type: Gauge
Query: histogram_quantile(0.99, rate(committee_notification_latency_ms_bucket[5m]))
Unit: ms
Thresholds: 0-500=Green, 500-1000=Orange, 1000+=Red
```

**Панель 4**: E2E Response Time
```
Type: Graph
Query: histogram_quantile(0.99, rate(violation_report_latency_ms_bucket[5m]))
Threshold: 1000ms (SLA)
```

**Панель 5**: Data Revocation
```
Type: Stat
Query: rate(data_revocation_events_total[1h])
Unit: events/hour
```

**Панель 6**: Policy Freshness
```
Type: Stat
Query: (time() - policy_last_load_timestamp) / 3600
Unit: hours
Thresholds: 0-4=Green, 4-24=Orange, 24+=Red
```

**Панель 7**: Investigation Rate
```
Type: Stat
Query: rate(investigation_initiated_total[5m])
Unit: investigations/sec
```

---

## ✅ ПРОВЕРКА ПОСЛЕ РАЗВЁРТЫВАНИЯ

```bash
# 1. Проверить alert rules
curl http://prometheus:9090/api/v1/rules | jq '.data.groups | length'

# 2. Проверить metrics flowing
curl http://prometheus:9090/api/v1/query?query=westworld_charter_violations_total

# 3. Проверить AlertManager
curl http://alertmanager:9093

# 4. Проверить Grafana dashboards
# - http://grafana:3000/dashboards
# - Должны быть 2 dashboard: Violations & Threats, Enforcement Performance

# 5. Test end-to-end
curl -X POST http://charter-api:8000/test/violation \
  -H "Content-Type: application/json" \
  -d '{"severity": "CRITICAL", "type": "data_extraction", "node": "test"}'
# Wait 2 minutes
# Check Slack #charter-security for alert
```

---

## 🚀 ВРЕМЕННАЯ ШКАЛА

```
0-30 min:  Prometheus alert rules deployment
30-60 min: AlertManager configuration
60-180 min: Create Grafana dashboards (2 dashboards)
180-240 min: Testing and verification
─────────────────────────────────
TOTAL: 4-5 часов до готовности WEST-0105-2 ✅
```

---

## 📞 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Alert rules не загружаются
```bash
# 1. Проверить синтаксис
yamllint prometheus/alerts/charter-alerts.yml

# 2. Проверить путь
ls -la /etc/prometheus/rules/charter-alerts.yml

# 3. Проверить logs
tail -f /var/log/prometheus/prometheus.log
```

### Grafana panels пусты ("No data")
```bash
# 1. Проверить datasource connection
# Go to: http://grafana:3000/datasources
# Click Prometheus-Charter → Test Data Source

# 2. Запустить query в Prometheus напрямую
curl 'http://prometheus:9090/api/v1/query?query=westworld_charter_violations_total'
```

### Slack notifications не приходят
```bash
# 1. Проверить webhook URL
echo $SLACK_WEBHOOK_URL

# 2. Test webhook
curl -X POST $SLACK_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text": "Test"}'

# 3. Проверить AlertManager logs
tail -f /var/log/alertmanager/alertmanager.log
```

---

## ✨ ВЫ ГОТОВЫ!

Всё необходимое подготовлено:
- ✅ Alert rules configured
- ✅ AlertManager setup
- ✅ Documentation complete
- ✅ Deployment scripts ready

**СЛЕДУЮЩИЙ ШАГ**: Начните со Стадии 1 (Prometheus alert rules)

**ВРЕМЯ**: 4-5 часов до живой observability ✅

---

*WEST-0105-2 Action Card | 2026-01-11 | Ready to Execute*
