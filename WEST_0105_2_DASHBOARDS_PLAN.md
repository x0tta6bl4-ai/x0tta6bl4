# WEST-0105-2: Grafana Dashboards & AlertManager Rules

**Status**: ⏳ READY TO START  
**Effort**: 4-5 hours  
**Dependencies**: WEST-0105-1 ✅ COMPLETE

---

## 📋 Task Breakdown

### Phase 2A: Grafana Dashboard 1 - Violations & Threats (2-2.5 hours)

#### Objectives
- Real-time visualization of Charter violations
- Threat detection heatmap
- Node risk scoring
- Policy violation timeline

#### Dashboard Components

**1. Violations Timeline (Top of Dashboard)**
```
Type: Graph/Time-Series
Metric: rate(westworld_charter_violations_total[5m])
Filters: 
  - By severity (CRITICAL, SUSPENSION, BAN, etc.)
  - By violation_type (data_extraction, behavioral_prediction, etc.)
Colors: 
  - CRITICAL → Red
  - SUSPENSION → Orange
  - WARNING → Yellow
  - OTHER → Blue
```

**2. Top 10 Violating Nodes (Heatmap)**
```
Type: Heatmap
Metric: topk(10, sum by (node_or_service) (westworld_charter_violations_total))
X-Axis: Node name
Y-Axis: Violation type
Color intensity: Violation count
Click action: Drill down to node details
```

**3. Violation Type Breakdown (Pie Chart)**
```
Type: Pie/Donut Chart
Metric: sum by (violation_type) (westworld_charter_violations_total)
Labels: violation_type
Sorting: By value (descending)
Top 5 types highlighted
```

**4. Forbidden Metric Attempts (Live Heatmap)**
```
Type: Heatmap
Metric: rate(westworld_charter_forbidden_metric_attempts_total[1m])
X-Axis: metric_name (user_location, device_hardware_id, etc.)
Y-Axis: node_or_service
Color intensity: Attempt rate
Threshold: Red if > 10 attempts/min
Purpose: Spot reconnaissance patterns
```

**5. Current Investigation Status (Gauge)**
```
Type: Gauge
Metric: sum by (severity) (westworld_charter_violations_under_investigation)
Ranges:
  - 0-2: Green (manageable)
  - 3-5: Orange (high workload)
  - 6+: Red (overloaded)
```

**6. Emergency Override Status (Stat Box)**
```
Type: Stat
Metric: westworld_charter_emergency_override_active_count
Color:
  - 0: Green ✓
  - 1: Orange ⚠️
  - 2+: Red 🚨
Click: Show override history table
```

#### Dashboard Layout
```
┌─────────────────────────────────────────────────────────┐
│ Violations Timeline (Rate)                             │
│ [CRITICAL │ SUSPENSION │ BAN │ WARNING]               │
└─────────────────────────────────────────────────────────┘
┌─────────────────────┬─────────────────────┬──────────────┐
│ Top 10 Nodes        │ Violation Types     │ Override     │
│ (Heatmap)          │ (Pie Chart)         │ Status [0]   │
│                    │                     │ 🟢           │
└─────────────────────┴─────────────────────┴──────────────┘
┌─────────────────────────────────────────────────────────┐
│ Forbidden Metric Attempts (Reconnaissance Heatmap)      │
│ Y-axis: Metric Names | X-axis: Nodes                   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────┬─────────────────────────────────┐
│ Investigations      │ Latest Events Table             │
│ (Gauge by Severity) │ Violation | Node | Time | Type  │
│ CRITICAL: 0         │ ........                        │
│ WARNING: 5          │ ........                        │
└─────────────────────┴─────────────────────────────────┘
```

---

### Phase 2B: Grafana Dashboard 2 - Enforcement Performance (2-2.5 hours)

#### Objectives
- SLA monitoring
- Performance bottleneck detection
- Latency trends
- System health

#### Dashboard Components

**1. Metric Validation Latency (p50/p95/p99)**
```
Type: Graph (stacked)
Metrics:
  - histogram_quantile(0.50, metric_validation_latency_ns) / 1000 → p50 µs
  - histogram_quantile(0.95, metric_validation_latency_ns) / 1000 → p95 µs
  - histogram_quantile(0.99, metric_validation_latency_ns) / 1000 → p99 µs
SLA Threshold: Red line at 10µs (10,000ns)
Alert Zone: Highlight if p99 > 20µs
```

**2. Policy Load Frequency & Duration**
```
Type: Dual-axis graph
Left Y-axis: rate(policy_load_duration_ms[1h]) → reloads per hour
Right Y-axis: histogram_quantile(0.99, policy_load_duration_ms) → p99 duration ms
Colors:
  - Load frequency: Blue
  - Duration: Orange
Threshold: 1 reload per day is normal, >5/hour is suspicious
```

**3. Committee Notification Latency SLA**
```
Type: Gauge + Graph
Gauge: Current p99 latency
Graph: Trend over 24 hours
SLA: Green if p99 < 500ms, Orange if 500-1000ms, Red if > 1000ms
```

**4. Violation Detection → Response Timeline (E2E)**
```
Type: Graph
Metric: histogram_quantile(0.99, violation_report_latency_ms)
Labels: "End-to-end violation processing"
SLA Line: 1000ms (1 second)
Shows: How fast from detection to committee notification
```

**5. Data Revocation Status**
```
Type: Counter Card
Metrics:
  - data_revocation_events_total (total revocations)
  - histogram_quantile(0.99, data_revocation_latency_ms) (p99 latency)
  - Last revocation: N minutes ago
Status: Green if latency SLA met, Orange/Red otherwise
```

**6. Policy Freshness Indicator**
```
Type: Stat Box
Metric: floor((now() - policy_last_load_timestamp) / 3600) → Hours since load
Display:
  - 0-4 hours: Green ✓ (Fresh)
  - 4-24 hours: Orange ⚠️ (Aging)
  - 24+ hours: Red 🚨 (Stale - alert!!)
```

#### Dashboard Layout
```
┌──────────────────────────────────────────────────────────┐
│ Metric Validation Latency (p50/p95/p99)                 │
│ SLA: p99 < 10µs ─────────────────────                   │
│ [Graph with three lines and threshold]                  │
└──────────────────────────────────────────────────────────┘
┌─────────────────────┬──────────────────────────────────┐
│ Policy Load Stats   │ Committee Notification Latency   │
│ • Frequency: 2/day  │ Current p99: 234ms 🟢            │
│ • p99: 156ms        │ [Trend graph - 24h]              │
│ • Last load: 2h ago │                                  │
└─────────────────────┴──────────────────────────────────┘
┌──────────────────────────────────────────────────────────┐
│ E2E Violation Response Time (p99)                        │
│ Target: 1000ms ─────────────────────                    │
│ [Graph - violation detection to notification]           │
└──────────────────────────────────────────────────────────┘
┌─────────────────────┬──────────────────────────────────┐
│ Data Revocation     │ Policy Freshness                 │
│ • Total: 42 events  │ Last loaded: 3h ago 🟢           │
│ • p99 latency: 2.1s │ Status: FRESH                    │
│ • SLA met: ✓        │                                  │
└─────────────────────┴──────────────────────────────────┘
```

---

### Phase 2C: AlertManager Rules Configuration (1 hour)

#### Alert Rules Definition

**1. CriticalViolationDetected** (CRITICAL)
```yaml
alert: CriticalViolationDetected
expr: increase(westworld_charter_violations_total{severity="CRITICAL"}[1m]) > 0
for: 1m
labels:
  severity: critical
  team: security
annotations:
  summary: "Critical Charter violation detected"
  description: "{{ $value }} critical violations in last 1m"
  runbook: "https://wiki.example.com/charter/critical-violations"
  dashboard: "Violations & Threats"
```

**2. ForbiddenMetricSpike** (WARNING)
```yaml
alert: ForbiddenMetricSpike
expr: rate(westworld_charter_forbidden_metric_attempts_total[5m]) > 10
for: 5m
labels:
  severity: warning
  team: security
annotations:
  summary: "Spike in forbidden metric access attempts"
  description: "{{ $value }} attempts/sec for metric {{ $labels.metric_name }}"
  dashboard: "Violations & Threats"
```

**3. ValidationLatencySLAViolation** (WARNING)
```yaml
alert: ValidationLatencySLAViolation
expr: histogram_quantile(0.99, rate(westworld_charter_metric_validation_latency_ns_bucket[5m])) > 20000000  # > 20µs
for: 5m
labels:
  severity: warning
  team: infrastructure
annotations:
  summary: "Metric validation SLA violated (p99 > 20µs)"
  description: "Current p99: {{ $value | humanizeDuration }}"
  dashboard: "Enforcement Performance"
```

**4. PolicyLoadFailure** (CRITICAL)
```yaml
alert: PolicyLoadFailure
expr: (now() - westworld_charter_policy_last_load_timestamp) > 86400  # 24 hours
for: 1h
labels:
  severity: critical
  team: security
annotations:
  summary: "Policy not loaded for > 24 hours"
  description: "Last load: {{ $value | humanizeTimestamp }}"
  action: "Manual policy load required"
```

**5. EmergencyOverrideStayingActive** (CRITICAL)
```yaml
alert: EmergencyOverrideStayingActive
expr: westworld_charter_emergency_override_active_count > 0
for: 30m
labels:
  severity: critical
  team: security
annotations:
  summary: "Emergency override active for > 30 minutes"
  description: "{{ $value }} override(s) active"
  action: "Verify reason and disable if no longer needed"
```

**6. CommitteeOverloaded** (WARNING)
```yaml
alert: CommitteeOverloaded
expr: sum(westworld_charter_violations_under_investigation) > 10
for: 10m
labels:
  severity: warning
  team: security
annotations:
  summary: "Audit committee investigation queue > 10 items"
  description: "{{ $value }} violations under investigation"
  action: "Consider escalating or adding committee resources"
```

---

### Phase 2D: AlertManager Notification Channels (1 hour)

#### Notification Integration

**Slack Channel: #charter-security**
```
For: CriticalViolationDetected, EmergencyOverrideStayingActive
Template:
🚨 CRITICAL: Charter Violation Detected
Severity: {{ .GroupLabels.severity }}
Type: {{ .GroupLabels.violation_type }}
Node: {{ .GroupLabels.node_or_service }}
Details: {{ .Alerts[0].Annotations.description }}
Dashboard: [Violations & Threats](http://grafana/d/violations-threats)
```

**PagerDuty: Critical Violations**
```
For: CriticalViolationDetected
Severity: Critical
Details: Immediate escalation to on-call security engineer
```

**Slack Channel: #charter-sre**
```
For: ValidationLatencySLAViolation, PolicyLoadFailure
Template:
⚠️ WARNING: Performance Issue
Alert: {{ .GroupLabels.alertname }}
Description: {{ .Alerts[0].Annotations.description }}
Dashboard: [Enforcement Performance](http://grafana/d/enforcement-performance)
```

**Email to audit-committee@example.com**
```
For: CommitteeOverloaded
Template:
Subject: Audit Committee Workload Alert
Body: {{ .Alerts[0].Annotations.description }}
Action Required: Review and prioritize investigations
```

---

## 📊 Deliverables

### Dashboard 1: Violations & Threats
- File: `grafana/dashboards/violations-threats.json`
- Panels: 6
- Refresh: 30s
- Time range: Last 24 hours (default)

### Dashboard 2: Enforcement Performance
- File: `grafana/dashboards/enforcement-performance.json`
- Panels: 6
- Refresh: 30s
- Time range: Last 24 hours (default)

### AlertManager Rules
- File: `prometheus/alerts/charter-alerts.yml`
- Rules: 6
- Evaluation interval: 30s

### Notification Templates
- File: `alertmanager/config.yml`
- Channels: Slack (3), PagerDuty (1), Email (1)

---

## 🎯 Success Criteria

- ✅ Both dashboards created and functional
- ✅ All 6 alert rules firing correctly
- ✅ Notification delivery verified (test alert sent)
- ✅ Dashboard links working in alert annotations
- ✅ Grafana datasource configured for Prometheus
- ✅ Grafana authentication configured

---

## 🔗 Integration with WEST-0105-3

After completion, update MAPE-K loop to:
- **MONITOR**: Consume violations from Prometheus
- **ANALYZE**: Use violation severity & type from metrics
- **PLAN**: Map severity to action (block, investigate, escalate)
- **EXECUTE**: Record action with `investigation_initiated_total` metric

---

## 📈 Testing Procedure

1. **Unit Test**: Each dashboard can be viewed in Grafana
2. **Integration Test**: Trigger test violation, verify alert fires
3. **E2E Test**: Alert → Slack notification delivery
4. **Load Test**: 100 violations/sec, verify alert handling

---

## ⏭️ Next Steps After Completion

1. **WEST-0105-3**: Integrate metrics into MAPE-K loop
2. **WEST-0105-4**: Create end-to-end tests
3. **Phase 1**: Deploy Cradle Sandbox with full observability

---

*WEST-0105-2: Ready to start | Phase: 0/WEST-0105 | Last updated: 2026-01-11*
