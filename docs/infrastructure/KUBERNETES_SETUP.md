# ☸️ Kubernetes Setup Guide

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

---

## 📋 Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm 3.x
- Access to cluster with admin privileges

---

## 🚀 Quick Start

### 1. Install with Helm

```bash
# Add repository (if using OCI registry)
helm repo add x0tta6bl4 oci://ghcr.io/x0tta6bl4
helm repo update

# Install
helm install x0tta6bl4 x0tta6bl4/x0tta6bl4 \
  --namespace x0tta6bl4 \
  --create-namespace \
  --set production.enabled=true
```

### 2. Verify Installation

```bash
# Check pods
kubectl get pods -n x0tta6bl4

# Check services
kubectl get svc -n x0tta6bl4

# Check health
kubectl port-forward -n x0tta6bl4 svc/x0tta6bl4 8000:8000
curl http://localhost:8000/health
```

---

## ⚙️ Configuration

### Production Mode

```bash
helm install x0tta6bl4 ./helm/x0tta6bl4 \
  --set production.enabled=true \
  --set production.requireLiboqs=true \
  --set production.requireSpiffe=true
```

### Custom Values

```bash
helm install x0tta6bl4 ./helm/x0tta6bl4 \
  -f custom-values.yaml
```

### Example custom-values.yaml

```yaml
replicaCount: 5

production:
  enabled: true

resources:
  limits:
    cpu: 4000m
    memory: 8Gi
  requests:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
```

---

## 🔒 Security

### Network Policies

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-network-policy
  namespace: x0tta6bl4
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: x0tta6bl4
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 443
```

### RBAC

ServiceAccount создается автоматически через Helm chart.

---

## 📊 Monitoring

### ServiceMonitor (Prometheus)

ServiceMonitor создается автоматически если `monitoring.enabled=true`.

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4

# Check Prometheus targets
# (if Prometheus Operator installed)
kubectl get prometheus -A
```

---

## 🔄 Updates & Rollbacks

### Update

```bash
helm upgrade x0tta6bl4 ./helm/x0tta6bl4 \
  --set image.tag=3.4.1
```

### Rollback

```bash
helm rollback x0tta6bl4
```

---

## 🐛 Troubleshooting

### Pods Not Starting

```bash
# Check pod logs
kubectl logs -n x0tta6bl4 -l app.kubernetes.io/name=x0tta6bl4

# Check events
kubectl describe pod -n x0tta6bl4 <pod-name>

# Check dependency health
kubectl exec -n x0tta6bl4 <pod-name> -- python3 scripts/check_dependencies.py
```

### Health Check Failures

```bash
# Check health endpoint
kubectl port-forward -n x0tta6bl4 svc/x0tta6bl4 8000:8000
curl http://localhost:8000/health/dependencies
```

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

