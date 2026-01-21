# Monitoring & Alerting Deployment - Complete
**Дата:** 2026-01-08 02:00 CET  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ✅ **DEPLOYED**

---

## ✅ Deployment Status

### Components Deployed

1. **Prometheus** ✅
   - Status: Running
   - Service: prometheus.monitoring.svc.cluster.local:9090
   - ConfigMap: prometheus-config, prometheus-alerts
   - Alert Rules: 6 essential alerts configured

2. **Alertmanager** ✅
   - Status: Running
   - Service: alertmanager.monitoring.svc.cluster.local:9093
   - ConfigMap: alertmanager-config
   - Secret: alertmanager-telegram (with bot token and chat_id)

3. **Telegram Webhook Server** ⚠️
   - Status: Init container installing dependencies
   - Service: telegram-webhook.monitoring.svc.cluster.local:8080
   - ConfigMap: telegram-webhook-script

---

## 📱 Telegram Configuration

**Bot:** @x0tta6bl4_allert_bot  
**Token:** 7671485111:AAGFIIdWnXzKmNBjW_i5sVUKeqohA39KJEM  
**Chat ID:** 2018432227  
**Secret:** alertmanager-telegram (created in monitoring namespace)

---

## 🔧 Configuration Files

### Prometheus
- **Deployment:** `monitoring/prometheus-deployment-staging.yaml`
- **Config:** ConfigMap `prometheus-config`
- **Alerts:** ConfigMap `prometheus-alerts` (6 essential alerts)

### Alertmanager
- **Deployment:** `monitoring/alertmanager-deployment-staging.yaml`
- **Config:** ConfigMap `alertmanager-config`
- **Credentials:** Secret `alertmanager-telegram`

### Telegram Webhook
- **Deployment:** `monitoring/telegram-webhook-deployment.yaml`
- **Script:** ConfigMap `telegram-webhook-script`

---

## 📊 Alert Rules Configured

1. **X0TTA6BL4HealthCheckFailed** (Critical)
   - Service down > 2 minutes

2. **X0TTA6BL4HighErrorRate** (Warning)
   - Error rate > 10/sec for 5 minutes

3. **X0TTA6BL4HighLatency** (Warning)
   - p95 latency > 1s for 5 minutes

4. **X0TTA6BL4PQCHandshakeFailure** (Critical)
   - PQC failures > 0.1/sec

5. **X0TTA6BL4HighMemoryUsage** (Warning)
   - Memory > 90% for 10 minutes

6. **X0TTA6BL4FrequentRestarts** (Warning)
   - Pod restarts detected

---

## 🧪 Testing Alert Delivery

### Manual Test via Telegram API

```bash
curl "https://api.telegram.org/bot7671485111:AAGFIIdWnXzKmNBjW_i5sVUKeqohA39KJEM/sendMessage?chat_id=2018432227&text=Test%20alert"
```

### Test via Alertmanager API

```bash
# Port-forward Alertmanager
kubectl port-forward -n monitoring svc/alertmanager 9093:9093

# Send test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "telegram-critical",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Test Alert",
        "description": "This is a test alert"
      },
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }]
  }'
```

### Test via Webhook Server

```bash
# Port-forward webhook server
kubectl port-forward -n monitoring svc/telegram-webhook 8080:8080

# Send test alert
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "telegram-critical",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {"alertname": "TestAlert", "severity": "critical"},
      "annotations": {"summary": "Test Alert", "description": "Test description"},
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }]
  }'
```

---

## 🔍 Verification Commands

### Check Pods Status

```bash
kubectl get pods -n monitoring
```

### Check Services

```bash
kubectl get svc -n monitoring
```

### Check ConfigMaps

```bash
kubectl get configmaps -n monitoring
```

### Check Secrets

```bash
kubectl get secrets -n monitoring
```

### View Prometheus UI

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090
```

### View Alertmanager UI

```bash
kubectl port-forward -n monitoring svc/alertmanager 9093:9093
# Open http://localhost:9093
```

### Check Prometheus Targets

```bash
# After port-forward
curl http://localhost:9090/api/v1/targets | python3 -m json.tool
```

### Check Alertmanager Configuration

```bash
# After port-forward
curl http://localhost:9093/api/v1/status | python3 -m json.tool
```

---

## 📋 Next Steps

### Immediate (Today)

1. ✅ Telegram credentials configured
2. ✅ Prometheus deployed
3. ✅ Alertmanager deployed
4. ⚠️ Telegram webhook server deploying (init container installing dependencies)
5. ⏳ Test alert delivery (after webhook server is ready)

### Short-term (Jan 9)

1. Verify all pods are running
2. Test alert delivery end-to-end
3. Verify Prometheus is scraping x0tta6bl4 metrics
4. Verify Alertmanager is receiving alerts from Prometheus
5. Verify Telegram notifications are working

### Long-term (After Beta Launch)

1. Setup Grafana dashboards
2. Add more alert rules as needed
3. Setup additional notification channels (email, PagerDuty)
4. Review and tune alert thresholds based on real usage

---

## 🐛 Troubleshooting

### Webhook Server Not Ready

**Symptom:** `telegram-webhook` pod stuck in `Init:0/1`

**Solution:**
```bash
# Check init container logs
kubectl logs -n monitoring <pod-name> -c install-requests

# If init container fails, check if requests package is installing correctly
# The init container installs requests and copies to shared volume
```

### Prometheus Not Scraping

**Symptom:** No targets in Prometheus UI

**Solution:**
```bash
# Check Prometheus config
kubectl get configmap prometheus-config -n monitoring -o yaml

# Check if x0tta6bl4 pods have metrics endpoint
curl http://localhost:8080/metrics

# Verify service discovery
kubectl get pods -n x0tta6bl4-staging -l app=x0tta6bl4
```

### Alertmanager Not Sending to Telegram

**Symptom:** Alerts in Alertmanager but no Telegram messages

**Solution:**
```bash
# Check Alertmanager logs
kubectl logs -n monitoring -l app=alertmanager

# Check webhook server logs
kubectl logs -n monitoring -l app=telegram-webhook

# Verify Secret exists
kubectl get secret alertmanager-telegram -n monitoring

# Test webhook server directly
kubectl port-forward -n monitoring svc/telegram-webhook 8080:8080
curl -X POST http://localhost:8080/ -H "Content-Type: application/json" -d '{"alerts":[{"labels":{"alertname":"test"}}]}'
```

---

## ✅ Success Criteria

- [x] Telegram credentials configured
- [x] Prometheus deployed and running
- [x] Alertmanager deployed and running
- [ ] Telegram webhook server ready (in progress)
- [ ] Test alert delivered to Telegram
- [ ] Prometheus scraping x0tta6bl4 metrics
- [ ] Alertmanager receiving alerts from Prometheus

---

**Status:** ✅ **DEPLOYED** (webhook server initializing)  
**Next Step:** Wait for webhook server to be ready, then test alert delivery  
**Ready for:** Beta Launch (Jan 11-12, 2026)

