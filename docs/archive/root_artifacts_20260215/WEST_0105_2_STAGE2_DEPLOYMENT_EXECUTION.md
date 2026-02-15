# 🚀 WEST-0105-2 STAGE 2 DEPLOYMENT: COMPLETE EXECUTION GUIDE

**Status**: 🎯 ACTIVE DEPLOYMENT NOW  
**Estimated Time**: 30 minutes  
**Complexity**: Medium (configure webhooks + deploy)  
**Prerequisites**: ✅ All verified  

---

## 📋 STAGE 2 OVERVIEW

Deploy AlertManager configuration with Slack & PagerDuty integration. After completion, Prometheus alerts will automatically route to notification channels.

**What happens**:
1. Prometheus fires alert rule
2. AlertManager receives alert
3. AlertManager checks routing rules
4. Alert sent to Slack/PagerDuty channels
5. Team receives notification

---

## 🎯 EXECUTION PLAN (30 min)

```
Task 1: Create Slack Webhooks (5 min)  
Task 2: Update AlertManager Config (10 min)  
Task 3: Deploy Configuration (5 min)  
Task 4: Test Routing (5 min)  
Task 5: Verify Setup (5 min)  
TOTAL: 30 min
```

---

## ✅ TASK 1: Create Slack Webhooks (5 min)

### Step 1a: Create Slack Channels (if needed)

In your Slack workspace, create 3 channels:

```
#charter-security      (for critical/security alerts)
#charter-sre          (for performance/SLA warnings)
#charter-monitoring   (for informational alerts)
```

**How to create a channel in Slack**:
1. Click "+" next to "Channels" in sidebar
2. Click "Create a channel"
3. Enter channel name
4. Click "Create"

### Step 1b: Get Webhook URLs

For each channel, create an incoming webhook:

**Repeat for each channel**:

1. **Go to Slack API**: https://api.slack.com/apps
2. **Click "Create New App"** → **"From scratch"**
3. **App name**: `Prometheus AlertManager`
4. **Workspace**: Select your workspace
5. **Click "Create App"**
6. **Go to**: "Incoming Webhooks"
7. **Activate**: Toggle "Incoming Webhooks" to ON
8. **Click**: "Add New Webhook to Workspace"
9. **Select Channel**: Choose one of your 3 channels
10. **Click**: "Allow"
11. **Copy**: Webhook URL (looks like: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX`)

**Save all 3 webhook URLs** - you'll need them in Task 2

---

## 📋 TASK 2: Update AlertManager Config (10 min)

### Step 2a: View Current Config

```bash
cat alertmanager/config.yml
```

### Step 2b: Replace Webhook URLs

Edit the file with your webhook URLs:

```bash
nano alertmanager/config.yml
```

**Or use sed to replace** (replace with your actual URLs):

```bash
# For #charter-security channel
sed -i 's|https://hooks.slack.com/services/YOUR_SECURITY_WEBHOOK_HERE|https://hooks.slack.com/services/T123456/B123456/XXXXXXXX|g' alertmanager/config.yml

# For #charter-sre channel
sed -i 's|https://hooks.slack.com/services/YOUR_SRE_WEBHOOK_HERE|https://hooks.slack.com/services/T123456/B789012/YYYYYYYY|g' alertmanager/config.yml

# For #charter-monitoring channel
sed -i 's|https://hooks.slack.com/services/YOUR_WEBHOOK_URL_HERE|https://hooks.slack.com/services/T123456/B345678/ZZZZZZZZ|g' alertmanager/config.yml

# For PagerDuty (optional)
sed -i 's|YOUR_PAGERDUTY_KEY_HERE|your_actual_pagerduty_service_key|g' alertmanager/config.yml
```

### Step 2c: Verify Updates

```bash
# Show config to verify changes
grep -n "api_url" alertmanager/config.yml

# Should show your actual webhook URLs, not placeholders
```

### Step 2d: Validate YAML Syntax

```bash
# Test YAML validity
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml')); print('✅ Config is valid')"
```

**Expected Output**:
```
✅ Config is valid
```

---

## 🚀 TASK 3: Deploy Configuration (5 min)

### Step 3a: Determine AlertManager Location

```bash
# Check if AlertManager is running
ps aux | grep alertmanager | grep -v grep

# Common locations:
# /etc/alertmanager/config.yml (systemd/Linux)
# /opt/alertmanager/config.yml (manual install)
# Docker container (see Step 3d)
```

### Step 3b: Copy Config to AlertManager (Choose one)

**For Linux/Systemd Installation**:
```bash
# Copy config
sudo cp alertmanager/config.yml /etc/alertmanager/config.yml

# Verify copy
sudo ls -lh /etc/alertmanager/config.yml

# Expected output:
# -rw-r--r-- 1 root root 4.7K /etc/alertmanager/config.yml
```

**For Manual/Local Installation**:
```bash
# Copy config to local AlertManager directory
cp alertmanager/config.yml ~/.alertmanager/config.yml
# Or
cp alertmanager/config.yml ./alertmanager/config.yml
```

**For Docker Container**:
```bash
# Find container ID
docker ps | grep alertmanager

# Copy config to container
docker cp alertmanager/config.yml CONTAINER_ID:/etc/alertmanager/config.yml
```

### Step 3c: Reload AlertManager (No Downtime)

```bash
# Via HTTP API (recommended - no downtime)
curl -X POST http://localhost:9093/-/reload

# Expected: HTTP 200 with empty response

# Alternative: Via systemd
sudo systemctl reload alertmanager

# Alternative: Via signal
sudo kill -HUP $(pgrep -f alertmanager)

# Alternative: Via Docker
docker kill -s HUP CONTAINER_ID
```

### Step 3d: Verify Reload Success

```bash
# Check AlertManager logs for errors
tail -20 /var/log/alertmanager/alertmanager.log

# Should NOT show errors like:
# - "config is invalid"
# - "failed to parse"
# - "No such file"

# If no errors, reload succeeded ✅
```

---

## 🧪 TASK 4: Test Routing (5 min)

### Step 4a: Send Test Alert

```bash
# Create test alert JSON
cat > test_alert.json << 'EOF'
[{
  "labels": {
    "alertname": "TestAlert",
    "severity": "critical"
  },
  "annotations": {
    "summary": "This is a test alert from AlertManager",
    "description": "If you see this in #charter-security on Slack, routing works!"
  },
  "generatorURL": "http://localhost:9090/test"
}]
EOF

# Send test alert to AlertManager
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d @test_alert.json

# Alternative: Direct JSON
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "critical"
    },
    "annotations": {
      "summary": "Test alert - check #charter-security Slack channel"
    }
  }]'
```

### Step 4b: Check Slack Channels

Look for test alert in:
- **#charter-security** ← Critical severity alert should appear here
- **#charter-sre** ← Performance warnings appear here
- **#charter-monitoring** ← Informational alerts appear here

**Expected**:
- ✅ Test alert appears in #charter-security
- ✅ Alert shows severity, summary, description
- ✅ Alert appears within 5 seconds

### Step 4c: Check AlertManager UI

Open in browser: `http://localhost:9093`

- **Status** tab: Should show no errors
- **Alerts** tab: Should show your test alert
- **Receivers** tab: Should show 5 receivers configured

---

## ✅ TASK 5: Verify Setup (5 min)

### Step 5a: Check AlertManager Status

```bash
# Health check
curl -s http://localhost:9093/-/healthy
# Expected: OK

# Check receivers are loaded
curl -s http://localhost:9093/api/v1/receivers | python3 -m json.tool | head -20

# Should show receiver names:
# - default
# - critical-security
# - security-warnings
# - sre-warnings
# - info-alerts
```

### Step 5b: Check Configuration Load

```bash
# View AlertManager config status
curl -s http://localhost:9093/api/v1/status | python3 -m json.tool

# Should show:
# "status": "success"
# "data": {...config info...}
```

### Step 5c: Verify Alert Rules in Prometheus

```bash
# Check Prometheus has rules loaded
curl -s http://localhost:9090/api/v1/rules | python3 -m json.tool | grep -c "alert"

# Should show: 11 (or higher if other rules exist)

# Check specific rule
curl -s http://localhost:9090/api/v1/rules | python3 -m json.tool | grep -A 3 "CriticalViolationDetected"
```

### Step 5d: Run Verification Script

```bash
# Run comprehensive health check
bash scripts/verify-observability.sh

# Expected output:
# ✅ Prometheus running
# ✅ Alert rules loaded
# ✅ AlertManager configured
# ✅ Slack webhooks responsive
```

---

## 🔧 TROUBLESHOOTING

### Issue: "Connection refused" on localhost:9093

**Solution**: Start AlertManager first

```bash
# Check if running
ps aux | grep alertmanager

# If not running, start it:
alertmanager --config.file=alertmanager/config.yml

# Or via Docker:
docker run -d -p 9093:9093 \
  -v $(pwd)/alertmanager/config.yml:/etc/alertmanager/config.yml \
  -v alertmanager_data:/alertmanager \
  prom/alertmanager
```

### Issue: Reload returns error "403"

**Solution**: AlertManager needs admin API enabled

```bash
# Restart with admin API enabled
alertmanager --config.file=alertmanager/config.yml --web.enable-admin-api

# Or check if already enabled in systemd unit file
cat /etc/systemd/system/alertmanager.service | grep web.enable-admin-api
```

### Issue: Slack webhooks not working

**Solution**: Test webhook directly

```bash
# Test webhook URL directly
curl -X POST 'https://hooks.slack.com/services/YOUR_URL' \
  -H 'Content-Type: application/json' \
  -d '{"text": "Test message"}'

# Should see: "1" (success)
# If error, webhook URL is invalid
```

### Issue: Config file not found

**Solution**: Check AlertManager config location

```bash
# Find where config is expected
grep -r "config.file" /etc/systemd/system/

# Check default locations
ls -lh /etc/alertmanager/config.yml
ls -lh /opt/alertmanager/config.yml

# Find the correct location and copy file there
```

### Issue: YAML syntax error

**Solution**: Validate and fix

```bash
# Show errors
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml'))"

# Check specific line numbers for errors
cat -n alertmanager/config.yml | grep -A 2 -B 2 "ERROR_LINE"

# Common issues:
# - Missing colons after keys
# - Incorrect indentation (use spaces, not tabs)
# - Unclosed quotes in strings
```

---

## 📊 SUCCESS CHECKLIST

- [ ] Slack channels created (3 channels)
- [ ] Webhook URLs obtained (3 URLs)
- [ ] alertmanager/config.yml updated with webhook URLs
- [ ] YAML syntax validated
- [ ] Config deployed to AlertManager
- [ ] AlertManager reloaded successfully
- [ ] Test alert sent
- [ ] Slack notification received
- [ ] AlertManager UI shows 5 receivers
- [ ] Prometheus shows 11 alert rules loaded

---

## 🎯 SUMMARY

**Stage 2 Complete When**:
- ✅ 3 Slack channels created
- ✅ 3 webhook URLs configured in AlertManager
- ✅ AlertManager reloaded
- ✅ Test alert successfully routed to Slack
- ✅ All 5 receivers visible in AlertManager UI

**Next Step**: Proceed to Stage 3 (Grafana Dashboards)

---

## ⏱️ TIME TRACKING

| Task | Time | Status |
|------|------|--------|
| Task 1: Slack webhooks | 5 min | ⏳ |
| Task 2: Update config | 10 min | ⏳ |
| Task 3: Deploy | 5 min | ⏳ |
| Task 4: Test | 5 min | ⏳ |
| Task 5: Verify | 5 min | ⏳ |
| **TOTAL** | **30 min** | ⏳ |

---

## 🚀 BEGIN NOW

**Step 1**: Start Task 1 (Create Slack Webhooks)  
**Step 2**: Follow each task sequentially  
**Step 3**: Verify at the end  
**Step 4**: Proceed to Stage 3

---

**Document**: WEST_0105_2_STAGE2_DEPLOYMENT_EXECUTION.md  
**Status**: ACTIVE EXECUTION GUIDE  
**Date**: 2026-01-11
