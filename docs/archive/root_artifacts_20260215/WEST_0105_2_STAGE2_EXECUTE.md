# 🚀 WEST-0105-2 STAGE 2: Deploy AlertManager Config (30 min)

**Status**: ⏳ READY TO DEPLOY  
**Estimated Time**: 30 minutes  
**Complexity**: Medium (configure webhooks)  
**Prerequisites**: ✅ Stage 1 Complete  

---

## 📋 Overview

Stage 2 deploys the AlertManager configuration which:
- Routes alerts to 4 notification channels
- Integrates with 3 Slack channels (security, SRE, monitoring)
- Integrates with PagerDuty (critical/security incidents)
- Handles alert grouping and inhibition

---

## 🎯 Stage 2 Checklist

### ✅ Prerequisites
- [x] Stage 1 complete (Prometheus alert rules deployed)
- [x] AlertManager service running on port 9093
- [x] alertmanager/config.yml exists (4.7K)
- [x] Slack API workspace access
- [x] PagerDuty integration access (optional, can use Slack-only)

---

## 📋 Tasks

### Task 1: Prepare Slack Webhooks (5 min)

AlertManager needs 3 Slack channels for notifications:

#### Channel 1: #charter-security (Critical & Security Alerts)
```
Purpose: Critical violations, security threats, emergency overrides
Integration Webhook URL: https://hooks.slack.com/services/T.../B.../XXXXXXXXXX
```

#### Channel 2: #charter-sre (Operational Alerts)
```
Purpose: Performance warnings, SLA violations, load issues
Integration Webhook URL: https://hooks.slack.com/services/T.../B.../YYYYYYYYYY
```

#### Channel 3: #charter-monitoring (Info & Monitoring)
```
Purpose: Informational alerts, investigation rates, frequency anomalies
Integration Webhook URL: https://hooks.slack.com/services/T.../B.../ZZZZZZZZZZ
```

**To create a Slack webhook**:

1. Go to Slack workspace settings: https://api.slack.com/apps
2. Create New App → From scratch
3. Name: "Prometheus AlertManager"
4. Select workspace
5. Go to "Incoming Webhooks" → Activate
6. "Add New Webhook to Workspace"
7. Select channel (e.g., #charter-security)
8. Copy Webhook URL (starts with https://hooks.slack.com/services/...)
9. Repeat for other 2 channels

---

### Task 2: Prepare PagerDuty Integration (3 min)

PagerDuty handles critical incident escalation (optional).

**To create PagerDuty integration**:

1. Log in to PagerDuty
2. Services → New Service
3. Name: "Prometheus Alerts"
4. Alert behavior: Create alerts and incidents
5. Response: Use default
6. Integrations → Add integration
7. Choose "Prometheus"
8. Copy Integration Key / Service Key
9. Save (looks like: a1b2c3d4e5f6g7h8)

---

### Task 3: Update AlertManager Config (10 min)

Edit `alertmanager/config.yml` with your webhook URLs.

#### Current template:
```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'SLACK_API_URL_HERE'  # Optional: for advanced Slack features

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#charter-monitoring'
        api_url: 'https://hooks.slack.com/services/YOUR_WEBHOOK_URL_HERE'

  - name: 'critical-security'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY_HERE'
    slack_configs:
      - channel: '#charter-security'
        api_url: 'https://hooks.slack.com/services/YOUR_SECURITY_WEBHOOK_HERE'

  - name: 'security-warnings'
    slack_configs:
      - channel: '#charter-security'
        api_url: 'https://hooks.slack.com/services/YOUR_SECURITY_WEBHOOK_HERE'

  - name: 'sre-warnings'
    slack_configs:
      - channel: '#charter-sre'
        api_url: 'https://hooks.slack.com/services/YOUR_SRE_WEBHOOK_HERE'

  - name: 'info-alerts'
    slack_configs:
      - channel: '#charter-monitoring'
        api_url: 'https://hooks.slack.com/services/YOUR_WEBHOOK_URL_HERE'
```

#### Edit with your values:
```bash
# Replace placeholders (use sed or your editor)
sed -i 's|https://hooks.slack.com/services/YOUR_WEBHOOK_URL_HERE|https://hooks.slack.com/services/YOUR_ACTUAL_WEBHOOK|g' alertmanager/config.yml
sed -i 's|YOUR_PAGERDUTY_KEY_HERE|your_actual_pagerduty_key|g' alertmanager/config.yml

# Verify changes
grep -E "(slack_configs|pagerduty|api_url)" alertmanager/config.yml
```

---

### Task 4: Validate AlertManager Config (3 min)

```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml')); print('✅ Config valid')"

# Validate with amtool (if installed)
amtool config routes -f alertmanager/config.yml

# Show configuration summary
python3 << 'PY'
import yaml
with open('alertmanager/config.yml') as f:
    cfg = yaml.safe_load(f)
    print("✅ AlertManager Configuration Summary:")
    print(f"   Receivers: {len(cfg.get('receivers', []))}")
    for rcv in cfg.get('receivers', []):
        print(f"     - {rcv['name']}")
PY
```

---

### Task 5: Deploy AlertManager Config (5 min)

```bash
# For typical Linux installation
sudo cp alertmanager/config.yml /etc/alertmanager/config.yml

# For development/local setup
cp alertmanager/config.yml ~/.alertmanager/config.yml

# For Docker container
docker cp alertmanager/config.yml alertmanager_container:/etc/alertmanager/config.yml
```

---

### Task 6: Reload AlertManager Configuration (2 min)

```bash
# Via systemd
sudo systemctl reload alertmanager

# Via Docker
docker kill -s HUP alertmanager_container

# Via HTTP API (if available)
curl -X POST http://localhost:9093/-/reload

# Manual restart (if needed)
sudo systemctl restart alertmanager
```

---

### Task 7: Verify AlertManager Loaded Config (2 min)

```bash
# Check AlertManager UI
# Browse to: http://localhost:9093

# Or check API
curl -s http://localhost:9093/api/v1/receivers | python3 -m json.tool

# Check logs for errors
tail -20 /var/log/alertmanager/alertmanager.log
# Should NOT show errors about config
```

---

## 🧪 Task 8: Test Alert Routing (Optional, 5 min)

Create a test alert to verify routing works:

```bash
# Send test alert via AlertManager API
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Test alert - should route to #charter-security"
      },
      "generatorURL": "http://localhost:9090/test"
    }
  ]'

# Or via Prometheus directly (if you have test metrics)
# Trigger a metric that causes an alert to fire
```

**Expected Result**:
- ✅ Slack notification appears in #charter-security
- ✅ PagerDuty incident created (if configured)

---

## ✅ Success Criteria

- [x] AlertManager config updated with webhook URLs
- [x] YAML syntax validated
- [x] Config deployed to AlertManager
- [x] AlertManager reloaded successfully
- [x] AlertManager UI shows 5 receivers
- [x] Test alert routes correctly

---

## 🔧 Troubleshooting

### Issue: AlertManager won't reload

```bash
# Solution 1: Validate YAML
python3 -c "import yaml; yaml.safe_load(open('alertmanager/config.yml')); print('✅')"

# Solution 2: Check logs
tail -50 /var/log/alertmanager/alertmanager.log

# Solution 3: Restart service
sudo systemctl restart alertmanager
```

### Issue: Slack webhooks not working

```bash
# Solution 1: Test webhook directly
curl -X POST 'https://hooks.slack.com/services/YOUR_URL' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Test message from AlertManager"
  }'

# Solution 2: Check AlertManager logs
tail -30 /var/log/alertmanager/alertmanager.log | grep -i slack

# Solution 3: Verify webhook URL format
# Should be: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX
```

### Issue: PagerDuty not receiving alerts

```bash
# Solution: Verify service key format
# Should be alphanumeric (32 chars): a1b2c3d4e5f6g7h8...

# Check AlertManager logs
tail -30 /var/log/alertmanager/alertmanager.log | grep -i pagerduty
```

---

## 📊 Configuration Reference

### Route Configuration

Alerts are routed based on severity labels:

```
Critical Alerts (severity: critical)
  → #charter-security (Slack) + PagerDuty
  
Warning Alerts (severity: warning)
  → #charter-sre OR #charter-security (depending on type)

Info Alerts (severity: info)
  → #charter-monitoring (Slack)
```

### Receivers Summary

| Receiver | Channels | Conditions |
|----------|----------|-----------|
| critical-security | Slack #charter-security + PagerDuty | severity: critical |
| security-warnings | Slack #charter-security | type: security |
| sre-warnings | Slack #charter-sre | type: sre/performance |
| info-alerts | Slack #charter-monitoring | severity: info |
| default | Slack #charter-monitoring | catch-all |

---

## ⏱️ Time Summary

| Task | Status | Time |
|------|--------|------|
| Prepare Slack webhooks | ⏳ | 5 min |
| Prepare PagerDuty (opt) | ⏳ | 3 min |
| Update config | ⏳ | 10 min |
| Validate config | ⏳ | 3 min |
| Deploy config | ⏳ | 5 min |
| Reload AlertManager | ⏳ | 2 min |
| Verify deployment | ⏳ | 2 min |
| **TOTAL Stage 2** | **⏳** | **30 min** |

---

## 🚀 Next: Stage 3

Once Stage 2 is complete ✅, proceed to:

**📋 WEST-0105-2 Stage 3**: Create Grafana Dashboards

This stage will:
1. Create Dashboard 1: Violations & Threats (7 panels)
2. Create Dashboard 2: Enforcement Performance (7 panels)
3. Configure dashboard alerting
4. Set SLA thresholds

**Estimated Time**: 2-3 hours

---

**Document**: WEST_0105_2_STAGE2_EXECUTE.md  
**Date**: 2026-01-11  
**Status**: READY TO EXECUTE
