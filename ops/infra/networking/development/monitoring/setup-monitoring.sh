#!/bin/bash

# Скрипт настройки системы мониторинга для проекта x0tta6bl4
# Версия: 1.0.0
# Дата: Октябрь 2025

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="development"
GRAFANA_ADMIN_PASSWORD="x0tta6bl4-dev"
PROMETHEUS_RETENTION="30d"
GRAFANA_VERSION="10.2.0"

# Функции логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."

    # Проверка kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl не установлен."
        exit 1
    fi

    # Проверка helm
    if ! command -v helm &> /dev/null; then
        log_error "Helm не установлен."
        exit 1
    fi

    # Проверка кластера
    if ! kubectl cluster-info &>/dev/null; then
        log_error "Kubernetes кластер недоступен."
        exit 1
    fi

    log_success "Все зависимости проверены"
}

# Создание namespace для мониторинга
create_monitoring_namespace() {
    log_info "Создание namespace для мониторинга..."

    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

    # Создание service account для мониторинга
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: monitoring-service-account
  namespace: $NAMESPACE
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-cluster-role
rules:
- apiGroups: [""]
  resources: ["nodes", "nodes/proxy", "nodes/metrics", "services", "endpoints", "pods", "ingresses"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["extensions"]
  resources: ["ingresses"]
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["/metrics", "/metrics/cadvisor"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: monitoring-cluster-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: monitoring-cluster-role
subjects:
- kind: ServiceAccount
  name: monitoring-service-account
  namespace: $NAMESPACE
EOF

    log_success "Namespace мониторинга создан"
}

# Установка Prometheus и Grafana
install_prometheus_grafana() {
    log_info "Установка Prometheus и Grafana..."

    # Добавление репозиториев Helm
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update

    # Установка kube-prometheus-stack
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace $NAMESPACE \
        --create-namespace \
        --set prometheus.service.type=NodePort \
        --set grafana.service.type=NodePort \
        --set prometheus-node-exporter.hostRootFsMount.enabled=false \
        --set grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD" \
        --set prometheus.retention="$PROMETHEUS_RETENTION" \
        --set grafana.persistence.enabled=true \
        --set grafana.persistence.size=10Gi \
        --set prometheus.persistence.enabled=true \
        --set prometheus.persistence.size=50Gi

    log_success "Prometheus и Grafana установлены"
}

# Установка дополнительных инструментов мониторинга
install_additional_monitoring() {
    log_info "Установка дополнительных инструментов мониторинга..."

    # Установка Jaeger для трассировки
    helm install jaeger jaegertracing/jaeger \
        --namespace $NAMESPACE \
        --set allInOne.enabled=true \
        --set storage.type=memory \
        --set service.type=NodePort

    # Установка Loki для логирования
    helm install loki grafana/loki-stack \
        --namespace $NAMESPACE \
        --set loki.persistence.enabled=true \
        --set loki.persistence.size=10Gi \
        --set promtail.enabled=true

    log_success "Дополнительные инструменты мониторинга установлены"
}

# Настройка мониторинга приложения
setup_application_monitoring() {
    log_info "Настройка мониторинга приложения..."

    # Создание ServiceMonitor для приложения
    kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: x0tta6bl4-servicemonitor
  namespace: $NAMESPACE
  labels:
    app: x0tta6bl4
spec:
  selector:
    matchLabels:
      app: x0tta6bl4
  endpoints:
  - port: http-metrics
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
---
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: x0tta6bl4-alert-rules
  namespace: $NAMESPACE
  labels:
    app: x0tta6bl4
spec:
  groups:
  - name: x0tta6bl4-alerts
    rules:
    - alert: X0tta6bl4Down
      expr: up{job="x0tta6bl4"} == 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "x0tta6bl4 application is down"
        description: "x0tta6bl4 has been down for more than 5 minutes."
    - alert: HighErrorRate
      expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.1
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected"
        description: "Error rate is above 10% for more than 10 minutes."
    - alert: HighLatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "High latency detected"
        description: "95th percentile latency is above 1 second for more than 10 minutes."
EOF

    log_success "Мониторинг приложения настроен"
}

# Настройка кастомных дашбордов Grafana
setup_custom_dashboards() {
    log_info "Настройка кастомных дашбордов Grafana..."

    # Создание ConfigMap с дашбордом для x0tta6bl4
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: x0tta6bl4-grafana-dashboard
  namespace: $NAMESPACE
  labels:
    grafana_dashboard: "1"
data:
  x0tta6bl4-dashboard.json: |
    {
      "dashboard": {
        "id": null,
        "title": "x0tta6bl4 Application Dashboard",
        "tags": ["x0tta6bl4", "application"],
        "timezone": "browser",
        "panels": [
          {
            "id": 1,
            "title": "Application Status",
            "type": "stat",
            "targets": [
              {
                "expr": "up{job=\"x0tta6bl4\"}",
                "refId": "A"
              }
            ],
            "fieldConfig": {
              "defaults": {
                "thresholds": {
                  "steps": [
                    {"color": "red", "value": 0},
                    {"color": "green", "value": 1}
                  ]
                }
              }
            }
          },
          {
            "id": 2,
            "title": "Request Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(http_requests_total[5m])",
                "refId": "A",
                "legendFormat": "{{method}} {{status}}"
              }
            ],
            "yAxes": [
              {"label": "Requests/sec"},
              {"label": "Requests/sec"}
            ]
          },
          {
            "id": 3,
            "title": "Error Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])",
                "refId": "A"
              }
            ],
            "yAxes": [
              {"label": "Error Rate", "format": "percentunit"},
              {"label": "Error Rate"}
            ]
          },
          {
            "id": 4,
            "title": "Latency",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
                "refId": "A",
                "legendFormat": "95th percentile"
              },
              {
                "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
                "refId": "B",
                "legendFormat": "50th percentile"
              }
            ],
            "yAxes": [
              {"label": "Latency", "format": "seconds"},
              {"label": "Latency"}
            ]
          }
        ],
        "time": {
          "from": "now-1h",
          "to": "now"
        },
        "refresh": "30s"
      }
    }
EOF

    log_success "Кастомные дашборды настроены"
}

# Настройка алертинга
setup_alerting() {
    log_info "Настройка алертинга..."

    # Создание AlertManager конфигурации
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: $NAMESPACE
data:
  config.yml: |
    global:
      smtp_smarthost: 'smtp.example.com:587'
      smtp_from: 'alerts@x0tta6bl4.com'
      smtp_auth_username: 'alerts@x0tta6bl4.com'
      smtp_auth_password: 'your-password'

    route:
      group_by: ['alertname']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 1h
      receiver: 'email'

    receivers:
    - name: 'email'
      email_configs:
      - to: 'devops@x0tta6bl4.com'
        subject: '[ALERT] x0tta6bl4 - {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Severity: {{ .Labels.severity }}
          Runbook: {{ .Annotations.runbook }}
          {{ end }}
EOF

    # Обновление AlertManager конфигурации
    kubectl patch deployment prometheus-kube-prometheus-operator \
        -n $NAMESPACE \
        --type='json' \
        -p='[{"op": "add", "path": "/spec/template/spec/volumes", "value": [{"name": "alertmanager-config", "configMap": {"name": "alertmanager-config"}}]}]'

    log_success "Алертинг настроен"
}

# Настройка логирования
setup_logging() {
    log_info "Настройка централизованного логирования..."

    # Создание Fluent Bit для сбора логов
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: $NAMESPACE
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off

    [INPUT]
        Name              tail
        Path              /var/log/containers/*x0tta6bl4*.log
        Parser            docker
        Tag               x0tta6bl4.*
        Refresh_Interval  5

    [INPUT]
        Name              tail
        Path              /var/log/containers/*nginx*.log
        Parser            nginx
        Tag               nginx.*
        Refresh_Interval  5

    [OUTPUT]
        Name  loki
        Match *
        Host  loki.$NAMESPACE.svc.cluster.local
        Port  3100
        Labels job=x0tta6bl4,env=development

    [OUTPUT]
        Name  stdout
        Match *
        Format json_lines
EOF

    # Создание DaemonSet для Fluent Bit
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
  namespace: $NAMESPACE
spec:
  selector:
    matchLabels:
      name: fluent-bit
  template:
    metadata:
      labels:
        name: fluent-bit
    spec:
      containers:
      - name: fluent-bit
        image: fluent/fluent-bit:2.2.0
        volumeMounts:
        - name: varlogcontainers
          mountPath: /var/log/containers
          readOnly: true
        - name: fluent-bit-config
          mountPath: /fluent-bit/etc/
          readOnly: true
      volumes:
      - name: varlogcontainers
        hostPath:
          path: /var/log/containers
      - name: fluent-bit-config
        configMap:
          name: fluent-bit-config
EOF

    log_success "Централизованное логирование настроено"
}

# Создание скрипта проверки мониторинга
create_monitoring_check_script() {
    log_info "Создание скрипта проверки мониторинга..."

    cat > ci-cd/scripts/check-monitoring.sh << 'EOF'
#!/bin/bash
set -euo pipefail

NAMESPACE="${1:-development}"

echo "🔍 Checking monitoring setup in namespace: $NAMESPACE"

# Проверка Prometheus
echo "📊 Checking Prometheus..."
if kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=prometheus | grep -q "Running"; then
    echo "✅ Prometheus is running"
else
    echo "❌ Prometheus is not running"
    exit 1
fi

# Проверка Grafana
echo "📈 Checking Grafana..."
if kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=grafana | grep -q "Running"; then
    echo "✅ Grafana is running"
else
    echo "❌ Grafana is not running"
    exit 1
fi

# Проверка Loki
echo "📝 Checking Loki..."
if kubectl get pods -n $NAMESPACE -l app=loki | grep -q "Running"; then
    echo "✅ Loki is running"
else
    echo "❌ Loki is not running"
    exit 1
fi

# Проверка Jaeger
echo "🔍 Checking Jaeger..."
if kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=jaeger | grep -q "Running"; then
    echo "✅ Jaeger is running"
else
    echo "❌ Jaeger is not running"
    exit 1
fi

# Проверка метрик приложения
echo "📊 Checking application metrics..."
if kubectl get servicemonitor -n $NAMESPACE x0tta6bl4-servicemonitor &>/dev/null; then
    echo "✅ ServiceMonitor is configured"
else
    echo "❌ ServiceMonitor is not configured"
    exit 1
fi

# Проверка алертов
echo "🚨 Checking alert rules..."
if kubectl get prometheusrule -n $NAMESPACE x0tta6bl4-alert-rules &>/dev/null; then
    echo "✅ Alert rules are configured"
else
    echo "❌ Alert rules are not configured"
    exit 1
fi

echo "🎉 All monitoring checks passed!"
EOF

    chmod +x ci-cd/scripts/check-monitoring.sh
    log_success "Скрипт проверки мониторинга создан"
}

# Вывод информации о доступе
show_access_info() {
    log_info "Информация о доступе к инструментам мониторинга:"
    echo

    # Получение портов сервисов
    PROMETHEUS_PORT=$(kubectl get svc prometheus-kube-prometheus-prometheus -n $NAMESPACE -o jsonpath='{.spec.ports[?(@.name=="http-web")].nodePort}' 2>/dev/null || echo "9090")
    GRAFANA_PORT=$(kubectl get svc prometheus-grafana -n $NAMESPACE -o jsonpath='{.spec.ports[?(@.name=="http-web")].nodePort}' 2>/dev/null || echo "3000")
    JAEGER_PORT=$(kubectl get svc jaeger-all-in-one -n $NAMESPACE -o jsonpath='{.spec.ports[?(@.name=="http")].nodePort}' 2>/dev/null || echo "16686")

    CLUSTER_IP=$(minikube ip 2>/dev/null || kubectl get nodes -o wide | awk 'NR==2{print $6}' | head -1)

    echo "🌐 Cluster IP: $CLUSTER_IP"
    echo
    echo "📊 Prometheus:"
    echo "   URL: http://$CLUSTER_IP:$PROMETHEUS_PORT"
    echo "   Targets: http://$CLUSTER_IP:$PROMETHEUS_PORT/targets"
    echo
    echo "📈 Grafana:"
    echo "   URL: http://$CLUSTER_IP:$GRAFANA_PORT"
    echo "   Username: admin"
    echo "   Password: $GRAFANA_ADMIN_PASSWORD"
    echo
    echo "🔍 Jaeger UI:"
    echo "   URL: http://$CLUSTER_IP:$JAEGER_PORT"
    echo
    echo "📝 Loki:"
    echo "   URL: http://loki.$NAMESPACE.svc.cluster.local:3100"
    echo
    echo "🔧 Команды для проверки:"
    echo "   kubectl get pods -n $NAMESPACE"
    echo "   kubectl get services -n $NAMESPACE"
    echo "   ./ci-cd/scripts/check-monitoring.sh $NAMESPACE"
    echo
    echo "📊 Команды для порта-форвардинга:"
    echo "   kubectl port-forward -n $NAMESPACE svc/prometheus-kube-prometheus-prometheus 9090:9090"
    echo "   kubectl port-forward -n $NAMESPACE svc/prometheus-grafana 3000:80"
    echo "   kubectl port-forward -n $NAMESPACE svc/jaeger-all-in-one 16686:16686"
}

# Основная функция
main() {
    log_info "Настройка системы мониторинга для проекта x0tta6bl4"
    echo "=================================================="

    check_dependencies
    create_monitoring_namespace
    install_prometheus_grafana
    install_additional_monitoring
    setup_application_monitoring
    setup_custom_dashboards
    setup_alerting
    setup_logging
    create_monitoring_check_script
    show_access_info

    log_success "Настройка мониторинга завершена успешно!"
    echo
    log_info "Мониторинг готов к использованию. Используйте команды выше для доступа к инструментам."
}

# Запуск основной функции
main "$@"