#!/bin/bash
# Setup monitoring stack for staging environment

set -e

NAMESPACE="x0tta6bl4-staging"
MONITORING_NS="monitoring"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Staging Monitoring Setup                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Create monitoring namespace
echo "📦 Creating monitoring namespace..."
kubectl create namespace $MONITORING_NS --dry-run=client -o yaml | kubectl apply -f -

# Add Prometheus Helm repository
echo "📊 Adding Prometheus Helm repository..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Deploy Prometheus
echo "🚀 Deploying Prometheus..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    --namespace $MONITORING_NS \
    --create-namespace \
    --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
    --set prometheus.prometheusSpec.serviceMonitorSelector.matchLabels.release=prometheus \
    --set grafana.adminPassword=admin123 \
    --set grafana.service.type=ClusterIP \
    --set grafana.service.port=3000 \
    --wait \
    --timeout 10m

# Create ServiceMonitor for x0tta6bl4
echo "📈 Creating ServiceMonitor for x0tta6bl4..."
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: x0tta6bl4-staging-metrics
  namespace: $MONITORING_NS
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: x0tta6bl4
  namespaceSelector:
    matchNames:
    - $NAMESPACE
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
EOF

# Create Grafana dashboard for x0tta6bl4
echo "📊 Creating Grafana dashboard..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: x0tta6bl4-dashboard
  namespace: $MONITORING_NS
  labels:
    grafana_dashboard: "1"
data:
  x0tta6bl4.json: |
    {
      "dashboard": {
        "id": null,
        "title": "x0tta6bl4 Staging Dashboard",
        "tags": ["x0tta6bl4", "staging"],
        "timezone": "browser",
        "panels": [
          {
            "title": "Request Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(http_requests_total[5m])",
                "legendFormat": "{{method}} {{endpoint}}"
              }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
          },
          {
            "title": "Response Time",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
                "legendFormat": "95th percentile"
              },
              {
                "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
                "legendFormat": "50th percentile"
              }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
          },
          {
            "title": "Error Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])",
                "legendFormat": "Error Rate"
              }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
          },
          {
            "title": "Memory Usage",
            "type": "graph",
            "targets": [
              {
                "expr": "container_memory_usage_bytes / 1024 / 1024",
                "legendFormat": "{{pod}}"
              }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
          }
        ],
        "time": {"from": "now-1h", "to": "now"},
        "refresh": "30s"
      }
    }
EOF

# Port-forward commands for local access
echo ""
echo "🔗 Access URLs (run in separate terminals):"
echo "   • Grafana: kubectl port-forward -n $MONITORING_NS svc/prometheus-grafana 3000:3000"
echo "   • Prometheus: kubectl port-forward -n $MONITORING_NS svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo ""
echo "🔐 Grafana Credentials:"
echo "   • Username: admin"
echo "   • Password: admin123"
echo ""

# Wait for deployment
echo "⏳ Waiting for monitoring stack to be ready..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/prometheus-grafana -n $MONITORING_NS

echo "✅ Monitoring setup complete!"
echo ""
echo "📊 Monitoring Status:"
kubectl get pods -n $MONITORING_NS
kubectl get servicemonitors -n $MONITORING_NS
