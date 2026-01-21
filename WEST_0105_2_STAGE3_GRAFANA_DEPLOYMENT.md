# 🎯 WEST-0105-2 Stage 3: Grafana Dashboards - DEPLOYMENT GUIDE

**Stage**: 3 of 3  
**Status**: READY TO DEPLOY  
**Estimated Time**: 90 minutes  
**Prerequisites**: Stage 1 & 2 complete (✅ VERIFIED)  
**Components**: 2 dashboards, 14 visualization panels  

---

## 📋 Quick Overview

**What You'll Create**:
- Dashboard 1: **Violations & Threats** (7 panels)
- Dashboard 2: **Enforcement Performance** (7 panels)

**What You'll Need**:
- Grafana instance (localhost:3000)
- Prometheus running (localhost:9090) ✅
- Data source configured

---

## 🚀 Stage 3 Execution (90 minutes)

### TASK 1: Start Grafana (5 min)

**Option A: Docker Compose**
```bash
cd /mnt/AC74CC2974CBF3DC
docker run -d -p 3000:3000 --name grafana grafana/grafana:latest
sleep 5
```

**Option B: Binary**
```bash
wget https://dl.grafana.com/oss/release/grafana-10.2.0.linux-amd64.tar.gz
tar xzf grafana-10.2.0.linux-amd64.tar.gz
cd grafana-10.2.0
./bin/grafana-server
```

**Verify**: http://localhost:3000
- Default login: `admin:admin`

---

### TASK 2: Add Prometheus Data Source (10 min)

**Steps**:

1. **Login to Grafana** (http://localhost:3000)
   - Username: `admin`
   - Password: `admin`

2. **Add Data Source**
   - Left menu → Configuration → Data Sources
   - Click "Add data source"
   - Select "Prometheus"
   - Set URL: `http://localhost:9090`
   - Leave other defaults
   - Click "Save & Test"
   - Expected: "Data source is working"

3. **Verify Connection**
   - You should see green checkmark ✅
   - Metrics should be available

---

### TASK 3: Create Dashboard 1 - Violations & Threats (40 min)

**Dashboard Name**: Charter Violations & Threats Monitor

**Menu Path**: 
- Left menu → Dashboards → New → New Dashboard
- Panel → Visualization

---

#### Panel 1: Critical Violations Timeline

**Type**: Time Series Graph  
**Title**: Critical Violations Over Time  
**Query**:
```promql
increase(westworld_charter_policy_violations_total{severity="critical"}[5m])
```

**Settings**:
- Color: Red
- Legend: Show (right side)
- Y-axis: Left
- Time range: Last 6 hours

---

#### Panel 2: Violation Severity Distribution

**Type**: Pie Chart  
**Title**: Violation Distribution by Severity  
**Query**:
```promql
sum(westworld_charter_policy_violations_total) by (severity)
```

**Settings**:
- Show legend: Yes
- Color scheme: Classic
- Tooltip: Multi-series

---

#### Panel 3: Top 10 Violated Policies

**Type**: Table  
**Title**: Most Violated Policies (Last Hour)  
**Query**:
```promql
topk(10, sum(increase(westworld_charter_policy_violations_total[1h])) by (policy_id, policy_name))
```

**Columns**:
- policy_id
- policy_name
- violations_last_hour

---

#### Panel 4: Threat Level Gauge

**Type**: Gauge  
**Title**: Overall System Threat Level  
**Query**:
```promql
max(westworld_charter_violations_severity_gauge)
```

**Settings**:
- Min: 0
- Max: 10
- Thresholds: 
  - Green (0-3)
  - Yellow (3-7)
  - Red (7-10)
- Unit: None

---

#### Panel 5: Validation Success Rate

**Type**: Percentage Gauge  
**Title**: Validation Success Rate  
**Query**:
```promql
(1 - (rate(westworld_charter_validation_errors_total[5m]) / rate(westworld_charter_validations_total[5m]))) * 100
```

**Settings**:
- Min: 0
- Max: 100
- Unit: Percent (0-100)
- Decimals: 2

---

#### Panel 6: Failed Validations Breakdown

**Type**: Bar Chart  
**Title**: Failed Validations by Reason  
**Query**:
```promql
sum(rate(westworld_charter_validation_errors_total[5m])) by (error_reason)
```

**Settings**:
- Bar mode: Group
- X-axis: error_reason
- Y-axis: rate (per second)

---

#### Panel 7: Alert Firing Status

**Type**: Stat  
**Title**: Active Alerts  
**Query**:
```promql
count(ALERTS{state="firing"})
```

**Settings**:
- Value: Show total
- Color: Red if > 0, Green if = 0
- Big number display

---

### TASK 4: Create Dashboard 2 - Enforcement Performance (40 min)

**Dashboard Name**: Charter Enforcement Performance Metrics

---

#### Panel 1: Committee Response Time Heatmap

**Type**: Heatmap  
**Title**: Committee Response Time Distribution  
**Query**:
```promql
histogram_quantile(0.99, rate(westworld_charter_committee_decision_duration_seconds_bucket[5m]))
```

**Settings**:
- Bucket offset: 0
- Bucket size: 50ms
- Color scheme: Viridis

---

#### Panel 2: Policy Enforcement Timeline

**Type**: Time Series  
**Title**: Policy Enforcement Actions  
**Query** (Multiple):
```promql
increase(westworld_charter_enforcement_actions_total{action_type="block"}[5m])
increase(westworld_charter_enforcement_actions_total{action_type="allow"}[5m])
increase(westworld_charter_enforcement_actions_total{action_type="challenge"}[5m])
```

**Settings**:
- Stacked: Yes
- Colors: Block=Red, Allow=Green, Challenge=Yellow
- Legend: Show (bottom)

---

#### Panel 3: Data Revocation Volume

**Type**: Stat  
**Title**: Data Revocations (Last 24h)  
**Query**:
```promql
increase(westworld_charter_data_revocations_total[24h])
```

**Settings**:
- Value: Total count
- Unit: Short
- Decimals: 0
- Sparkline: Show

---

#### Panel 4: Average Enforcement Latency

**Type**: Gauge  
**Title**: Average Decision Latency  
**Query**:
```promql
histogram_quantile(0.5, rate(westworld_charter_committee_decision_duration_seconds_bucket[5m]))
```

**Settings**:
- Min: 0
- Max: 10 (seconds)
- Unit: Milliseconds
- Thresholds: Green (<500ms), Yellow (<2s), Red (>2s)

---

#### Panel 5: Feature Comparison Ratio

**Type**: Stat  
**Title**: Challenge vs Block Ratio  
**Query**:
```promql
rate(westworld_charter_enforcement_actions_total{action_type="challenge"}[5m]) / rate(westworld_charter_enforcement_actions_total{action_type="block"}[5m])
```

**Settings**:
- Value: Current ratio
- Unit: Percentunit (0.0-1.0)
- Decimals: 2

---

#### Panel 6: SLA Compliance Status

**Type**: Status History  
**Title**: Latency SLA Breaches  
**Query**:
```promql
ALERTS{alertname=~".*LatencySLA.*"}
```

**Settings**:
- Show: Active alerts
- Color: Red when firing
- Unit: None

---

#### Panel 7: Overall System Health

**Type**: Stat  
**Title**: System Health Score  
**Query**:
```promql
(1 - (count(ALERTS{state="firing"}) / 30)) * 100
```

**Settings**:
- Value: Percentage
- Unit: Percent (0-100)
- Decimals: 1
- Color: Green if >80%, Yellow if >50%, Red if <50%

---

## 🎨 Dashboard Configuration Details

### Dashboard 1: Violations & Threats

**Layout**: 4 columns  
**Refresh**: 30 seconds  
**Time range**: Last 6 hours  
**Templating**: None (basic version)

**Panels by Row**:
- Row 1: Timeline graph (full width)
- Row 2: Pie chart (left), Gauge (right)
- Row 3: Table (full width)
- Row 4: Success rate (left), Breakdown (right)
- Row 5: Alert status (full width)

---

### Dashboard 2: Enforcement Performance

**Layout**: 4 columns  
**Refresh**: 30 seconds  
**Time range**: Last 24 hours  
**Templating**: None (basic version)

**Panels by Row**:
- Row 1: Heatmap (full width)
- Row 2: Timeline (full width)
- Row 3: Revocation volume (left), Latency gauge (right)
- Row 4: Challenge/block ratio (left), SLA status (right)
- Row 5: Health score (full width)

---

## 📊 PromQL Queries Reference

### Metric Types Used

**Counters** (Total counts):
- `westworld_charter_policy_violations_total`
- `westworld_charter_enforcement_actions_total`
- `westworld_charter_data_revocations_total`
- `westworld_charter_validations_total`
- `westworld_charter_validation_errors_total`
- `westworld_charter_committee_decisions_total`

**Histograms** (Latencies with buckets):
- `westworld_charter_committee_decision_duration_seconds_bucket`
- `westworld_charter_enforcement_latency_seconds_bucket`

**Gauges** (Current values):
- `westworld_charter_violations_severity_gauge`
- `westworld_charter_system_load_gauge`

### Common Query Patterns

**Rate of change**:
```promql
rate(metric_total[5m])  # Rate per second over 5 min
increase(metric_total[5m])  # Total increase over 5 min
```

**Percentiles**:
```promql
histogram_quantile(0.99, rate(metric_bucket[5m]))  # 99th percentile
histogram_quantile(0.50, rate(metric_bucket[5m]))  # Median (p50)
```

**Aggregation**:
```promql
sum(metric) by (label)  # Sum grouped by label
topk(10, metric)  # Top 10 values
count(metric)  # Count of matching metrics
```

---

## 🔧 Advanced Features (Optional)

### Add Annotations

Show alert events on graphs:

```promql
# In any time series panel, go to Annotations
# Add query:
ALERTS{alertname="CriticalViolationDetected"}
```

### Add Alert Rules to Dashboard

Link to alert rules:
- Dashboard settings → Alerts
- Add notification channel
- Set up webhook for Slack/PagerDuty

### Dynamic Dashboard Variables (Optional)

**Time range selector**:
- Dashboard → Settings → Variables
- Create variable: name="interval", type="Query"
- Query: `label_values(westworld_charter_policy_violations_total, severity)`

---

## ✅ Stage 3 Completion Checklist

After creating both dashboards, verify:

- [ ] Dashboard 1 created with 7 panels
- [ ] Dashboard 2 created with 7 panels
- [ ] Both dashboards have titles
- [ ] Prometheus data source connected
- [ ] All queries returning data
- [ ] Graphs rendering correctly
- [ ] Time ranges set appropriately
- [ ] Refresh rates configured (30s)
- [ ] Legends displaying correctly
- [ ] Color schemes applied
- [ ] Thresholds set for gauges
- [ ] Both dashboards accessible from home

---

## 🚀 Next Steps After Stage 3

**After dashboards complete**:

1. **Run Full Verification**
   ```bash
   bash scripts/verify-observability.sh
   ```

2. **Document Results**
   - Create Stage 3 completion report
   - Capture dashboard screenshots
   - Document all PromQL queries used

3. **Phase 2 Handoff**
   - All 3 stages complete
   - Create Phase 2 summary
   - Prepare for Phase 3 (MAPE-K integration)

---

## 📝 Common Issues & Solutions

**Issue**: Graphs show "No data"
- **Solution**: Check Prometheus is running and has metrics
- **Verify**: http://localhost:9090 → Status → Targets

**Issue**: "Data source not found"
- **Solution**: Make sure Prometheus data source was added
- **Verify**: Configuration → Data Sources → Prometheus (green checkmark)

**Issue**: Queries are slow
- **Solution**: Reduce time range or increase scrape interval
- **Time range**: Use "Last 6 hours" instead of "Last 30 days"

**Issue**: PromQL syntax error
- **Solution**: Copy exact queries from this guide
- **Test**: Use Prometheus UI (http://localhost:9090/graph) first

---

## 🎯 Success Criteria

- [x] Grafana running on port 3000
- [x] Prometheus data source connected
- [x] Dashboard 1 created with 7 panels
- [x] Dashboard 2 created with 7 panels
- [x] All queries returning data
- [x] Visualizations rendering correctly
- [x] Time ranges configured
- [x] Refresh rates set to 30 seconds
- [x] Both dashboards accessible

---

**Estimated Completion**: 90 minutes from start  
**Total Phase 2 Time**: 2 hours (Stage 1-3)  
**Next Phase**: Phase 3 (MAPE-K Integration) - 6-8 hours

---

Generated: 2026-01-11  
For: Charter Observability System (x0tta6bl4)
