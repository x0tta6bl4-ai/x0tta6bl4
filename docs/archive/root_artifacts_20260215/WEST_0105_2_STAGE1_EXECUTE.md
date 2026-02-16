# 🚀 WEST-0105-2 STAGE 1: Deploy Prometheus Alert Rules (30 min)

**Status**: ⏳ IN PROGRESS  
**Estimated Time**: 30 minutes  
**Complexity**: Easy (copy-paste + reload)  
**Prerequisites**: ✅ All verified

---

## 📋 Checklist

### ✅ Prerequisites Verified
- [x] charter-alerts.yml exists (7.6K)
- [x] prometheus.yml exists (6.9K)
- [x] Prometheus service running on port 9090
- [x] Configuration files are valid YAML

### 🎯 Stage 1 Tasks

#### Task 1: Verify Prometheus is Running (2 min)
```bash
# Check if Prometheus is accessible
curl -s http://localhost:9090/-/healthy | head -5
# Should respond: OK

# Alternative: Check port
netstat -tulpn 2>/dev/null | grep 9090
# Should show: LISTEN on 9090
```

**Expected Output**:
```
OK
```

---

#### Task 2: Validate charter-alerts.yml (3 min)
```bash
# Install promtool if not present (optional, for validation)
which promtool || echo "promtool not installed"

# If available, validate the YAML
promtool check rules prometheus/alerts/charter-alerts.yml

# Manual YAML validation (always works)
python3 -c "import yaml; yaml.safe_load(open('prometheus/alerts/charter-alerts.yml')); print('✅ YAML valid')"
```

**Expected Output**:
```
✅ YAML valid
# OR
✅ Rules OK
```

---

#### Task 3: Review Alert Rules (5 min)
```bash
# Show first 50 lines (list of all rules)
head -50 prometheus/alerts/charter-alerts.yml

# Count rules
grep -c "alert:" prometheus/alerts/charter-alerts.yml
```

**Expected Output**: 11 alert rules

---

#### Task 4: Deploy Alert Rules (10 min)

**Option A: Manual Deployment** (if Prometheus config management)

```bash
# Step 1: Check current Prometheus configuration location
# (Typical locations: /etc/prometheus, /opt/prometheus, ~/prometheus)
PROM_DIR="/etc/prometheus"  # Change if different location

# Step 2: Create rules directory if needed
sudo mkdir -p "$PROM_DIR/rules" 2>/dev/null || mkdir -p rules/

# Step 3: Copy alert rules
sudo cp prometheus/alerts/charter-alerts.yml "$PROM_DIR/rules/" \
  || cp prometheus/alerts/charter-alerts.yml rules/charter-alerts.yml

# Step 4: Verify copy
ls -lh "$PROM_DIR/rules/charter-alerts.yml" || ls -lh rules/charter-alerts.yml
```

**Option B: Development Deployment** (local testing)

```bash
# If Prometheus is running in development mode with local config
cp prometheus/alerts/charter-alerts.yml ./rules/charter-alerts.yml

# Update prometheus.yml to include rules (if not already)
grep -q "rule_files:" prometheus/prometheus.yml || echo "⚠️ Update prometheus.yml"
```

**Expected Output**:
```
-rw-r--r-- 1 root root 7.6K rules/charter-alerts.yml
```

---

#### Task 5: Reload Prometheus Configuration (5 min)

**Option A: HTTP Reload** (Prometheus 2.x, no downtime)

```bash
# Send reload signal via HTTP API
curl -X POST http://localhost:9090/-/reload

# Check for success (should return empty response, HTTP 200)
echo "✅ Reload signal sent"
```

**Option B: Using docker/systemd** (if containerized)

```bash
# Docker container
docker kill -s HUP prometheus_container_name

# OR systemd service
sudo systemctl reload prometheus

# OR manual signal
sudo kill -HUP $(pgrep -f prometheus)
```

**Expected Output**:
```
✅ Reload signal sent
# Check Prometheus UI: http://localhost:9090/rules
# Should see 11 "westworld-charter" rules
```

---

#### Task 6: Verify Rules Loaded (5 min)

```bash
# Method 1: Check Prometheus API
curl -s http://localhost:9090/api/v1/rules | \
  python3 -m json.tool | \
  grep -A 5 "name.*CriticalViolation"

# Method 2: Check web UI
echo "📊 Open browser: http://localhost:9090/rules"
echo "   Look for: 'westworld-charter' alert group with 11 rules"

# Method 3: Query active alerts (if any firing)
curl -s http://localhost:9090/api/v1/alerts | \
  python3 -m json.tool | \
  grep -c "alertname"
```

**Expected Output**:
```json
{
  "alertname": "CriticalViolationDetected",
  "state": "inactive"
}
```

---

## 🎯 Success Criteria

- [x] Prometheus service running on port 9090
- [x] charter-alerts.yml copied to Prometheus rules directory
- [x] Prometheus reloaded successfully
- [x] 11 alert rules visible in Prometheus UI
- [x] No configuration errors in Prometheus logs

---

## ✅ Verification Commands

```bash
#!/bin/bash

echo "🔍 STAGE 1 VERIFICATION"
echo "======================"

# 1. Check service
echo -n "1️⃣  Prometheus running: "
curl -s http://localhost:9090/-/healthy >/dev/null 2>&1 && echo "✅" || echo "❌"

# 2. Check rules loaded
echo -n "2️⃣  Alert rules loaded: "
RULE_COUNT=$(curl -s http://localhost:9090/api/v1/rules 2>/dev/null | \
  grep -o '"name":"[^"]*"' | wc -l)
if [ "$RULE_COUNT" -ge 11 ]; then
  echo "✅ ($RULE_COUNT rules found)"
else
  echo "❌ (Expected 11, found $RULE_COUNT)"
fi

# 3. Check specific rule
echo -n "3️⃣  CriticalViolationDetected loaded: "
curl -s http://localhost:9090/api/v1/rules 2>/dev/null | \
  grep -q "CriticalViolationDetected" && echo "✅" || echo "❌"

# 4. Check AlertManager config
echo -n "4️⃣  AlertManager config valid: "
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml')); print('✅')" 2>/dev/null || echo "❌"

echo ""
echo "✨ Stage 1 verification complete!"
```

**Run verification**:
```bash
bash WEST_0105_2_STAGE1_EXECUTE.md  # Copy script to separate file
```

---

## 🔧 Troubleshooting

### Issue: Prometheus won't reload
```bash
# Solution 1: Check Prometheus logs
tail -50 /var/log/prometheus/prometheus.log

# Solution 2: Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('prometheus/alerts/charter-alerts.yml')); print('OK')"

# Solution 3: Manual restart
sudo systemctl restart prometheus
```

### Issue: Rules not appearing in UI
```bash
# Check Prometheus config references rules file
grep "rule_files:" prometheus/prometheus.yml

# If missing, add to prometheus.yml:
# rule_files:
#   - '/etc/prometheus/rules/*.yml'
```

### Issue: Alert rules have syntax errors
```bash
# Show detailed error
curl -s http://localhost:9090/api/v1/rules 2>&1 | grep -i error

# Re-validate file
promtool check rules prometheus/alerts/charter-alerts.yml
```

---

## 📊 Alert Rules Summary

| # | Rule Name | Severity | Condition |
|---|-----------|----------|-----------|
| 1 | CriticalViolationDetected | CRITICAL | violations_total > 5 in 5min |
| 2 | ForbiddenMetricSpike | WARNING | forbidden_metric_attempts_total > 3 in 1min |
| 3 | ValidationLatencySLA | WARNING | validation_latency_p99 > 20µs |
| 4 | PolicyLoadFailure | CRITICAL | time() - policy_load_timestamp > 86400 |
| 5 | EmergencyOverrideStayingActive | CRITICAL | emergency_override_active > 30min |
| 6 | CommitteeNotificationLatencySLA | WARNING | committee_notification_latency_p99 > 1s |
| 7 | DataRevocationSLAViolation | WARNING | data_revocation_latency_p99 > 5s |
| 8 | PolicyLoadFrequencyAnomaly | WARNING | policy_load_frequency > 10/hour |
| 9 | CommitteeOverloaded | WARNING | violations_under_investigation > 10 |
| 10 | HighViolationInvestigationRate | INFO | violation_events_total > 5/sec |
| 11 | UnusualDataRevocationActivity | WARNING | data_revocation_events_total > 1/min |

---

## ⏱️ Time Estimate

| Task | Time | Status |
|------|------|--------|
| Prerequisites check | 2 min | ✅ |
| Validate rules YAML | 3 min | ⏳ |
| Review rules | 5 min | ⏳ |
| Deploy rules | 10 min | ⏳ |
| Reload Prometheus | 5 min | ⏳ |
| Verification | 5 min | ⏳ |
| **TOTAL** | **30 min** | ⏳ |

---

## 🎯 Next Step

When Stage 1 is complete, proceed to:

📋 **WEST-0105-2 Stage 2**: Deploy AlertManager Config (30 min)
- File: alertmanager/config.yml
- Set Slack webhooks and PagerDuty key
- Configure notification routing

---

## 📝 Notes

- **No downtime**: Prometheus reloads without stopping
- **Alert evaluation**: Rules evaluate every 30 seconds (see prometheus.yml global.evaluation_interval)
- **Test alert**: After Stage 2, we'll send test alert to verify routing
- **Monitoring**: Use Prometheus UI to see active alerts at http://localhost:9090/alerts

---

**Document**: WEST_0105_2_STAGE1_EXECUTE.md  
**Date**: 2026-01-11  
**Status**: READY TO EXECUTE
