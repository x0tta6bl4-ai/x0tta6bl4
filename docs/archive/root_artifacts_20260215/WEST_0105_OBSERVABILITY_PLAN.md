# WEST-0105: Observability Layer for Anti-Delos Charter
## Phase 0 → Live Monitoring & Real-Time Enforcement Visibility

**Status**: 🔄 IN PROGRESS  
**Start Date**: 2026-01-11  
**Target Completion**: 2026-01-18 (Week 2)

---

## 📋 Epic: Make Charter Observable

**Goal:** Charter transitions from "static policy" to "live enforcement system" with real-time metrics, alerting, and MAPE-K integration.

**Acceptance Criteria:**
- [x] Prometheus metrics exported from Charter
- [ ] Grafana dashboards showing violations & performance
- [ ] AlertManager rules for security events
- [ ] MAPE-K loop consumes Charter signals
- [ ] End-to-end test: violation → alert → action

---

## 🎯 Breakdown by Priority

### **WEST-0105-1: Prometheus Exporter (CURRENT - In Progress)**
**Complexity**: Medium | **Effort**: 4-6 hours | **Blocks**: All others

#### Tasks:
- [ ] 1.1: Define metric schema
  - `charter_violations_total{severity, violation_type, node_or_service}`
  - `charter_forbidden_metric_attempts_total{metric_name, node_or_service}`
  - `charter_validation_latency_ns_bucket` (histogram with buckets)
  - `charter_policy_load_duration_ms`
  - `charter_audit_committee_notifications_total`
  - `charter_data_revocation_events_total`

- [ ] 1.2: Instrument AntiDelosCharter class
  - Import prometheus_client
  - Add counters for violations
  - Add histogram for latency
  - Add gauge for policy load time
  - Update all methods to emit metrics

- [ ] 1.3: Create PrometheusRegistry integration
  - Singleton pattern for metrics
  - Proper namespacing (`westworld_charter_*`)
  - Thread-safe counter/histogram updates

- [ ] 1.4: Add tests for metric emission
  - Verify counters increment
  - Verify histogram buckets
  - Verify gauge updates
  - Test concurrent metric updates

- [ ] 1.5: Document metric exports
  - `/metrics` endpoint schema
  - Example Prometheus scrape config
  - Metric interpretation guide

**Deliverables:**
- `src/westworld/prometheus_metrics.py` - Metrics definitions
- `src/westworld/anti_delos_charter.py` - Instrumented (updated)
- `tests/test_charter_prometheus.py` - 15+ metric tests
- `docs/PROMETHEUS_METRICS.md` - Metric reference

---

### **WEST-0105-2: Grafana Dashboards + Alerting (Next)**
**Complexity**: Medium | **Effort**: 4-5 hours | **Depends on**: 1

#### Tasks:
- [ ] 2.1: Create "Violations & Threats" dashboard
  - Violations timeline (by severity)
  - Top nodes by violation count
  - Violation type distribution
  - Forbidden metric attempts heatmap

- [ ] 2.2: Create "Enforcement Performance" dashboard
  - Metric validation latency (p50, p95, p99)
  - Policy load frequency & duration
  - Committee notification latency
  - Data revocation timeline

- [ ] 2.3: Implement AlertManager rules
  ```
  - ForbiddenMetricSpike: attempts_rate > threshold for 5m
  - CriticalViolation: severity=CRITICAL > 0
  - ValidationLatencySLA: latency_p99 > 50ms
  - PolicyLoadFailure: load_failures > 0
  ```

- [ ] 2.4: Create alert notification templates
  - Slack: 3 channels (violations, perf, debug)
  - PagerDuty: Critical violations → immediate escalation
  - Log to audit trail

**Deliverables:**
- `monitoring/dashboards/charter-violations.json` - Grafana dashboard
- `monitoring/dashboards/charter-performance.json` - Grafana dashboard
- `monitoring/alert_rules/charter.rules` - Alert rules
- `monitoring/notification_templates/` - Alert templates

---

### **WEST-0105-3: MAPE-K Integration (Parallel)**
**Complexity**: High | **Effort**: 6-8 hours | **Depends on**: 1

#### Tasks:
- [ ] 3.1: Update MAPE-K MONITOR phase
  - Only subscribe to `charter_allowed_metrics`
  - Log attempts on forbidden metrics
  - Feed violations to knowledge base

- [ ] 3.2: Update MAPE-K ANALYZE phase
  - Consume charter_violations events
  - Detect violation patterns
  - Calculate threat level per node

- [ ] 3.3: Update MAPE-K PLAN phase
  - Generate remediation plans based on violations
  - Severity → action mapping:
    - WARNING → log & monitor
    - SUSPENSION → quarantine network
    - BAN → remove from cluster
    - CRIMINAL → escalate to DAO

- [ ] 3.4: Add action execution
  - Execute planned remediation
  - Log all actions to audit trail
  - Emit `healing_action_taken` metric

**Deliverables:**
- `src/self_healing/mape_k_charter_integration.py` - Updated MAPE-K
- `tests/test_mape_k_charter_integration.py` - Integration tests
- `docs/MAPE_K_CHARTER_FLOW.md` - Flow documentation

---

### **WEST-0105-4: End-to-End Tests + Validation (Final)**
**Complexity**: Medium | **Effort**: 3-4 hours | **Depends on**: 1, 2, 3

#### Tasks:
- [ ] 4.1: E2E scenario: Violation detection → Alert
  - Simulate forbidden metric collection
  - Verify violation counter incremented
  - Verify alert triggered in AlertManager
  - Verify Grafana shows violation

- [ ] 4.2: E2E scenario: Alert → MAPE-K Action
  - Violation generated
  - MAPE-K analyzes
  - Remediation plan created
  - Action executed
  - Metric shows healing action

- [ ] 4.3: Load test metrics pipeline
  - 1000 violations/sec sustained
  - Verify no metric loss
  - Verify latency < 100ms end-to-end

- [ ] 4.4: Integration test with Prometheus
  - Start Prometheus scraper
  - Generate violations
  - Query Prometheus
  - Verify metrics present

**Deliverables:**
- `tests/test_observability_e2e.py` - E2E tests
- `tests/test_metrics_performance.py` - Load tests
- `docs/OBSERVABILITY_E2E.md` - Test scenarios

---

## 📊 Timeline & Milestones

```
Week 2 (Jan 13-15)
├─ Jan 13: WEST-0105-1 Complete (Prometheus exporter)
├─ Jan 14: WEST-0105-2 Complete (Dashboards & alerts)
├─ Jan 15: WEST-0105-3 Complete (MAPE-K integration)
└─ Jan 15: WEST-0105-4 Complete (E2E tests)

Week 3 (Jan 18)
└─ Code review, documentation, production deployment
```

---

## 🎓 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Metrics exported | 6+ metrics | 🔄 In progress |
| Dashboards created | 2 dashboards | ⏳ Pending 1 |
| Alert rules | 4+ rules | ⏳ Pending 2 |
| MAPE-K integration | Full flow | ⏳ Pending 3 |
| E2E tests | 4 scenarios | ⏳ Pending 4 |
| Code coverage | >75% | ⏳ After all done |

---

## 🔧 Technical Stack

- **Metrics**: `prometheus_client` (Python library)
- **Dashboards**: Grafana + JSON API
- **Alerting**: AlertManager + custom templates
- **Integration**: MAPE-K loop (existing)
- **Testing**: pytest + prometheus_client test utilities

---

## 📝 Related Epics

- ✅ **WEST-0104**: Charter Test Infrastructure (COMPLETE)
- 🔄 **WEST-0105**: Observability Layer (THIS EPIC)
- ⏳ **WEST-0106**: DAO Integration (After 0105)
- ⏳ **Phase 1**: Cradle Sandbox (After 0105)

---

## 🚀 Current Status

**Active Task**: WEST-0105-1.1 - Define metric schema & start instrumentation

Next: Begin implementation of Prometheus metrics collection in AntiDelosCharter.
