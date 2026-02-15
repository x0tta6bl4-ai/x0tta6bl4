# Production Runbook for x0tta6bl4

**Версия:** 1.0  
**Дата:** 2025-12-29  
**Статус:** ✅ **PRODUCTION READY**

---

## 🚨 Emergency Procedures

### Service Down

```bash
# 1. Check deployment status
kubectl get deployment x0tta6bl4
kubectl get pods -l app=x0tta6bl4

# 2. Check logs
kubectl logs -l app=x0tta6bl4 --tail=100

# 3. Check health endpoint
kubectl exec -it <pod-name> -- curl http://localhost:8080/health

# 4. Restart deployment if needed
kubectl rollout restart deployment/x0tta6bl4

# 5. Scale up if needed
kubectl scale deployment x0tta6bl4 --replicas=5
```

### High Memory Usage

```bash
# 1. Check resource usage
kubectl top pods -l app=x0tta6bl4

# 2. Check memory limits
kubectl describe deployment x0tta6bl4 | grep -A 5 "Limits"

# 3. Restart pods if needed
kubectl delete pod -l app=x0tta6bl4

# 4. Scale horizontally
kubectl scale deployment x0tta6bl4 --replicas=5
```

### High CPU Usage

```bash
# 1. Check CPU usage
kubectl top pods -l app=x0tta6bl4

# 2. Check for resource limits
kubectl describe deployment x0tta6bl4 | grep -A 5 "Limits"

# 3. Scale horizontally
kubectl scale deployment x0tta6bl4 --replicas=5
```

### Network Issues

```bash
# 1. Check service endpoints
kubectl get endpoints x0tta6bl4

# 2. Check service connectivity
kubectl exec -it <pod-name> -- curl http://x0tta6bl4:80/health

# 3. Check ingress
kubectl get ingress x0tta6bl4
kubectl describe ingress x0tta6bl4
```

---

## 🔄 Deployment Procedures

### Rolling Update

```bash
# 1. Update image
kubectl set image deployment/x0tta6bl4 app=registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-NEW_SHA

# 2. Watch rollout
kubectl rollout status deployment/x0tta6bl4

# 3. Rollback if needed
kubectl rollout undo deployment/x0tta6bl4
```

### Blue-Green Deployment

```bash
# 1. Deploy green version
kubectl apply -f deployment/kubernetes/blue-green-deployment.yaml

# 2. Wait for green to be ready
kubectl wait --for=condition=available deployment/x0tta6bl4-green

# 3. Switch service to green
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'

# 4. Verify green is serving traffic
kubectl get endpoints x0tta6bl4

# 5. Scale down blue
kubectl scale deployment x0tta6bl4-blue --replicas=0
```

---

## 📊 Monitoring

### Health Checks

```bash
# Check health endpoint
curl http://x0tta6bl4.example.com/health

# Expected response:
# {
#   "status": "ok",
#   "version": "3.0.0",
#   "components": {...},
#   "component_stats": {...}
# }
```

### Metrics

```bash
# Prometheus metrics
curl http://x0tta6bl4.example.com/metrics

# Key metrics:
# - process_resident_memory_bytes
# - mesh_mttd_seconds_bucket
# - gnn_recall_score
# - mesh_mape_k_*
```

### Logs

```bash
# View logs
kubectl logs -l app=x0tta6bl4 --tail=100 -f

# Filter by level
kubectl logs -l app=x0tta6bl4 | grep ERROR

# Export logs
kubectl logs -l app=x0tta6bl4 > logs.txt
```

---

## 🔧 Maintenance

### Update Configuration

```bash
# Update ConfigMap
kubectl edit configmap x0tta6bl4-config

# Restart pods to apply changes
kubectl rollout restart deployment/x0tta6bl4
```

### Scale Deployment

```bash
# Scale up
kubectl scale deployment x0tta6bl4 --replicas=5

# Scale down
kubectl scale deployment x0tta6bl4 --replicas=3

# Auto-scaling (if HPA configured)
kubectl get hpa x0tta6bl4
```

### Backup

```bash
# Export configuration
kubectl get configmap x0tta6bl4-config -o yaml > config-backup.yaml

# Export deployment
kubectl get deployment x0tta6bl4 -o yaml > deployment-backup.yaml
```

---

## 🧪 Testing

### Performance Testing

```bash
# Run performance tests
bash scripts/performance_test.sh http://x0tta6bl4.example.com 60 10
```

### Load Testing

```bash
# Using k6 (if available)
k6 run load-test.js

# Using Apache Bench
ab -n 10000 -c 100 http://x0tta6bl4.example.com/health
```

### Validation

```bash
# Run full validation suite
bash scripts/run_production_validation.sh
```

---

## 📝 Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name>

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp

# Check logs
kubectl logs <pod-name>
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets

# Verify image exists
docker pull registry.gitlab.com/x0tta6bl4/x0tta6bl4:sha256-SHA

# Check registry access
kubectl describe pod <pod-name> | grep -A 5 "Events"
```

### Health Check Failures

```bash
# Test health endpoint manually
kubectl exec -it <pod-name> -- curl http://localhost:8080/health

# Check probe configuration
kubectl describe deployment x0tta6bl4 | grep -A 10 "Liveness\|Readiness"

# Adjust probe timing if needed
kubectl patch deployment x0tta6bl4 -p '{"spec":{"template":{"spec":{"containers":[{"name":"app","livenessProbe":{"initialDelaySeconds":60}}]}}}}'
```

---

## ✅ Pre-Deployment Checklist

- [ ] Image built and pushed to registry
- [ ] Image tag updated in deployment.yaml
- [ ] ConfigMap updated if needed
- [ ] Resource limits reviewed
- [ ] Health checks configured
- [ ] Security context verified
- [ ] Backup of current deployment
- [ ] Rollback plan prepared

---

## 📞 Support

- **Documentation:** `docs/deployment/`
- **Troubleshooting:** `docs/deployment/TROUBLESHOOTING.md`
- **API Reference:** `docs/api/API_REFERENCE.md`

---

**Mesh обновлён. Production runbook готов.**  
**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

