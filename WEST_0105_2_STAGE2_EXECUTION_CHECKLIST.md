# ✅ WEST-0105-2 STAGE 2 EXECUTION CHECKLIST

**Date**: 2026-01-11  
**Phase**: Stage 2 of Phase 2 (Dashboards & Alerting)  
**Estimated Time**: 30 minutes  
**Status**: 🎯 ACTIVE - FOLLOW THIS CHECKLIST  

---

## 🚀 PRE-EXECUTION CHECKLIST

Before starting Stage 2, verify:

- [ ] AlertManager is running on port 9093
  ```bash
  curl -s http://localhost:9093/-/healthy
  # Should return: OK
  ```

- [ ] Prometheus is running on port 9090
  ```bash
  curl -s http://localhost:9090/-/healthy
  # Should return: OK
  ```

- [ ] You have Slack workspace access
  - [ ] Can access https://api.slack.com

- [ ] You can access AlertManager UI
  - [ ] Open http://localhost:9093 in browser

- [ ] alertmanager/config.yml exists
  ```bash
  ls -lh alertmanager/config.yml
  # Should show file exists
  ```

**If any checks fail**: Stop and fix before proceeding

---

## 📋 TASK 1: CREATE SLACK WEBHOOKS (5 min)

### Checklist

- [ ] Opened Slack workspace
- [ ] Created channel: #charter-security
- [ ] Created channel: #charter-sre
- [ ] Created channel: #charter-monitoring

### Get Webhook URLs

- [ ] Went to: https://api.slack.com/apps
- [ ] Created app: "Prometheus AlertManager"
- [ ] In "Incoming Webhooks": Clicked "Activate"
- [ ] Added webhook for #charter-security
  - [ ] Copied URL and saved it: `WEBHOOK_SECURITY = https://hooks.slack.com/services/...`
- [ ] Added webhook for #charter-sre
  - [ ] Copied URL and saved it: `WEBHOOK_SRE = https://hooks.slack.com/services/...`
- [ ] Added webhook for #charter-monitoring
  - [ ] Copied URL and saved it: `WEBHOOK_MONITORING = https://hooks.slack.com/services/...`

### Verification

```bash
# Test webhooks directly (optional)
curl -X POST '$WEBHOOK_SECURITY' -H 'Content-Type: application/json' -d '{"text": "Test"}'
# Should respond: 1
```

- [ ] All 3 webhook URLs obtained and saved

---

## 📋 TASK 2: UPDATE ALERTMANAGER CONFIG (10 min)

### Backup Current Config

```bash
cp alertmanager/config.yml alertmanager/config.yml.backup
```

- [ ] Backup created

### Replace Webhook URLs

Open file:
```bash
nano alertmanager/config.yml
```

**Or use sed** (replace with your actual URLs):

```bash
# Replace security webhook
sed -i 's|YOUR_SECURITY_WEBHOOK|https://hooks.slack.com/services/T.../B.../XXX|g' alertmanager/config.yml

# Replace SRE webhook  
sed -i 's|YOUR_SRE_WEBHOOK|https://hooks.slack.com/services/T.../B.../YYY|g' alertmanager/config.yml

# Replace monitoring webhook
sed -i 's|YOUR_WEBHOOK_URL_HERE|https://hooks.slack.com/services/T.../B.../ZZZ|g' alertmanager/config.yml

# Optional: Replace PagerDuty key
sed -i 's|YOUR_PAGERDUTY_KEY_HERE|your_actual_key_here|g' alertmanager/config.yml
```

- [ ] All webhook URLs replaced

### Verify No Placeholders Remain

```bash
grep -i "YOUR_\|_HERE\|placeholder" alertmanager/config.yml
# Should show: No matches (clean!)
```

- [ ] No placeholders found

### Validate YAML Syntax

```bash
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml')); print('✅ Valid')"
```

- [ ] YAML validation passed

---

## 📋 TASK 3: DEPLOY CONFIGURATION (5 min)

### Find AlertManager Installation

```bash
# Check where AlertManager is installed
ps aux | grep alertmanager | grep -v grep
# Shows: /path/to/alertmanager

# Check config location
sudo grep -r "config.file" /etc/systemd/system/ 2>/dev/null
# Shows: /etc/alertmanager/config.yml (or other location)
```

- [ ] Identified AlertManager location

### Copy Configuration

**For Systemd** (/etc/alertmanager):
```bash
sudo cp alertmanager/config.yml /etc/alertmanager/config.yml
sudo chown alertmanager:alertmanager /etc/alertmanager/config.yml
ls -lh /etc/alertmanager/config.yml
```

**For Local/Manual**:
```bash
cp alertmanager/config.yml ~/.alertmanager/config.yml
# or
cp alertmanager/config.yml ./alertmanager/config.yml
```

**For Docker**:
```bash
CONTAINER_ID=$(docker ps | grep alertmanager | awk '{print $1}')
docker cp alertmanager/config.yml $CONTAINER_ID:/etc/alertmanager/config.yml
```

- [ ] Config file copied

### Reload AlertManager

```bash
# Via HTTP API (no downtime)
curl -X POST http://localhost:9093/-/reload
# Should respond: HTTP 200 (no output)

# Or via systemd
sudo systemctl reload alertmanager

# Or via signal
sudo kill -HUP $(pgrep -f alertmanager)
```

- [ ] Reload command executed

### Check for Errors

```bash
# Check logs
tail -20 /var/log/alertmanager/alertmanager.log
# Should show: No errors about config parsing
```

- [ ] No errors in logs

---

## 📋 TASK 4: TEST ROUTING (5 min)

### Send Test Alert

```bash
# Create and send test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "critical"
    },
    "annotations": {
      "summary": "Test alert - Stage 2 deployment",
      "description": "If you see this in #charter-security, routing works!"
    }
  }]'

# Expected response: HTTP 200
```

- [ ] Test alert sent

### Check AlertManager UI

Open: http://localhost:9093

- [ ] Alerts tab shows "TestAlert"
- [ ] Alert shows status: "firing"
- [ ] Alert shows severity: "critical"

### Check Slack Channels

- [ ] #charter-security: Alert notification appeared ✅
- [ ] #charter-sre: No notification (correct - wrong severity) ✅
- [ ] #charter-monitoring: No notification (correct - wrong severity) ✅

### Test Different Severities (Optional)

```bash
# Test warning alert (should go to #charter-sre)
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestWarning",
      "severity": "warning"
    },
    "annotations": {
      "summary": "Test warning - should appear in #charter-sre"
    }
  }]'
```

- [ ] Critical alert → #charter-security ✅
- [ ] Warning alert → #charter-sre ✅ (optional)

---

## 📋 TASK 5: VERIFY SETUP (5 min)

### AlertManager Health

```bash
# Health check
curl -s http://localhost:9093/-/healthy
# Should respond: OK
```

- [ ] AlertManager healthy

### Check Receivers Loaded

```bash
# View receivers
curl -s http://localhost:9093/api/v1/receivers | python3 -m json.tool | head -30

# Should show: default, critical-security, security-warnings, sre-warnings, info-alerts
```

- [ ] 5 receivers configured
- [ ] Receiver names correct

### Check Prometheus Rules

```bash
# Count alert rules
curl -s http://localhost:9090/api/v1/rules | python3 -m json.tool | grep -c "alert"
# Should show: 11 (or more)
```

- [ ] Alert rules loaded in Prometheus

### Run Verification Script

```bash
bash scripts/verify-observability.sh

# Should show:
# ✅ Prometheus running
# ✅ Alert rules loaded
# ✅ AlertManager configured
# ✅ Slack webhooks responsive
```

- [ ] All checks passing

### View AlertManager UI Status

Open: http://localhost:9093/status

- [ ] Config status: success
- [ ] Uptime: positive number
- [ ] No error messages

- [ ] AlertManager UI shows healthy status

---

## 🎯 STAGE 2 COMPLETION VERIFICATION

Run full verification:

```bash
cat << 'EOF'
═══════════════════════════════════════════════════════════════════════════
STAGE 2 VERIFICATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════

AlertManager:
  [ ] Service running on port 9093
  [ ] Config loaded without errors
  [ ] 5 receivers configured
  [ ] Test alert received in Slack

Slack Integration:
  [ ] #charter-security receiving alerts
  [ ] #charter-sre receiving alerts
  [ ] #charter-monitoring receiving alerts
  [ ] Webhooks responding to alerts

Prometheus:
  [ ] 11 alert rules loaded
  [ ] Rules evaluating correctly
  [ ] AlertManager receiving alerts

Configuration:
  [ ] alertmanager/config.yml updated
  [ ] All webhook URLs configured
  [ ] YAML syntax valid
  [ ] No placeholder values remaining

═══════════════════════════════════════════════════════════════════════════
EOF
```

---

## ✅ FINAL SIGN-OFF: STAGE 2 COMPLETE

When ALL checkboxes above are checked:

- [ ] Stage 1: Alert Rules ✅ (validated previously)
- [ ] Stage 2: AlertManager Config ✅ (just completed)
- [ ] Stage 3: Grafana Dashboards ⏳ (next phase)

---

## 📊 STATUS DASHBOARD

```
STAGE 1 (Prometheus)    ✅ VALIDATED
STAGE 2 (AlertManager)  🎯 IN PROGRESS
  ├─ Task 1: Webhooks        [ ]
  ├─ Task 2: Config Update   [ ]
  ├─ Task 3: Deploy          [ ]
  ├─ Task 4: Test Routing    [ ]
  └─ Task 5: Verify          [ ]
STAGE 3 (Grafana)       ⏳ READY
```

---

## 🚀 NEXT STEPS AFTER STAGE 2

When Stage 2 is complete ✅:

1. **Proceed to Stage 3**: WEST_0105_2_DASHBOARDS_PLAN.md
2. **Create Grafana dashboards**: 2 dashboards, 14 panels
3. **Run final verification**: `bash scripts/verify-observability.sh`
4. **Complete Phase 2**: Full observability layer operational

**Phase 2 Total Time**: ~2.5-3 hours (10 min Stage 1 + 30 min Stage 2 + 90 min Stage 3 + 30 min verification)

---

## 📁 KEY FILES

- **This Guide**: WEST_0105_2_STAGE2_EXECUTION_CHECKLIST.md
- **Detailed Steps**: WEST_0105_2_STAGE2_DEPLOYMENT_EXECUTION.md
- **Config File**: alertmanager/config.yml
- **Verification**: scripts/verify-observability.sh
- **Next Stage**: WEST_0105_2_DASHBOARDS_PLAN.md

---

**Start Date**: 2026-01-11  
**Status**: ACTIVE - FOLLOW THIS CHECKLIST  
**Time Estimate**: 30 minutes  
**Difficulty**: Medium
