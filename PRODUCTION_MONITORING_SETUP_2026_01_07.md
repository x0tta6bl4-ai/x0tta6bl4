# Production Monitoring & Alerting Setup
**Дата:** 2026-01-07  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ⏳ В процессе подготовки

---

## 📊 Overview

**Цель:** Настроить полный production monitoring и alerting stack для x0tta6bl4

**Компоненты:**
- Prometheus (метрики)
- Grafana (дашборды)
- Alertmanager (алертинг)
- Production monitoring (код)

---

## 🔧 Setup Steps

### 1. Prometheus Setup

**Файлы:**
- `monitoring/prometheus.yml` - конфигурация
- `monitoring/prometheus/alerts.yaml` - правила алертов
- `monitoring/prometheus-deployment.yaml` - Kubernetes deployment

**Команды:**
```bash
# Deploy Prometheus
kubectl apply -f monitoring/prometheus-deployment.yaml

# Apply alert rules
kubectl create configmap prometheus-alerts \
  --from-file=monitoring/prometheus/alerts.yaml \
  -n monitoring

# Verify
kubectl get pods -n monitoring
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

**Проверка:**
- Prometheus UI: http://localhost:9090
- Targets: http://localhost:9090/targets
- Alerts: http://localhost:9090/alerts

---

### 2. Grafana Setup

**Файлы:**
- `monitoring/grafana/dashboards/` - дашборды
- `monitoring/grafana/datasources/prometheus.yml` - datasource

**Команды:**
```bash
# Deploy Grafana
kubectl apply -f monitoring/grafana-deployment.yaml

# Import dashboards
./monitoring/import-grafana-dashboards.sh

# Verify
kubectl get pods -n monitoring
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

**Проверка:**
- Grafana UI: http://localhost:3000
- Default credentials: admin/admin (change on first login)
- Dashboards: http://localhost:3000/dashboards

**Available Dashboards:**
- `x0tta6bl4-overview.json` - Overview dashboard
- `x0tta6bl4-production-ready.json` - Production dashboard
- `x0tta6bl4-enhanced.json` - Enhanced metrics
- `x0tta6bl4-complete.json` - Complete dashboard

---

### 3. Alertmanager Setup

**Создать:** `monitoring/alertmanager-config.yaml`

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: '${SLACK_WEBHOOK_URL}'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#x0tta6bl4-alerts'
        title: 'x0tta6bl4 Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'critical-alerts'
    slack_configs:
      - channel: '#x0tta6bl4-critical'
        title: '🚨 CRITICAL: x0tta6bl4'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
    email_configs:
      - to: 'oncall@x0tta6bl4.com'
        from: 'alerts@x0tta6bl4.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@x0tta6bl4.com'
        auth_password: '${SMTP_PASSWORD}'

  - name: 'warning-alerts'
    slack_configs:
      - channel: '#x0tta6bl4-alerts'
        title: '⚠️ WARNING: x0tta6bl4'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
```

**Deploy:**
```bash
# Create Alertmanager config
kubectl create secret generic alertmanager-config \
  --from-file=alertmanager.yml=monitoring/alertmanager-config.yaml \
  -n monitoring

# Deploy Alertmanager (create deployment YAML)
kubectl apply -f monitoring/alertmanager-deployment.yaml
```

---

### 4. Production Monitoring Integration

**Код:** `src/monitoring/production_monitoring.py`

**Использование:**
```python
from src.monitoring.production_monitoring import ProductionMonitor, MonitoringConfig

# Initialize
monitor = ProductionMonitor()

# Collect metrics
metrics = monitor.collect_metrics()

# Get dashboard data
dashboard_data = monitor.get_dashboard_data()

# Check alerts
alerts = monitor.alerts
```

**Endpoints:**
- `/metrics` - Prometheus metrics
- `/api/v1/monitoring/dashboard` - Dashboard data
- `/api/v1/monitoring/alerts` - Current alerts

---

## 📊 Key Metrics

### Application Metrics

- `x0tta6bl4_requests_total` - Total requests
- `x0tta6bl4_request_duration_seconds` - Request latency
- `x0tta6bl4_errors_total` - Error count
- `x0tta6bl4_active_connections` - Active connections

### Mesh Network Metrics

- `mesh_mape_k_cycle_duration_seconds` - MAPE-K cycle time
- `mesh_mape_k_packet_drop_rate` - Packet drop rate
- `mesh_mape_k_route_discovery_success_rate` - Route discovery
- `mesh_mttd_seconds` - Mean Time To Detect
- `mesh_mttr_seconds` - Mean Time To Recover

### Security Metrics

- `x0tta6bl4_pqc_handshake_duration_seconds` - PQC handshake time
- `x0tta6bl4_pqc_handshake_failures_total` - PQC failures
- `x0tta6bl4_spiffe_certificates_expiring` - Certificate expiry

### AI/ML Metrics

- `gnn_recall_score` - GraphSAGE recall
- `gnn_anomaly_detection_accuracy` - Anomaly detection accuracy
- `causal_analysis_confidence` - Causal analysis confidence

### Resource Metrics

- `container_cpu_usage_seconds_total` - CPU usage
- `container_memory_usage_bytes` - Memory usage
- `container_network_receive_bytes_total` - Network receive
- `container_network_transmit_bytes_total` - Network transmit

---

## 🚨 Alert Rules

### Critical Alerts

1. **Health Check Failed**
   - Condition: `up{job="x0tta6bl4"} == 0` for 2m
   - Action: Page on-call, escalate

2. **PQC Handshake Failure**
   - Condition: `rate(x0tta6bl4_pqc_handshake_failures_total[5m]) > 0.1`
   - Action: Page on-call, security team

3. **Critical Dependency Missing**
   - Condition: `x0tta6bl4_dependencies_health{status="required",available="false"} == 1`
   - Action: Page on-call

### Warning Alerts

1. **High Error Rate**
   - Condition: `rate(x0tta6bl4_errors_total[5m]) > 10`
   - Action: Notify team

2. **High Latency**
   - Condition: `histogram_quantile(0.95, rate(x0tta6bl4_request_duration_seconds_bucket[5m])) > 1`
   - Action: Notify team

3. **High CPU/Memory Usage**
   - Condition: CPU > 80% or Memory > 90% for 10m
   - Action: Notify team

4. **Frequent Pod Restarts**
   - Condition: `rate(kube_pod_container_status_restarts_total[15m]) > 0`
   - Action: Notify team

---

## 📈 Dashboard Configuration

### Overview Dashboard

**Panels:**
- Request rate (requests/sec)
- Error rate (%)
- Latency (p50, p95, p99)
- Active connections
- CPU/Memory usage
- Pod status

### Production Dashboard

**Panels:**
- All Overview panels
- Mesh network topology
- MAPE-K cycle metrics
- Security metrics (PQC, SPIFFE)
- AI/ML metrics (GraphSAGE, Causal Analysis)
- Resource utilization
- Alert history

---

## ✅ Verification Checklist

### Prometheus
- [ ] Prometheus deployed and running
- [ ] Targets are UP
- [ ] Alert rules loaded
- [ ] Metrics being scraped

### Grafana
- [ ] Grafana deployed and running
- [ ] Prometheus datasource configured
- [ ] Dashboards imported
- [ ] Dashboards showing data

### Alertmanager
- [ ] Alertmanager deployed
- [ ] Config loaded
- [ ] Notification channels configured
- [ ] Test alert sent successfully

### Application
- [ ] `/metrics` endpoint working
- [ ] Metrics being exported
- [ ] ProductionMonitor initialized
- [ ] Alerts being generated

---

## 🔧 Troubleshooting

### Prometheus not scraping

**Проблема:** Targets showing as DOWN

**Решение:**
```bash
# Check service endpoints
kubectl get endpoints -n x0tta6bl4-staging

# Check service
kubectl get svc -n x0tta6bl4-staging

# Check pod labels
kubectl get pods -n x0tta6bl4-staging --show-labels
```

### Grafana no data

**Проблема:** Dashboards showing "No data"

**Решение:**
1. Check Prometheus datasource connection
2. Verify metric names match queries
3. Check time range
4. Verify metrics are being exported

### Alerts not firing

**Проблема:** Alerts configured but not firing

**Решение:**
1. Check alert rule syntax
2. Verify metric names exist
3. Check threshold values
4. Verify Alertmanager is connected to Prometheus

---

## 📝 Next Steps

1. Deploy Prometheus in production cluster
2. Deploy Grafana with dashboards
3. Configure Alertmanager with notification channels
4. Set up on-call rotation
5. Test alerting end-to-end
6. Document runbooks for common alerts

---

**Статус:** ⏳ В процессе подготовки  
**Следующий шаг:** Deploy monitoring stack в production cluster

