# Kubernetes Deployment for Residential Proxy Infrastructure

## Структура манифестов

```
deploy/k8s/
├── namespace.yaml              # Namespace + ResourceQuota + LimitRange
├── redis-statefulset.yaml      # Redis StatefulSet с PVC
├── proxy-api-deployment.yaml   # Proxy API Deployment с HPA
├── proxy-node-agent-daemonset.yaml  # Node Agent DaemonSet
├── kustomization.yaml          # Kustomize конфигурация
├── monitoring/                 # Мониторинг
│   ├── servicemonitors.yaml    # ServiceMonitor CRDs
│   ├── prometheus-rules.yaml   # Alert rules
│   └── grafana-dashboards.yaml # Grafana dashboards
├── webhook/                    # Webhook notifications
│   └── alertmanager-webhook.yaml
├── security/                   # Security
│   ├── network-policies.yaml   # NetworkPolicies
│   └── sealed-secrets.yaml     # SealedSecrets / ExternalSecrets
└── README.md                   # Этот файл
```

## Быстрый старт

### 1. Установка с kustomize

```bash
# Применить все манифесты
kubectl apply -k deploy/k8s/

# Или поэтапно
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/redis-statefulset.yaml
kubectl apply -f deploy/k8s/proxy-api-deployment.yaml
kubectl apply -f deploy/k8s/proxy-node-agent-daemonset.yaml
```

### 2. Проверка статуса

```bash
# Проверить pods
kubectl get pods -n proxy-infrastructure

# Проверить services
kubectl get svc -n proxy-infrastructure

# Проверить HPA
kubectl get hpa -n proxy-infrastructure
```

## Компоненты

### Redis Cluster
- **StatefulSet**: 3 реплики
- **PersistentVolume**: 10Gi per pod
- **Service**: Headless service для кластеризации
- **Metrics**: Redis exporter на порту 9121

### Proxy API
- **Deployment**: 3+ реплики (HPA до 20)
- **HPA**: CPU 70%, Memory 80%, Custom metric (connections)
- **PDB**: minAvailable: 2
- **Init Container**: Валидация конфигурации
- **Sidecar**: Prometheus для метрик

### Node Agent
- **DaemonSet**: на всех нодах
- **hostNetwork**: true
- **Tolerations**: для master/control-plane нод

## Мониторинг

### Prometheus Rules
- ProxyPoolExhaustion (< 30% healthy)
- HighProxyLatency (P95 > 2000ms)
- ProxyFailureRate (> 10%)
- AuthenticationFailures
- TLSCertificateExpiry
- DDoSAttackDetected

### Grafana Dashboards
- Proxy Infrastructure Health
- Proxy Performance Metrics
- Geographic Distribution
- Error Analysis

## Webhook Notifications

### Поддерживаемые каналы
- Slack
- Telegram
- Discord
- Custom HTTP endpoints

### Severity levels
- critical: немедленная отправка
- warning: агрегированная отправка

## Security

### Network Policies
- Default deny all
- Разрешен трафик только между компонентами
- Ingress только из ingress-nginx и monitoring

### Secrets
- SealedSecrets для GitOps
- ExternalSecrets (Vault integration)
- TLS certificates

## Масштабирование

### Horizontal Pod Autoscaler
```yaml
minReplicas: 3
maxReplicas: 20
metrics:
  - CPU: 70%
  - Memory: 80%
  - Custom: proxy_active_connections > 1000
```

### Vertical Scaling
```bash
# Обновить resources
kubectl patch deployment proxy-api -n proxy-infrastructure -p '{"spec":{"template":{"spec":{"containers":[{"name":"proxy-api","resources":{"requests":{"cpu":"1000m","memory":"1Gi"}}}]}}}}'
```

## Troubleshooting

### Проверка логов
```bash
# Proxy API logs
kubectl logs -n proxy-infrastructure deployment/proxy-api -c proxy-api

# Redis logs
kubectl logs -n proxy-infrastructure statefulset/redis-cluster -c redis

# Node agent logs
kubectl logs -n proxy-infrastructure daemonset/proxy-node-agent
```

### Debug
```bash
# Exec в pod
kubectl exec -it -n proxy-infrastructure deployment/proxy-api -- /bin/sh

# Проверка конфигурации
kubectl get configmap -n proxy-infrastructure proxy-config -o yaml

# Проверка secrets
kubectl get secrets -n proxy-infrastructure
```

## Обновление

### Rolling update
```bash
# Обновить image
kubectl set image -n proxy-infrastructure deployment/proxy-api proxy-api=x0tta6bl4/proxy-orchestrator:v1.1.0

# Проверить rollout status
kubectl rollout status -n proxy-infrastructure deployment/proxy-api
```

### Rollback
```bash
# Откатить на предыдущую версию
kubectl rollout undo -n proxy-infrastructure deployment/proxy-api
```

## Production Checklist

- [ ] Настроить Vault/Sealed Secrets
- [ ] Обновить webhook URLs
- [ ] Настроить TLS certificates
- [ ] Проверить ResourceQuotas
- [ ] Настроить backup для Redis PVC
- [ ] Настроить log aggregation
- [ ] Проверить NetworkPolicies
- [ ] Настроить PodDisruptionBudgets
