# Prometheus Metrics Reference for Anti-Delos Charter

**WEST-0105-1: Prometheus Exporter**  
**Status**: ✅ COMPLETE (20/20 tests passing)

---

## 📊 Metric Overview

All metrics are prefixed with `westworld_charter_` and exported to `/metrics` endpoint.

### Metric Count
- **6 Counters** (monotonically increasing)
- **5 Histograms** (latency measurements)
- **4 Gauges** (current state)
- **Total: 15 metrics**

---

## 📈 Counter Metrics (Cumulative)

### 1. `violations_total`
**Type**: Counter  
**Labels**: `severity`, `violation_type`, `node_or_service`

```
westworld_charter_violations_total{
  severity="WARNING|SUSPENSION|BAN_1YEAR|PERMANENT_BAN|CRIMINAL_REFERRAL",
  violation_type="silent_collection|behavioral_prediction|data_extraction|...",
  node_or_service="service_name"
} N
```

**Purpose**: Track all detected violations by type and severity.  
**Use Cases**:
- Dashboard: Violations per day/hour
- Alert: Critical violations > 0
- Trending: Are we seeing more violations over time?

**Example**:
```
westworld_charter_violations_total{severity="CRITICAL",violation_type="data_extraction",node_or_service="node_234"} 5
westworld_charter_violations_total{severity="WARNING",violation_type="silent_collection",node_or_service="node_101"} 23
```

---

### 2. `forbidden_metric_attempts_total`
**Type**: Counter  
**Labels**: `metric_name`, `node_or_service`, `status`

```
westworld_charter_forbidden_metric_attempts_total{
  metric_name="user_location|browsing_history|device_hardware_id|...",
  node_or_service="service_name",
  status="blocked|reported|escalated"
} N
```

**Purpose**: Track every attempt to collect a forbidden metric.  
**Use Cases**:
- Dashboard: Heatmap of attempts per metric & node
- Alert: Spike in attempts for specific metric
- Security: Detect reconnaissance patterns

**Example**:
```
westworld_charter_forbidden_metric_attempts_total{metric_name="user_location",node_or_service="node_456",status="blocked"} 127
westworld_charter_forbidden_metric_attempts_total{metric_name="browsing_history",node_or_service="node_456",status="escalated"} 3
```

---

### 3. `data_revocation_events_total`
**Type**: Counter  
**Labels**: `reason`, `node_or_service`

```
westworld_charter_data_revocation_events_total{
  reason="account_closure|policy_violation|security_incident|...",
  node_or_service="service_name"
} N
```

**Purpose**: Track data access revocation procedures.  
**Use Cases**:
- Dashboard: Revocation timeline
- Compliance: Audit trail of data revocations
- SLA: Time to complete revocation

**Example**:
```
westworld_charter_data_revocation_events_total{reason="account_closure",node_or_service="user_alice"} 1
westworld_charter_data_revocation_events_total{reason="security_incident",node_or_service="honeypot_node"} 5
```

---

### 4. `audit_committee_notifications_total`
**Type**: Counter  
**Labels**: `severity`, `recipient_count`

```
westworld_charter_audit_committee_notifications_total{
  severity="WARNING|CRITICAL|...",
  recipient_count="1|2|3|5"
} N
```

**Purpose**: Track audit committee notification events.  
**Use Cases**:
- Dashboard: Committee workload
- Alert: Too many notifications (possible attack)
- SLA: Notification latency

---

### 5. `investigation_initiated_total`
**Type**: Counter  
**Labels**: `violation_type`, `initiated_by`

```
westworld_charter_investigation_initiated_total{
  violation_type="data_extraction|...",
  initiated_by="system|committee|external"
} N
```

**Purpose**: Track investigation procedure initiations.  
**Use Cases**:
- Dashboard: Investigation frequency by violation type
- Alert: Spike in investigations suggests coordinated attack

---

### 6. `emergency_override_total`
**Type**: Counter  
**Labels**: `reason`, `who_triggered`

```
westworld_charter_emergency_override_total{
  reason="security_incident|network_breach|...",
  who_triggered="cto_admin|security_team"
} N
```

**Purpose**: Track emergency override procedures.  
**Use Cases**:
- Dashboard: Override history
- Audit: Who triggered what and when
- Alert: Emergency override rate

---

## ⏱️ Histogram Metrics (Latency)

### 1. `metric_validation_latency_ns`
**Type**: Histogram  
**Unit**: Nanoseconds  
**Buckets**: 100ns, 1µs, 10µs, 100µs, 1ms, 10ms

```
westworld_charter_metric_validation_latency_ns_bucket{le="1000"} 45
westworld_charter_metric_validation_latency_ns_bucket{le="10000"} 89
westworld_charter_metric_validation_latency_ns_bucket{le="+Inf"} 100
westworld_charter_metric_validation_latency_ns_sum 834500
westworld_charter_metric_validation_latency_ns_count 100
```

**Purpose**: Measure metric validation performance.  
**SLA**: p99 < 10µs (10,000ns)  
**Use Cases**:
- Dashboard: Latency percentiles (p50, p95, p99)
- Alert: p99 > 10µs indicates performance degradation
- Debugging: Identify slow validation paths

---

### 2. `policy_load_duration_ms`
**Type**: Histogram  
**Unit**: Milliseconds  
**Buckets**: 10ms, 50ms, 100ms, 200ms, 500ms, 1000ms

**Purpose**: Measure policy loading time.  
**SLA**: p99 < 500ms  
**Use Cases**:
- Dashboard: Policy reload times
- Alert: Policy load > 1s suggests stale policies
- Debugging: Identify policy loading bottlenecks

---

### 3. `violation_report_latency_ms`
**Type**: Histogram  
**Unit**: Milliseconds  
**Buckets**: 50ms, 100ms, 250ms, 500ms, 1s, 2s

**Purpose**: Measure time from violation detection to full escalation.  
**SLA**: p99 < 1000ms (1 second)  
**Includes**:
- Investigation trigger
- Committee notification
- Immediate action execution

**Use Cases**:
- Dashboard: End-to-end violation response time
- Alert: Violations taking > 2s to process
- Trending: Is response time getting slower?

---

### 4. `committee_notification_latency_ms`
**Type**: Histogram  
**Unit**: Milliseconds  
**Buckets**: 10ms, 50ms, 100ms, 250ms, 500ms, 1s

**Purpose**: Measure audit committee notification delivery time.  
**SLA**: p99 < 500ms

---

### 5. `data_revocation_latency_ms`
**Type**: Histogram  
**Unit**: Milliseconds  
**Buckets**: 50ms, 100ms, 250ms, 500ms, 1s, 5s

**Purpose**: Measure data revocation procedure completion time.  
**SLA**: p99 < 5000ms (5 seconds)

---

## 📊 Gauge Metrics (Current State)

### 1. `violations_under_investigation`
**Type**: Gauge  
**Labels**: `severity`

```
westworld_charter_violations_under_investigation{severity="CRITICAL"} 3
westworld_charter_violations_under_investigation{severity="WARNING"} 12
```

**Purpose**: Current count of violations in investigating state.  
**Use Cases**:
- Dashboard: Ongoing investigation count
- Alert: Too many active investigations

---

### 2. `audit_committee_size`
**Type**: Gauge (no labels)

```
westworld_charter_audit_committee_size 5
```

**Purpose**: Number of audit committee members.  
**Use Cases**:
- Dashboard: Committee composition
- Verify: Is committee properly staffed?

---

### 3. `policy_last_load_timestamp`
**Type**: Gauge  
**Unit**: Unix timestamp (seconds since epoch)

```
westworld_charter_policy_last_load_timestamp 1673462400
```

**Purpose**: When was policy last loaded.  
**Use Cases**:
- Alert: Policy not loaded in > N hours (stale)
- Dashboard: Policy freshness

---

### 4. `emergency_override_active_count`
**Type**: Gauge  
**Unit**: Count

```
westworld_charter_emergency_override_active_count 0
```

**Purpose**: Number of active emergency overrides.  
**Note**: Should normally be 0 or very low.  
**Use Cases**:
- Dashboard: Emergency status
- Alert: Threshold exceeded (indicates crisis mode)

---

## 🔌 Integration Points

### Prometheus Scrape Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'westworld-charter'
    static_configs:
      - targets: ['localhost:8000']  # FastAPI app
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
```

### Example Queries

**Violations per hour**:
```
rate(westworld_charter_violations_total[1h])
```

**Forbidden attempt spike detection**:
```
rate(westworld_charter_forbidden_metric_attempts_total[5m]) > 10
```

**Validation latency p99**:
```
histogram_quantile(0.99, westworld_charter_metric_validation_latency_ns_bucket)
```

**Active investigations**:
```
westworld_charter_violations_under_investigation
```

---

## 🎯 Dashboard Recommendations

### Dashboard 1: Violations & Threats
- Violations timeline by severity
- Top violating nodes
- Violation type breakdown
- Forbidden metric attempts heatmap
- Policy freshness indicator

### Dashboard 2: Enforcement Performance
- Metric validation latency (p50, p95, p99)
- Policy load frequency & duration
- Committee notification latency
- Data revocation timelines
- Investigation timeline

---

## 🚨 Alert Rules

### Critical Alerts

1. **CriticalViolationDetected**
   ```
   ALERTS{severity="CRITICAL"} > 0 for 1m
   Action: Page on-call engineer
   ```

2. **ForbiddenMetricSpike**
   ```
   rate(forbidden_metric_attempts_total[5m]) > threshold for 5m
   Action: Investigate source, block if needed
   ```

3. **ValidationLatencySLA**
   ```
   histogram_quantile(0.99, validation_latency_ns) > 10_000_000 for 5m
   Action: Alert SRE/Infra team
   ```

4. **EmergencyOverrideActive**
   ```
   emergency_override_active_count > 1 for 10m
   Action: Page security team
   ```

---

## 📝 Python API for Instrumentation

```python
from src.westworld.prometheus_metrics import (
    record_violation,
    record_forbidden_attempt,
    record_data_revocation,
    record_validation_latency_ns,
    update_committee_size,
    get_metrics_text
)

# In your Charter code:
try:
    # Measure validation
    start = time.perf_counter_ns()
    # ... validation logic ...
    elapsed_ns = time.perf_counter_ns() - start
    record_validation_latency_ns(float(elapsed_ns))
    
    # Record violation
    record_violation('CRITICAL', 'data_extraction', 'node_123')
    
    # Record forbidden attempt
    record_forbidden_attempt('user_location', 'node_456', status='blocked')
    
except Exception as e:
    logger.error(f"Metric recording failed: {e}")
    # Don't let metrics failures break the app

# Export metrics
metrics_text = get_metrics_text()
# Send to /metrics endpoint
```

---

## ✅ Test Coverage

**Prometheus metrics module**: 80.49% coverage  
**Tests**: 20 tests, all passing

Test scenarios:
- ✅ Counter increments
- ✅ Histogram observations
- ✅ Gauge updates
- ✅ Concurrent updates
- ✅ Error handling
- ✅ Label validation
- ✅ Metric export format
- ✅ Thread safety

---

## 🎓 WEST-0105-1 Status

**Status**: ✅ COMPLETE

**Deliverables**:
- ✅ `prometheus_metrics.py` (315 lines)
- ✅ `test_charter_prometheus.py` (20 tests)
- ✅ `PROMETHEUS_METRICS.md` (this file)

**Next**: WEST-0105-2 (Grafana Dashboards & Alerting)

---

*Generated: 2026-01-11 | Module: Charter Observability | Phase: 0/WEST-0105-1*
