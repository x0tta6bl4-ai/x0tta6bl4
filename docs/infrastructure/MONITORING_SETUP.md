# 📊 Monitoring Setup Guide

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

---

## 📋 Overview

x0tta6bl4 использует комплексный стек мониторинга:
- **Prometheus** - Metrics collection
- **Grafana** - Visualization
- **OpenTelemetry** - Distributed tracing
- **Alertmanager** - Alerting

---

## 🚀 Prometheus Setup

### Installation (Prometheus Operator)

```bash
# Add Prometheus Operator Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### ServiceMonitor Integration

x0tta6bl4 автоматически создает ServiceMonitor при `monitoring.enabled=true`:

```yaml
# Already configured in helm/x0tta6bl4/templates/servicemonitor.yaml
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s
    scrapeTimeout: 10s
```

### Verify

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4

# Check Prometheus targets
# Access Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

---

## 📈 Grafana Setup

### Installation

Grafana обычно устанавливается вместе с Prometheus Operator.

### Access

```bash
# Get Grafana admin password
kubectl get secret -n monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 -d

# Port forward
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open http://localhost:3000
# Login: admin / <password>
```

### Dashboards

x0tta6bl4 предоставляет готовые dashboards:
- Mesh Network Metrics
- MAPE-K Cycle Metrics
- Federated Learning Metrics
- Security Metrics (PQC, SPIFFE)
- Dependency Health

**Импорт:** См. `docs/monitoring/grafana-dashboards/`

---

## 🔍 OpenTelemetry Setup

### Collector Deployment

```yaml
# otel-collector.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
        - name: otel-collector
          image: otel/opentelemetry-collector:latest
          args:
            - --config=/etc/otel-collector-config.yaml
          volumeMounts:
            - name: otel-collector-config
              mountPath: /etc/otel-collector-config.yaml
              subPath: otel-collector-config.yaml
      volumes:
        - name: otel-collector-config
          configMap:
            name: otel-collector-config
```

### Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

## 🚨 Alertmanager Setup

### Configuration

```yaml
# alertmanager-config.yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://alert-webhook:5001/alerts'
  
  - name: 'critical'
    telegram_configs:
      - bot_token: 'YOUR_BOT_TOKEN'
        chat_id: YOUR_CHAT_ID
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
  
  - name: 'warning'
    email_configs:
      - to: 'team@example.com'
        from: 'alerts@x0tta6bl4.io'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@x0tta6bl4.io'
        auth_password: 'password'
```

### Alert Rules

x0tta6bl4 предоставляет готовые alert rules:
- PQC handshake failures
- SPIFFE certificate expiry
- MAPE-K cycle failures
- Dependency health issues
- High latency
- Resource exhaustion

**Файлы:** `docs/monitoring/alert-rules/`

---

## 📊 Key Metrics

### Application Metrics

- `x0tta6bl4_requests_total` - Total requests
- `x0tta6bl4_request_duration_seconds` - Request duration
- `x0tta6bl4_errors_total` - Error count
- `x0tta6bl4_dependencies_health` - Dependency health status

### Mesh Metrics

- `x0tta6bl4_mesh_nodes_total` - Total mesh nodes
- `x0tta6bl4_mesh_beacons_total` - Total beacons
- `x0tta6bl4_mesh_latency_seconds` - Mesh latency

### MAPE-K Metrics

- `x0tta6bl4_mapek_cycles_total` - Total MAPE-K cycles
- `x0tta6bl4_mapek_recovery_actions_total` - Recovery actions
- `x0tta6bl4_mapek_mttd_seconds` - Mean Time To Detect

### Security Metrics

- `x0tta6bl4_pqc_handshakes_total` - PQC handshakes
- `x0tta6bl4_pqc_handshake_failures_total` - PQC failures
- `x0tta6bl4_spiffe_certificates_expiring` - Expiring certificates

---

## 🔧 Troubleshooting

### Metrics Not Appearing

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4 -o yaml

# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets

# Check metrics endpoint
kubectl port-forward -n x0tta6bl4 svc/x0tta6bl4 8000:8000
curl http://localhost:8000/metrics
```

### Traces Not Appearing

```bash
# Check OpenTelemetry collector
kubectl logs -n monitoring -l app=otel-collector

# Check Jaeger
kubectl port-forward -n monitoring svc/jaeger-query 16686:16686
# Open http://localhost:16686
```

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

