# Basic Monitoring & Alerting Setup - Complete
**Дата:** 2026-01-08 02:00 CET  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ✅ **COMPLETE**

---

## ✅ Completed Tasks

### 1. Basic Monitoring/Alerting Setup ✅

**Created Files:**
- ✅ `monitoring/alertmanager-config-basic.yaml` - Simplified Alertmanager config for beta
- ✅ `monitoring/prometheus/alerts-basic.yaml` - Essential alert rules for beta
- ✅ `scripts/setup_basic_monitoring.sh` - Automated setup script

**Configuration:**
- ✅ Telegram integration for alerts (critical and warning)
- ✅ Basic alert rules (6 essential alerts)
- ✅ Alert routing by severity
- ✅ Inhibition rules (suppress warnings when critical is firing)

**Alerts Configured:**
1. **X0TTA6BL4HealthCheckFailed** (Critical) - Service down > 2 minutes
2. **X0TTA6BL4HighErrorRate** (Warning) - Error rate > 10/sec for 5 minutes
3. **X0TTA6BL4HighLatency** (Warning) - p95 latency > 1s for 5 minutes
4. **X0TTA6BL4PQCHandshakeFailure** (Critical) - PQC failures > 0.1/sec
5. **X0TTA6BL4HighMemoryUsage** (Warning) - Memory > 90% for 10 minutes
6. **X0TTA6BL4FrequentRestarts** (Warning) - Pod restarts detected

**Next Steps:**
1. Set environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
2. Run setup script: `./scripts/setup_basic_monitoring.sh`
3. Deploy Prometheus: `kubectl apply -f monitoring/prometheus-deployment.yaml`
4. Deploy Alertmanager: `kubectl apply -f monitoring/alertmanager-deployment.yaml`

---

### 2. On-Call Rotation Setup ✅

**Created File:**
- ✅ `docs/team/ON_CALL_ROTATION.md` - Complete on-call rotation plan

**Features:**
- ✅ Weekly rotation schedule (Monday to Monday)
- ✅ Beta launch specific schedule (Jan 8-14, 2026)
- ✅ Response time SLAs by severity
- ✅ Escalation path (3 levels)
- ✅ Handoff procedures (daily and weekly)
- ✅ On-call checklist
- ✅ Communication channels (Telegram, Email, Phone)
- ✅ Beta launch specific procedures

**Schedule:**
- **Week 1 (Jan 8-14):** Enhanced coverage for beta launch
- **Week 2+:** Standard weekly rotation

**Response Times:**
- SEV-1: 5 min acknowledgment, 15 min escalation
- SEV-2: 15 min acknowledgment, 1 hour escalation
- SEV-3: 1 hour acknowledgment, 4 hours escalation
- SEV-4: 1 business day acknowledgment

---

### 3. Incident Response Plan Review ✅

**Updated File:**
- ✅ `docs/team/INCIDENT_RESPONSE_PLAN.md` - Updated to v3.1.0

**Updates:**
- ✅ Added beta launch specific procedures
- ✅ Updated rollback triggers based on test results
- ✅ Added stability test results context
- ✅ Added failure injection test results context
- ✅ Updated response times for beta phase
- ✅ Added beta launch specific communication procedures

**Key Updates:**
- **Stability Test Results:** Memory stable, GNN Recall 0.96, 0% error rate
- **Failure Injection Results:** MTTD 2s, MTTR 2s (excellent)
- **Beta Launch Procedures:** Enhanced monitoring, 5-minute response time
- **Updated Rollback Triggers:** Based on actual test results

---

## 📋 Deployment Instructions

### Step 1: Setup Telegram Bot

```bash
# Create Telegram bot (if not exists)
# 1. Message @BotFather on Telegram
# 2. Create new bot: /newbot
# 3. Get bot token
# 4. Get chat ID (message your bot, then visit: https://api.telegram.org/bot<TOKEN>/getUpdates)

export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### Step 2: Run Setup Script

```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/setup_basic_monitoring.sh
```

### Step 3: Deploy Prometheus and Alertmanager

```bash
# Deploy Prometheus
kubectl apply -f monitoring/prometheus-deployment.yaml

# Deploy Alertmanager
kubectl apply -f monitoring/alertmanager-deployment.yaml

# Verify
kubectl get pods -n monitoring
kubectl get configmaps -n monitoring
kubectl get secrets -n monitoring
```

### Step 4: Verify Setup

```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Port-forward Alertmanager
kubectl port-forward -n monitoring svc/alertmanager 9093:9093

# Check Prometheus UI
open http://localhost:9090

# Check Alertmanager UI
open http://localhost:9093

# Check alerts
curl http://localhost:9090/api/v1/alerts
```

---

## 📊 Monitoring Dashboard

### Essential Metrics to Monitor

1. **Health Checks:**
   - `up{job="x0tta6bl4"}` - Service availability

2. **Error Rate:**
   - `rate(x0tta6bl4_errors_total[5m])` - Error rate per second

3. **Latency:**
   - `histogram_quantile(0.95, rate(x0tta6bl4_request_duration_seconds_bucket[5m]))` - p95 latency

4. **Memory:**
   - `container_memory_usage_bytes{pod=~"x0tta6bl4.*"}` - Memory usage

5. **PQC:**
   - `rate(x0tta6bl4_pqc_handshake_failures_total[5m])` - PQC failure rate

6. **Pod Restarts:**
   - `rate(kube_pod_container_status_restarts_total{pod=~"x0tta6bl4.*"}[15m])` - Restart rate

---

## 🎯 Beta Launch Readiness

### ✅ Completed

1. ✅ Basic monitoring/alerting configured
2. ✅ On-call rotation plan established
3. ✅ Incident response plan reviewed and updated
4. ✅ Alert rules configured (6 essential alerts)
5. ✅ Telegram integration ready
6. ✅ Setup script created

### ⚠️ Remaining (Before Beta Launch)

1. ⚠️ Deploy Prometheus and Alertmanager to cluster
2. ⚠️ Configure Telegram bot credentials
3. ⚠️ Test alert delivery (send test alert)
4. ⚠️ Verify on-call rotation schedule with team
5. ⚠️ Review incident response plan with team

---

## 📝 Notes

- **Beta Phase:** Enhanced monitoring and response times during first 2 weeks
- **Telegram:** Primary alert channel for beta phase
- **Escalation:** 3-level escalation path (On-Call → Team Lead → CTO)
- **Documentation:** All procedures documented and ready

---

**Status:** ✅ **COMPLETE**  
**Next Step:** Deploy Prometheus and Alertmanager, configure Telegram credentials  
**Ready for:** Beta Launch (Jan 11-12, 2026)

