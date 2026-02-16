# 🎯 WEST-0105 Quick Reference Card

**Status**: Phase 1 ✅ Complete | Phase 2 ⏳ Ready to Start  
**Date**: 2026-01-11 | **Effort**: 4-5 hours for Phase 2

---

## 📊 What's Ready?

### ✅ Phase 1: Prometheus Exporter (COMPLETE)
- **File**: `src/westworld/prometheus_metrics.py` (320 lines)
- **Status**: Production-ready, tested (20/20 tests passing)
- **Metrics**: 15 total
  - 6 Counters (violations, attempts, events, etc.)
  - 5 Histograms (latency measurements)
  - 4 Gauges (current state)

### ⏳ Phase 2: Dashboards & Alerts (READY TO START)
- **Files Prepared**: 5 configuration files + 2 documentation files
- **Dashboards**: 2 (14 panels total)
- **Alerts**: 11 rules configured
- **Notifications**: Slack + PagerDuty
- **Implementation**: 28-step checklist ready
- **Time Estimate**: 4-5 hours

---

## 🚀 Quick Start for Phase 2

### Prerequisites (5 min)
```bash
# Verify services are running
curl http://prometheus:9090 -I        # Should return 200
curl http://alertmanager:9093 -I      # Should return 200
curl http://grafana:3000 -I           # Should return 200
curl http://charter-api:8000/metrics  # Should show metrics
```

### Deploy in 4 Steps (4-5 hours total)

#### 1. Deploy Prometheus Alerts (1 hour)
```bash
# Copy alert rules file
cp prometheus/alerts/charter-alerts.yml /etc/prometheus/rules/

# Update prometheus.yml to load rules
# Add under 'rule_files:':
#   - '/etc/prometheus/rules/charter-alerts.yml'

# Reload Prometheus
curl -X POST http://prometheus:9090/-/reload

# Verify alerts loaded
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[0].rules | length'
# Should show: 11
```

#### 2. Deploy AlertManager Config (30 min)
```bash
# Set Slack webhook
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/YOUR/WEBHOOK'

# Copy config
cp alertmanager/config.yml /etc/alertmanager/

# Reload AlertManager
curl -X POST http://alertmanager:9093/-/reload

# Test Slack integration
# Go to http://alertmanager:9093 and send test notification
```

#### 3. Create Grafana Dashboards (2 hours)
**Option A: Manual (Recommended for learning)**
- Follow 28-step checklist in `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md`
- Create 2 dashboards with 14 panels total
- Time: ~2 hours

**Option B: Import JSON (Faster)**
```bash
# When JSON dashboard files are available:
curl -X POST http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/violations-threats.json
  
curl -X POST http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/enforcement-performance.json
```

#### 4. Test Everything (1-1.5 hours)
```bash
# Generate test violation
curl -X POST http://charter-api:8000/test/violation \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "CRITICAL",
    "violation_type": "data_extraction",
    "node_or_service": "test_node_123"
  }'

# Wait 1-2 minutes, then:

# Check Prometheus
# http://prometheus:9090/alerts → Should see CriticalViolationDetected firing

# Check Grafana
# http://grafana:3000 → Dashboards should show the violation

# Check Slack
# #charter-security → Should have alert notification
```

---

## 📈 Dashboards Overview

### Dashboard 1: Violations & Threats
| Panel | Query | Purpose |
|-------|-------|---------|
| Timeline | `rate(violations_total[5m])` | Violation rate |
| Top Nodes | `topk(10, violations_total)` | Worst offenders |
| Types | `violations_total` grouped | Distribution |
| Forbidden | `forbidden_metric_attempts_total` | Reconnaissance |
| Investigations | `violations_under_investigation` | Current workload |
| Override Status | `emergency_override_active_count` | Critical status |
| Recent Events | Latest violations | Event details |

### Dashboard 2: Enforcement Performance
| Panel | Query | Purpose |
|-------|-------|---------|
| Validation SLA | `p50/p95/p99` latency | Performance |
| Policy Loads | Frequency + Duration | Health indicator |
| Notification SLA | `p99` committee latency | Response time |
| E2E Response | `violation_report_latency` | End-to-end time |
| Revocation Rate | Rate of revocations | Activity |
| Policy Freshness | Hours since last load | Staleness |
| Investigation Rate | Rate of initiations | Activity level |

---

## 🚨 Alert Rules at a Glance

| Alert | Severity | Trigger | Action |
|-------|----------|---------|--------|
| CriticalViolation | 🔴 CRITICAL | Any CRITICAL violation | Page on-call |
| ForbiddenSpike | 🟡 WARNING | > 10 attempts/sec | Investigate |
| ValidationLatency | 🟡 WARNING | p99 > 20µs | Check infra |
| PolicyLoadFailure | 🔴 CRITICAL | No load > 24h | Manual reload |
| EmergencyOverride | 🔴 CRITICAL | Active > 30m | Disable |
| CommitteeOverloaded | 🟡 WARNING | > 10 investigations | Add resources |
| NotificationLatency | 🟡 WARNING | p99 > 1000ms | Optimize |
| RevocationLatency | 🟡 WARNING | p99 > 5000ms | Check service |
| PolicyFrequency | 🟡 WARNING | > 10 reloads/hr | Investigate |
| UnusualRevocation | 🟡 WARNING | > 1/minute | Verify |
| HighInvestigationRate | ℹ️ INFO | > 5/sec | Monitor |

---

## 🔌 Integration Points

```
Charter App
    ↓ (exports metrics to /metrics)
Prometheus (scrapes every 15s)
    ↓ (evaluates rules every 30s)
Alert Rules (11 rules)
    ↓ (fires alerts)
AlertManager (routes by severity)
    ├→ Slack #charter-security (critical)
    ├→ Slack #charter-sre (warnings)
    ├→ PagerDuty (critical)
    └→ Email (compliance)
    ↓ (all metrics available to)
Grafana Dashboards (refresh every 30s)
    ├→ Violations & Threats
    └→ Enforcement Performance
```

---

## 📚 Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/westworld/prometheus_metrics.py` | Metrics module | 320 |
| `tests/test_charter_prometheus.py` | 20 comprehensive tests | 360 |
| `prometheus/alerts/charter-alerts.yml` | 11 alert rules | 220 |
| `alertmanager/config.yml` | Notification routing | 180 |
| `prometheus/prometheus.yml` | Scrape config | 230 |
| `docs/PROMETHEUS_METRICS.md` | Metric reference | 550 |
| `WEST_0105_2_DASHBOARDS_PLAN.md` | Design doc | 380 |
| `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md` | 28-step guide | 550 |
| `scripts/deploy-observability.sh` | Deploy script | 300 |

---

## ✅ Verification Checklist

After deployment:
- [ ] Prometheus loads alert rules (check `/alerts` page)
- [ ] AlertManager loads config (check UI)
- [ ] Grafana datasource connects (test in datasource UI)
- [ ] Dashboards display data (not just "No data")
- [ ] Test alert fires and sends to Slack
- [ ] SLA thresholds are visible on dashboards

---

## 🆘 Troubleshooting

### No metrics showing in Prometheus
```bash
# Check if Charter app is exporting metrics
curl http://charter-api:8000/metrics | grep westworld_charter

# Check Prometheus scrape status
# Go to http://prometheus:9090/targets
# Should see 'westworld-charter' with status "UP"
```

### Alerts not firing
```bash
# Check alert rules loaded
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[].rules[]'

# Manually trigger a violation and wait 2 minutes
# Check Prometheus UI under /alerts
```

### Slack notifications not arriving
```bash
# Check AlertManager config syntax
yamllint alertmanager/config.yml

# Test AlertManager notification
curl -X POST http://alertmanager:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels": {"alertname": "Test"}}]'
```

### Dashboard panels show "No data"
```bash
# Check Grafana datasource
# Go to Configuration → Data Sources
# Click Prometheus-Charter → Test Data Source

# Check query in panel
# Edit panel, run query manually in Prometheus
```

---

## 📞 Quick Reference URLs

```
Prometheus:          http://localhost:9090
  - Targets:         http://localhost:9090/targets
  - Alerts:          http://localhost:9090/alerts
  - Query:           http://localhost:9090/graph

AlertManager:        http://localhost:9093
  - Alerts:          http://localhost:9093/#/alerts
  - Silences:        http://localhost:9093/#/silences

Grafana:             http://localhost:3000
  - Datasources:     http://localhost:3000/datasources
  - Dashboards:      http://localhost:3000/dashboards
  - Alerts:          http://localhost:3000/alerting/list

Charter API Metrics: http://localhost:8000/metrics
```

---

## 🎓 Useful Queries for Prometheus

```
# Violations in last hour
rate(westworld_charter_violations_total[1h])

# Top 5 violating nodes
topk(5, sum by (node_or_service) (rate(westworld_charter_violations_total[5m])))

# Validation latency p99 (in microseconds)
histogram_quantile(0.99, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) / 1000

# Are we under SLA?
histogram_quantile(0.99, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) < 20000000

# Forbidden metric attempts (last 5 min)
rate(westworld_charter_forbidden_metric_attempts_total[5m])

# Committee workload
sum(westworld_charter_violations_under_investigation)

# Is policy stale?
(time() - westworld_charter_policy_last_load_timestamp) / 3600 > 24
```

---

## 🎯 Success Criteria

✅ **Phase 2 is complete when:**
- [ ] 2 Grafana dashboards created and displaying data
- [ ] 11 alert rules loaded and evaluated by Prometheus
- [ ] AlertManager configured and routing alerts
- [ ] Test alert fires and reaches Slack
- [ ] All 15 metrics visible in Prometheus
- [ ] SLA thresholds visible on dashboards
- [ ] Documentation complete
- [ ] Team trained on usage

---

## 🚀 Next After Phase 2

**WEST-0105-3: MAPE-K Integration** (6-8 hours)
- Integrate metrics into MAPE-K Monitor phase
- Process violations in Analyze phase
- Map severity to actions in Plan phase
- Record healing actions in Execute phase

**WEST-0105-4: End-to-End Tests** (3-4 hours)
- E2E test scenarios
- Load testing (1000 violations/sec)
- Integration tests

---

## 📝 Phase 2 Timeline

```
Time    Activity                        Duration    Status
─────────────────────────────────────────────────────────────
0-30m   Prerequisites & validation     30 min      ✓ Ready
30m-1h  Deploy Prometheus alerts       30 min      ⏳
1-1.5h  Deploy AlertManager            30 min      ⏳
1.5-3h  Create Grafana dashboards      1.5 hours   ⏳
3-4.5h  Test & validate everything     1.5 hours   ⏳
─────────────────────────────────────────────────────────────
TOTAL   Complete WEST-0105-2           4-5 hours   ⏳ Ready
```

---

**Ready to start? Follow the 28-step checklist in `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md` 🚀**

*Generated: 2026-01-11 | Last Updated: Session WEST-0105 | Version: 1.0*
