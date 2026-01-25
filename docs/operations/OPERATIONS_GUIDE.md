# 🔧 Operations Guide

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

---

## 📋 Overview

Руководство по операционному управлению x0tta6bl4 в production.

---

## 🚀 Deployment

### Staging Deployment

```bash
# Deploy to staging
./scripts/deploy_staging.sh latest

# Monitor deployment
./scripts/monitor_deployment.sh x0tta6bl4-staging 300
```

### Production Deployment

```bash
# Deploy to production (requires confirmation)
CONFIRM_PRODUCTION=true ./scripts/deploy_production.sh 3.4.0

# Monitor deployment
./scripts/monitor_deployment.sh x0tta6bl4 600
```

---

## 🔄 Rollback

### Rollback to Previous Revision

```bash
# Staging rollback
./scripts/rollback.sh x0tta6bl4-staging previous

# Production rollback (requires confirmation)
CONFIRM_ROLLBACK=true ./scripts/rollback.sh x0tta6bl4 previous
```

### Rollback to Specific Revision

```bash
# Rollback to revision 5
./scripts/rollback.sh x0tta6bl4 5
```

---

## 📊 Monitoring

### Health Checks

```bash
# Port forward
kubectl port-forward -n x0tta6bl4 svc/x0tta6bl4 8000:8000

# Health check
curl http://localhost:8000/health

# Dependencies
curl http://localhost:8000/health/dependencies

# Metrics
curl http://localhost:8000/metrics
```

### Deployment Monitoring

```bash
# Monitor for 5 minutes
./scripts/monitor_deployment.sh x0tta6bl4 300
```

---

## 🔍 Troubleshooting

### Pod Issues

```bash
# Check pod status
kubectl get pods -n x0tta6bl4

# Check pod logs
kubectl logs -n x0tta6bl4 deployment/x0tta6bl4

# Describe pod
kubectl describe pod -n x0tta6bl4 <pod-name>
```

### Service Issues

```bash
# Check service
kubectl get svc -n x0tta6bl4

# Check endpoints
kubectl get endpoints -n x0tta6bl4
```

### Network Issues

```bash
# Check network policies
kubectl get networkpolicy -n x0tta6bl4

# Test connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- sh
```

---

## 💾 Backup

### Configuration Backup

```bash
# Backup all configurations
./scripts/backup_config.sh x0tta6bl4
```

### Restore from Backup

```bash
# Extract backup
tar -xzf backups/YYYYMMDD_HHMMSS.tar.gz

# Restore resources
kubectl apply -f backups/YYYYMMDD_HHMMSS/kubernetes-resources.yaml
```

---

## 🔐 Security

### Certificate Rotation

```bash
# Check SPIFFE certificates
kubectl exec -n x0tta6bl4 deployment/x0tta6bl4 -- \
    python3 -c "from src.security.spiffe.controller.spiffe_controller import SPIFFEController; ..."
```

### Network Policies

```bash
# Check network policies
kubectl get networkpolicy -n x0tta6bl4

# Update network policy
kubectl apply -f helm/x0tta6bl4/templates/networkpolicy.yaml
```

---

## 📈 Scaling

### Manual Scaling

```bash
# Scale up
kubectl scale deployment/x0tta6bl4 -n x0tta6bl4 --replicas=5

# Scale down
kubectl scale deployment/x0tta6bl4 -n x0tta6bl4 --replicas=3
```

### Auto Scaling (HPA)

```bash
# Check HPA
kubectl get hpa -n x0tta6bl4

# Update HPA
kubectl edit hpa x0tta6bl4 -n x0tta6bl4
```

---

## 🧪 Testing

### Load Testing

```bash
# Run load test
./scripts/load_test.sh http://localhost:8000 60s 10
```

### Health Check Testing

```bash
# Continuous health checks
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

---

## 📊 Metrics

### Prometheus Metrics

```bash
# Query metrics
curl http://localhost:8000/metrics | grep x0tta6bl4
```

### Grafana Dashboards

- Access Grafana: `http://grafana.x0tta6bl4.io`
- Dashboard: "x0tta6bl4 Overview"

---

## 🚨 Alerts

### Alert Rules

Alert rules are configured in `monitoring/prometheus/alerts.yaml`:

- Health check failures
- Critical dependency missing
- PQC handshake failures
- High error rate
- High latency
- Resource exhaustion

### Alert Channels

- Email
- Slack
- PagerDuty

---

## 🔧 Maintenance

### Cluster Validation

```bash
# Validate cluster readiness
./scripts/validate_cluster.sh
```

### Dependency Updates

```bash
# Check dependency health
python3 scripts/check_dependencies.py

# Update requirements
pip install -r requirements-core.txt --upgrade
```

---

## 📚 Additional Resources

- [Kubernetes Setup Guide](../infrastructure/KUBERNETES_SETUP.md)
- [Monitoring Setup Guide](../infrastructure/MONITORING_SETUP.md)
- [Security Setup Guide](../infrastructure/SECURITY_SETUP.md)
- [Beta Testing Guide](../beta/BETA_TESTING_GUIDE.md)

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

