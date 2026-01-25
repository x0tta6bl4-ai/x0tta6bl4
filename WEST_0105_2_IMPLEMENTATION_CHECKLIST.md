# WEST-0105-2 Implementation Checklist

**Status**: ⏳ READY TO IMPLEMENT  
**Effort**: 4-5 hours  
**Priority**: HIGH (unblocks WEST-0105-3 & real-time observability)

---

## ✅ Phase 2A: Grafana Setup & Dashboard 1 (Violations & Threats)

### Step 1: Grafana Prerequisites (30 minutes)
- [ ] **1.1** Verify Grafana is running (`http://grafana:3000`)
- [ ] **1.2** Log in with default credentials (admin/admin)
- [ ] **1.3** Change default admin password
- [ ] **1.4** Add Prometheus datasource:
  - [ ] Name: `Prometheus-Charter`
  - [ ] URL: `http://prometheus:9090`
  - [ ] Scrape interval: `15s`
  - [ ] Query timeout: `30s`
  - [ ] Click "Save & Test" → Expect: "Data source is working"
- [ ] **1.5** Create folder: `Charter Observability`
  - [ ] Access: Admin
  - [ ] Description: "Anti-Delos Charter observability dashboards"
- [ ] **1.6** Create team: `charter-security`
  - [ ] Members: [List team members]

### Step 2: Dashboard 1 - Create Structure (1 hour)
- [ ] **2.1** Create new dashboard in Grafana
- [ ] **2.2** Name: `Violations & Threats`
- [ ] **2.3** Folder: `Charter Observability`
- [ ] **2.4** Tags: `charter`, `violations`, `security`
- [ ] **2.5** Set refresh interval: `30s`
- [ ] **2.6** Set time range: `Last 24 hours`

### Step 3: Dashboard 1 - Add Panel 1 (Violations Timeline)
- [ ] **3.1** Add new panel → Graph type
- [ ] **3.2** Panel title: `Violations Timeline (Last 24h)`
- [ ] **3.3** Add query A:
  ```
  sum by(severity) (rate(westworld_charter_violations_total[5m]))
  ```
- [ ] **3.4** Legend: `{{ severity }}`
- [ ] **3.5** Colors:
  - [ ] CRITICAL → Red (#FF0000)
  - [ ] SUSPENSION → Orange (#FF9900)
  - [ ] BAN_1YEAR → Orange (#FF6600)
  - [ ] WARNING → Yellow (#FFD700)
- [ ] **3.6** Y-axis label: `Violations/sec`
- [ ] **3.7** Add threshold line at y=0
- [ ] **3.8** Size: 100% width, 300px height
- [ ] **3.9** Position: Row 1, Full width

### Step 4: Dashboard 1 - Add Panel 2 (Top Nodes)
- [ ] **4.1** Add new panel → Heatmap type
- [ ] **4.2** Panel title: `Top 10 Violating Nodes (Heatmap)`
- [ ] **4.3** Query:
  ```
  topk(10, sum by(node_or_service, violation_type) (westworld_charter_violations_total))
  ```
- [ ] **4.4** X-axis: `node_or_service`
- [ ] **4.5** Y-axis: `violation_type`
- [ ] **4.6** Color scale: Green (0) → Red (100+)
- [ ] **4.7** Size: 50% width, 250px height
- [ ] **4.8** Position: Row 2, Left

### Step 5: Dashboard 1 - Add Panel 3 (Violation Types)
- [ ] **5.1** Add new panel → Pie chart type
- [ ] **5.2** Panel title: `Violation Types Distribution`
- [ ] **5.3** Query:
  ```
  sum by(violation_type) (westworld_charter_violations_total)
  ```
- [ ] **5.4** Sort by: Value (descending)
- [ ] **5.5** Show legend: Yes
- [ ] **5.6** Size: 50% width, 250px height
- [ ] **5.7** Position: Row 2, Right

### Step 6: Dashboard 1 - Add Panel 4 (Forbidden Metric Attempts)
- [ ] **6.1** Add new panel → Heatmap type
- [ ] **6.2** Panel title: `Forbidden Metric Access Attempts (Last 1h)`
- [ ] **6.3** Query:
  ```
  rate(westworld_charter_forbidden_metric_attempts_total[1m])
  ```
- [ ] **6.4** X-axis: `metric_name`
- [ ] **6.5** Y-axis: `node_or_service`
- [ ] **6.6** Color scale: Green (0) → Red (100+)
- [ ] **6.7** Add threshold: Red if > 10 attempts/min
- [ ] **6.8** Size: 100% width, 250px height
- [ ] **6.9** Position: Row 3, Full width

### Step 7: Dashboard 1 - Add Panel 5 (Investigations Gauge)
- [ ] **7.1** Add new panel → Gauge type
- [ ] **7.2** Panel title: `Violations Under Investigation`
- [ ] **7.3** Query:
  ```
  sum by(severity) (westworld_charter_violations_under_investigation)
  ```
- [ ] **7.4** Thresholds:
  - [ ] Green: 0-2
  - [ ] Orange: 3-5
  - [ ] Red: 6+
- [ ] **7.5** Unit: `short` (no unit)
- [ ] **7.6** Size: 33% width, 250px height
- [ ] **7.7** Position: Row 4, Column 1

### Step 8: Dashboard 1 - Add Panel 6 (Emergency Status)
- [ ] **8.1** Add new panel → Stat type
- [ ] **8.2** Panel title: `🚨 Emergency Override Status`
- [ ] **8.3** Query:
  ```
  westworld_charter_emergency_override_active_count
  ```
- [ ] **8.4** Thresholds:
  - [ ] 0 → Green ✓
  - [ ] 1 → Orange ⚠️
  - [ ] 2+ → Red 🚨
- [ ] **8.5** Size: 33% width, 250px height
- [ ] **8.6** Position: Row 4, Column 2

### Step 9: Dashboard 1 - Add Panel 7 (Events Table)
- [ ] **9.1** Add new panel → Table type
- [ ] **9.2** Panel title: `Recent Violations`
- [ ] **9.3** Use Prometheus: "Table" format
- [ ] **9.4** Query:
  ```
  topk(20, increase(westworld_charter_violations_total[1h]))
  ```
- [ ] **9.5** Columns: severity, violation_type, node_or_service, count
- [ ] **9.6** Sort by: count (descending)
- [ ] **9.7** Size: 33% width, 250px height
- [ ] **9.8** Position: Row 4, Column 3
- [ ] **9.9** Save dashboard

---

## ✅ Phase 2B: Grafana Dashboard 2 (Enforcement Performance)

### Step 10: Dashboard 2 - Create Structure (30 minutes)
- [ ] **10.1** Create new dashboard in Grafana
- [ ] **10.2** Name: `Enforcement Performance`
- [ ] **10.3** Folder: `Charter Observability`
- [ ] **10.4** Tags: `charter`, `performance`, `sla`
- [ ] **10.5** Set refresh interval: `30s`
- [ ] **10.6** Set time range: `Last 24 hours`

### Step 11: Dashboard 2 - Add Panel 1 (Validation Latency SLA)
- [ ] **11.1** Add new panel → Graph type
- [ ] **11.2** Panel title: `Metric Validation Latency (p50/p95/p99)`
- [ ] **11.3** Add query A (p50):
  ```
  histogram_quantile(0.50, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) / 1000
  ```
  Legend: `p50`
- [ ] **11.4** Add query B (p95):
  ```
  histogram_quantile(0.95, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) / 1000
  ```
  Legend: `p95`
- [ ] **11.5** Add query C (p99):
  ```
  histogram_quantile(0.99, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) / 1000
  ```
  Legend: `p99`
- [ ] **11.6** Y-axis label: `Latency (µs)`
- [ ] **11.7** Add SLA threshold line: 10µs (10000ns = 10µs)
- [ ] **11.8** Alert zone: Highlight if p99 > 20µs
- [ ] **11.9** Size: 100% width, 300px height
- [ ] **11.10** Position: Row 1, Full width

### Step 12: Dashboard 2 - Add Panel 2 (Policy Load Performance)
- [ ] **12.1** Add new panel → Graph type
- [ ] **12.2** Panel title: `Policy Load Duration & Frequency`
- [ ] **12.3** Add query A (frequency):
  ```
  rate(westworld_charter_policy_load_duration_ms_count[1h])
  ```
  Legend: `Reloads/hour`
  Y-axis: Left
- [ ] **12.4** Add query B (latency p99):
  ```
  histogram_quantile(0.99, rate(westworld_charter_policy_load_duration_ms_bucket[5m]))
  ```
  Legend: `p99 Duration (ms)`
  Y-axis: Right
- [ ] **12.5** Left Y-axis label: `Reloads/hour`
- [ ] **12.6** Right Y-axis label: `Duration (ms)`
- [ ] **12.7** Size: 50% width, 250px height
- [ ] **12.8** Position: Row 2, Left

### Step 13: Dashboard 2 - Add Panel 3 (Committee Notification SLA)
- [ ] **13.1** Add new panel → Gauge type
- [ ] **13.2** Panel title: `Committee Notification Latency (p99)`
- [ ] **13.3** Query:
  ```
  histogram_quantile(0.99, rate(westworld_charter_committee_notification_latency_ms_bucket[5m]))
  ```
- [ ] **13.4** Unit: `ms`
- [ ] **13.5** Thresholds:
  - [ ] Green: 0-500ms (SLA met)
  - [ ] Orange: 500-1000ms (warning)
  - [ ] Red: 1000+ ms (critical)
- [ ] **13.6** Size: 50% width, 250px height
- [ ] **13.7** Position: Row 2, Right

### Step 14: Dashboard 2 - Add Panel 4 (E2E Violation Response)
- [ ] **14.1** Add new panel → Graph type
- [ ] **14.2** Panel title: `E2E Violation Response Time (Detection → Committee)`
- [ ] **14.3** Query:
  ```
  histogram_quantile(0.99, rate(westworld_charter_violation_report_latency_ms_bucket[5m]))
  ```
- [ ] **14.4** Y-axis label: `Latency (ms)`
- [ ] **14.5** Add SLA threshold: 1000ms (1 second)
- [ ] **14.6** Size: 100% width, 250px height
- [ ] **14.7** Position: Row 3, Full width

### Step 15: Dashboard 2 - Add Panel 5 (Data Revocation)
- [ ] **15.1** Add new panel → Stat type
- [ ] **15.2** Panel title: `Data Revocation Status`
- [ ] **15.3** Query:
  ```
  rate(westworld_charter_data_revocation_events_total[1h])
  ```
- [ ] **15.4** Unit: `events/hour`
- [ ] **15.5** Size: 33% width, 200px height
- [ ] **15.6** Position: Row 4, Column 1

### Step 16: Dashboard 2 - Add Panel 6 (Policy Freshness)
- [ ] **16.1** Add new panel → Stat type
- [ ] **16.2** Panel title: `Policy Freshness`
- [ ] **16.3** Query:
  ```
  (time() - westworld_charter_policy_last_load_timestamp) / 3600
  ```
- [ ] **16.4** Unit: `hours`
- [ ] **16.5** Thresholds:
  - [ ] Green: 0-4 hours (fresh)
  - [ ] Orange: 4-24 hours (aging)
  - [ ] Red: 24+ hours (stale - ALERT!)
- [ ] **16.6** Size: 33% width, 200px height
- [ ] **16.7** Position: Row 4, Column 2

### Step 17: Dashboard 2 - Add Panel 7 (Investigation Rate)
- [ ] **17.1** Add new panel → Stat type
- [ ] **17.2** Panel title: `Investigation Initiation Rate`
- [ ] **17.3** Query:
  ```
  rate(westworld_charter_investigation_initiated_total[5m])
  ```
- [ ] **17.4** Unit: `investigations/sec`
- [ ] **17.5** Size: 33% width, 200px height
- [ ] **17.6** Position: Row 4, Column 3
- [ ] **17.7** Save dashboard

---

## ✅ Phase 2C: Prometheus Alert Rules

### Step 18: Deploy Alert Rules (1 hour)
- [ ] **18.1** Copy `prometheus/alerts/charter-alerts.yml` to Prometheus config directory
- [ ] **18.2** Validate YAML syntax: `yamllint prometheus/alerts/charter-alerts.yml`
- [ ] **18.3** Add alert rule file to `prometheus.yml`:
  ```
  rule_files:
    - '/etc/prometheus/alerts/charter-alerts.yml'
  ```
- [ ] **18.4** Reload Prometheus configuration:
  ```bash
  curl -X POST http://prometheus:9090/-/reload
  ```
- [ ] **18.5** Verify alert rules loaded:
  - [ ] Go to `http://prometheus:9090/alerts`
  - [ ] Should see 11 alert rules (all in green)
- [ ] **18.6** Verify alert state:
  - [ ] Some may show as "FIRING" (if conditions met)
  - [ ] Most should be "INACTIVE"

---

## ✅ Phase 2D: AlertManager Configuration

### Step 19: Deploy AlertManager (1 hour)
- [ ] **19.1** Copy `alertmanager/config.yml` to AlertManager config directory
- [ ] **19.2** Validate YAML syntax: `yamllint alertmanager/config.yml`
- [ ] **19.3** Set environment variables:
  ```bash
  export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
  export PAGERDUTY_SERVICE_KEY='your-pagerduty-service-key'
  ```
- [ ] **19.4** Reload AlertManager:
  ```bash
  curl -X POST http://alertmanager:9093/-/reload
  ```
- [ ] **19.5** Verify AlertManager started: `http://alertmanager:9093`
- [ ] **19.6** Test Slack integration:
  - [ ] Go to AlertManager UI
  - [ ] Trigger test alert
  - [ ] Verify message received in Slack #charter-monitoring

### Step 20: Setup Notification Channels (30 minutes)
- [ ] **20.1** Create Slack channels:
  - [ ] `#charter-monitoring` (all alerts)
  - [ ] `#charter-security` (security alerts + PagerDuty)
  - [ ] `#charter-sre` (infrastructure alerts)
- [ ] **20.2** Create Slack webhook for notifications:
  - [ ] Go to `https://api.slack.com/apps`
  - [ ] Select your app
  - [ ] Enable "Incoming Webhooks"
  - [ ] Create webhook for each channel
  - [ ] Copy webhook URLs
- [ ] **20.3** Setup PagerDuty integration (if using PagerDuty):
  - [ ] Create integration in PagerDuty
  - [ ] Get service key
  - [ ] Add to AlertManager config

---

## ✅ Phase 2E: Integration & Testing

### Step 21: Prometheus Scrape Configuration (30 minutes)
- [ ] **21.1** Copy `prometheus/prometheus.yml` to Prometheus config directory
- [ ] **21.2** Verify Charter app is running and exporting metrics:
  ```bash
  curl http://charter-api:8000/metrics
  ```
- [ ] **21.3** Add datasource to Prometheus `prometheus.yml`
- [ ] **21.4** Reload Prometheus
- [ ] **21.5** Verify metrics are being scraped:
  - [ ] Go to `http://prometheus:9090`
  - [ ] Graph tab
  - [ ] Type: `westworld_charter_violations_total`
  - [ ] Should see metric with data
- [ ] **21.6** Verify all 15 metrics are available:
  - [ ] 6 Counters (violations_total, forbidden_metric_attempts_total, etc.)
  - [ ] 5 Histograms (metric_validation_latency_ns, policy_load_duration_ms, etc.)
  - [ ] 4 Gauges (violations_under_investigation, audit_committee_size, etc.)

### Step 22: Dashboard Validation (1 hour)
- [ ] **22.1** Load Dashboard 1: `Violations & Threats`
  - [ ] All 7 panels load successfully
  - [ ] Violations timeline shows data
  - [ ] No errors in browser console
- [ ] **22.2** Load Dashboard 2: `Enforcement Performance`
  - [ ] All 7 panels load successfully
  - [ ] Latency charts show data
  - [ ] SLA thresholds are visible
  - [ ] No errors in browser console
- [ ] **22.3** Test dashboard interactivity:
  - [ ] Click on heatmap → Should drill down
  - [ ] Change time range → Charts should update
  - [ ] Refresh rate: Should be 30s (visible in top-right)
- [ ] **22.4** Test dashboard links:
  - [ ] Alert annotations contain dashboard URLs
  - [ ] Click links → Should navigate to correct dashboard

### Step 23: Alert Rule Testing (1 hour)
- [ ] **23.1** Trigger test CriticalViolationDetected:
  ```bash
  # In Charter app, generate a critical violation
  # Verify alert fires in Prometheus: http://prometheus:9090/alerts
  ```
- [ ] **23.2** Verify alert state transitions:
  - [ ] INACTIVE → FIRING → RESOLVED
- [ ] **23.3** Check Slack notifications:
  - [ ] Alert fires → Message in #charter-security
  - [ ] Message contains: severity, violation_type, node_or_service
  - [ ] Dashboard link is clickable
  - [ ] Alert resolves → Resolved message in Slack
- [ ] **23.4** Test each alert rule (sample):
  - [ ] CriticalViolationDetected ✓
  - [ ] ForbiddenMetricSpike ✓
  - [ ] PolicyLoadFailure ✓
  - [ ] EmergencyOverrideStayingActive ✓
  - [ ] CommitteeOverloaded ✓

### Step 24: Load Testing (30 minutes)
- [ ] **24.1** Simulate high violation rate:
  ```bash
  # Generate 100 violations
  for i in {1..100}; do
    curl -X POST http://charter-api:8000/test/violation \
      -H "Content-Type: application/json" \
      -d '{"severity": "WARNING", "type": "data_extraction", "node": "test_node_'$i'"}'
  done
  ```
- [ ] **24.2** Verify metrics are updated:
  - [ ] Dashboard shows spike in violations
  - [ ] Alerts fire appropriately
  - [ ] No performance degradation
- [ ] **24.3** Verify metrics don't drop:
  - [ ] Check `up` metric: `up{job="westworld-charter"}`
  - [ ] Should stay = 1 (up)

---

## ✅ Phase 2F: Documentation & Handoff

### Step 25: Create Runbooks (30 minutes)
- [ ] **25.1** Create runbook for each alert:
  - [ ] File: `docs/runbooks/charter-alerts-runbook.md`
  - [ ] Include: alert description, root causes, remediation steps
- [ ] **25.2** Document dashboard usage:
  - [ ] File: `docs/dashboards-guide.md`
  - [ ] How to read each panel
  - [ ] What each metric means
  - [ ] How to drill down for details
- [ ] **25.3** Document troubleshooting:
  - [ ] Common issues and fixes
  - [ ] How to verify metrics are flowing
  - [ ] How to manually trigger alerts

### Step 26: Create Deployment Scripts (30 minutes)
- [ ] **26.1** Create deployment script:
  ```bash
  # scripts/deploy-observability.sh
  - Deploy Prometheus config
  - Deploy AlertManager config
  - Deploy Grafana dashboards
  - Verify all services healthy
  ```
- [ ] **26.2** Create verification script:
  ```bash
  # scripts/verify-observability.sh
  - Check all metrics are flowing
  - Check all alerts are loaded
  - Check Slack integration
  - Health check dashboard panels
  ```
- [ ] **26.3** Document deployment procedure:
  - [ ] Prerequisites
  - [ ] Deployment steps
  - [ ] Verification steps
  - [ ] Rollback procedure

### Step 27: Final Validation (30 minutes)
- [ ] **27.1** Full end-to-end test:
  - [ ] Trigger violation → Dashboard shows it → Alert fires → Slack notified
- [ ] **27.2** Performance validation:
  - [ ] Dashboard load time < 5 seconds
  - [ ] Alert response time < 1 minute
  - [ ] No dropped metrics
- [ ] **27.3** Documentation review:
  - [ ] All runbooks are clear
  - [ ] Dashboards are documented
  - [ ] Troubleshooting guide is complete
- [ ] **27.4** Team training:
  - [ ] Brief security team on dashboards
  - [ ] Brief SRE team on alerts
  - [ ] Brief on-call on escalation procedures

### Step 28: Mark Complete ✅
- [ ] **28.1** Update WEST_0105_OBSERVABILITY_PLAN.md:
  ```
  Task 1 (Prometheus Exporter): ✅ COMPLETE
  Task 2 (Dashboards & Alerting): ✅ COMPLETE
  Task 3 (MAPE-K Integration): ⏳ NEXT
  Task 4 (E2E Tests): ⏳ PENDING
  ```
- [ ] **28.2** Create completion summary:
  - [ ] Dashboards created: 2
  - [ ] Alert rules created: 11
  - [ ] Notification channels: 4 (Slack + PagerDuty)
  - [ ] Metrics flowing: 15/15 ✓
- [ ] **28.3** Schedule WEST-0105-3 kickoff
  - [ ] MAPE-K integration starts immediately
  - [ ] Can run in parallel with dashboard tuning

---

## 📊 Success Criteria Summary

| Component | Status | Evidence |
|-----------|--------|----------|
| Dashboards Created | ✅ | 2 dashboards with 14 total panels |
| Alert Rules | ✅ | 11 alert rules deployed and firing |
| Prometheus Scraping | ✅ | All 15 metrics flowing into Prometheus |
| Slack Integration | ✅ | Test message received in all channels |
| PagerDuty Integration | ✅ | Critical alerts escalated |
| Dashboard Performance | ✅ | Load time < 5 seconds |
| Alert Response Time | ✅ | Alert fires < 1 minute after event |
| Documentation | ✅ | Runbooks, guides, troubleshooting complete |
| Team Readiness | ✅ | Security & SRE trained on system |

---

## ⏰ Timeline Estimate

- **Setup & Prerequisites**: 30 min
- **Dashboard 1 (Violations & Threats)**: 1.5 hours
- **Dashboard 2 (Enforcement Performance)**: 1.5 hours
- **Prometheus & AlertManager Config**: 1 hour
- **Testing & Validation**: 1.5 hours
- **Documentation & Handoff**: 1 hour
- **Buffer (debugging, issues)**: 30 min
- **TOTAL**: 4-5 hours

---

## 🚀 Next After Completion

Immediately start **WEST-0105-3: MAPE-K Integration**
- Update MAPE-K Monitor phase to consume Charter metrics
- Update MAPE-K Analyze phase to process violations
- Update MAPE-K Plan phase with severity → action mapping
- Update MAPE-K Execute phase to record healing actions

---

*Last Updated: 2026-01-11 | Phase: 0/WEST-0105-2 | Status: READY TO IMPLEMENT*
