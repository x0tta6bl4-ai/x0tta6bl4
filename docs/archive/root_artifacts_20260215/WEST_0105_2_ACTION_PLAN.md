# 🎯 WEST-0105-2 Action Plan: NEXT STEPS

**Current Status**: WEST-0105-1 ✅ Complete | WEST-0105-2 ⏳ Ready to Start  
**Timeline**: 4-5 hours to Phase 2 completion  
**Priority**: HIGH (unblocks Phase 3 & real-time observability)

---

## 📋 Decision Point

### Choose Your Implementation Path

#### 🎓 Path A: Manual Implementation (Recommended for Learning)
**Best For**: Understanding Grafana, AlertManager, and observability principles  
**Time**: 4-5 hours  
**Effort**: High (hands-on work)  
**Learning Outcome**: Deep understanding of components  

**Steps**:
1. Open `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md`
2. Work through 28 steps sequentially
3. Create dashboards manually in Grafana UI
4. Configure alerts step-by-step
5. Test each component as you go

**Recommendation**: Choose this path if you want to understand how observability works.

---

#### ⚡ Path B: Automated Deployment (Fastest)
**Best For**: Quick deployment to get observability live  
**Time**: 1-2 hours  
**Effort**: Low (script-driven)  
**Learning Outcome**: Basic understanding of deployment process  

**Steps**:
1. Run deployment validation: `./scripts/deploy-observability.sh`
2. Deploy Prometheus alerts (automated)
3. Deploy AlertManager config (automated)
4. Create Grafana dashboards (manual - JSON import when available)
5. Run verification tests

**Recommendation**: Choose this path if you want observability running fast.

---

## 🚀 Recommended: Start Now (Path A - Manual)

Why manual is recommended for this project:
1. **Understanding**: You'll deeply understand each component
2. **Customization**: Can adapt to your specific needs
3. **Troubleshooting**: Better equipped to debug issues
4. **Scalability**: Ready to extend the system later

---

## ⏰ 4-5 Hour Implementation Timeline

### Hour 0-0.5: Prerequisites (30 minutes)
```
□ Verify Prometheus running (http://prometheus:9090)
□ Verify AlertManager running (http://alertmanager:9093)
□ Verify Grafana running (http://grafana:3000)
□ Verify Charter app exporting metrics (http://charter-api:8000/metrics)
□ Create Slack webhook if not done
□ Gather all configuration files
```

### Hour 0.5-1.5: Prometheus Setup (1 hour)
```
□ Deploy alert rules to Prometheus
□ Validate YAML syntax
□ Reload Prometheus
□ Verify alert rules loaded (check /alerts page)
□ Test one alert fires manually
```

### Hour 1.5-2: AlertManager Setup (30 minutes)
```
□ Deploy AlertManager config
□ Configure Slack webhook URLs
□ Reload AlertManager
□ Test Slack notification delivery
□ Verify routing configuration
```

### Hour 2-3.5: Grafana Dashboard 1 (1.5 hours)
```
□ Create dashboard: "Violations & Threats"
□ Add 7 panels with correct queries
□ Configure colors and thresholds
□ Add dashboard links
□ Verify data displays correctly
```

### Hour 3.5-5: Grafana Dashboard 2 (1.5 hours)
```
□ Create dashboard: "Enforcement Performance"
□ Add 7 panels with SLA thresholds
□ Configure latency charts
□ Add alert integration
□ Verify all panels show data
```

---

## 🎯 Implementation Path (Manual - Detailed)

### Phase 2A: Prometheus Alert Rules Deployment

**File to Deploy**: `prometheus/alerts/charter-alerts.yml`

**Steps**:
1. Copy alert rules file
2. Validate YAML
3. Update prometheus.yml
4. Reload Prometheus
5. Verify 11 rules loaded

**Duration**: 30 minutes  
**Success Criteria**: All 11 alert rules visible in Prometheus UI

---

### Phase 2B: AlertManager Configuration

**File to Deploy**: `alertmanager/config.yml`

**Steps**:
1. Set up Slack webhooks
2. Copy AlertManager config
3. Test notification channels
4. Configure PagerDuty (optional)
5. Reload AlertManager

**Duration**: 30 minutes  
**Success Criteria**: Test alert sent to Slack successfully

---

### Phase 2C: Grafana Dashboard 1 - Violations & Threats

**Create**: 7 panels visualizing threat landscape

**Panels**:
1. Violations timeline (5-min rate)
2. Top 10 violating nodes (heatmap)
3. Violation types distribution (pie)
4. Forbidden metric attempts (heatmap)
5. Current investigations (gauge)
6. Emergency override status (stat)
7. Recent events table

**Duration**: 1.5 hours  
**Success Criteria**: All panels load and display data without errors

---

### Phase 2D: Grafana Dashboard 2 - Enforcement Performance

**Create**: 7 panels visualizing SLA metrics

**Panels**:
1. Metric validation latency (p50/p95/p99)
2. Policy load frequency & duration
3. Committee notification latency
4. E2E violation response time
5. Data revocation rate
6. Policy freshness indicator
7. Investigation initiation rate

**Duration**: 1.5 hours  
**Success Criteria**: All panels load and SLA thresholds are visible

---

## 📊 Verification Checklist

After completing all phases:

### Prometheus Verification
- [ ] 11 alert rules loaded (check `/alerts`)
- [ ] Alert rules in "INACTIVE" state (or "FIRING" if conditions met)
- [ ] All metric names resolve correctly
- [ ] No syntax errors in Prometheus logs

### AlertManager Verification
- [ ] Configuration loads without errors
- [ ] 3 Slack channels configured
- [ ] PagerDuty integration ready (optional)
- [ ] Test alert reaches #charter-monitoring

### Grafana Verification
- [ ] Datasource "Prometheus-Charter" connects
- [ ] Dashboard 1: 7 panels load and show data
- [ ] Dashboard 2: 7 panels load and show data
- [ ] Charts refresh every 30 seconds
- [ ] Drill-down functionality works (heatmaps)

### End-to-End Verification
- [ ] Generate test violation
- [ ] Wait 2 minutes for scrape + eval
- [ ] Verify alert fires in Prometheus
- [ ] Verify Slack notification received
- [ ] Verify dashboard shows violation

---

## 🧪 Testing Procedure

### Test 1: Alert Firing
```bash
# Generate test CRITICAL violation
curl -X POST http://charter-api:8000/test/violation \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "CRITICAL",
    "violation_type": "data_extraction",
    "node_or_service": "test_node_123"
  }'

# Wait 2 minutes, then:
# - Check Prometheus: http://prometheus:9090/alerts
# - Check Slack: #charter-security
# - Check Grafana: Violations & Threats dashboard
```

### Test 2: Dashboard Functionality
```bash
# Dashboard loads quickly (< 5 seconds)
curl -w "%{http_code}" http://grafana:3000/d/violations-threats

# All panels have data (no "No data" message)
# Refresh rate is 30 seconds (visible in top-right)
# Heatmaps are clickable and drill-down works
```

### Test 3: Slack Notification
```bash
# Message contains:
# - Alert name
# - Severity level
# - Affected node/service
# - Dashboard link
# - Runbook link (if applicable)
```

---

## 🔧 Troubleshooting During Implementation

### If Prometheus alerts won't load:
```bash
# Check syntax
yamllint prometheus/alerts/charter-alerts.yml

# Check Prometheus logs
tail -f /var/log/prometheus/prometheus.log

# Verify file is in correct location
ls -la /etc/prometheus/rules/charter-alerts.yml

# Force reload
curl -X POST http://prometheus:9090/-/reload
```

### If Grafana dashboards show "No data":
```bash
# Check datasource
# Go to: http://grafana:3000/datasources
# Click "Prometheus-Charter"
# Run "Test Data Source"

# Check query
# In dashboard, edit panel
# Run query manually in Prometheus

# Common issues:
# - Wrong datasource selected
# - Query syntax error
# - Metrics not being scraped yet
```

### If Slack notifications don't arrive:
```bash
# Check webhook URL
echo $SLACK_WEBHOOK_URL

# Test Slack webhook directly
curl -X POST $SLACK_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text": "Test notification"}'

# Check AlertManager config
yamllint alertmanager/config.yml

# Check AlertManager logs
tail -f /var/log/alertmanager/alertmanager.log
```

---

## 📈 Metrics to Verify During Implementation

After deployment, verify these metrics are flowing:

```
# Counters (should be > 0)
westworld_charter_violations_total
westworld_charter_forbidden_metric_attempts_total
westworld_charter_data_revocation_events_total

# Gauges (should have values)
westworld_charter_violations_under_investigation
westworld_charter_audit_committee_size

# Histograms (should have buckets)
westworld_charter_metric_validation_latency_ns
westworld_charter_policy_load_duration_ms
```

**Query in Prometheus**: `{job="westworld-charter"}`  
**Expected Result**: 15+ metrics with data

---

## 🎓 Learning Resources During Implementation

### Grafana
- [Grafana Dashboard Design Guide](https://grafana.com/grafana/dashboards/)
- Focus on: Panels, queries, visualization types

### Prometheus
- [PromQL Documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- Focus on: rate(), histogram_quantile(), aggregation

### AlertManager
- [AlertManager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- Focus on: Routing, grouping, notification templates

### Our Documentation
- `docs/PROMETHEUS_METRICS.md` - Metric reference
- `WEST_0105_2_DASHBOARDS_PLAN.md` - Design details
- `WEST_0105_QUICK_REFERENCE.md` - Common queries

---

## ✅ Definition of "Done" for Phase 2

Phase 2 is complete when ALL of these are true:

```
Prometheus
□ 11 alert rules deployed and loaded
□ Alert rules evaluate without errors
□ At least one alert has fired (tested)
□ All metric targets show "UP"

AlertManager
□ Configuration deployed and reloaded
□ 3 Slack channels configured
□ Test notification sent successfully
□ Routing rules working correctly

Grafana
□ 2 dashboards created
□ 14 total panels across both dashboards
□ All panels display data
□ Dashboard refresh working (30s interval)
□ No "No data" messages in any panel

Integration
□ End-to-end test: Violation → Alert → Slack works
□ SLA thresholds visible on dashboards
□ All 15 metrics visible in Prometheus
□ Dashboard links work from alert notifications

Documentation
□ Team trained on using dashboards
□ Runbooks prepared for alert responses
□ Troubleshooting guide reviewed
□ Escalation procedures documented
```

---

## 🚀 Next After Phase 2

### Immediately After (30 minutes)
- [ ] Brief security team on dashboards
- [ ] Brief SRE team on alerts
- [ ] Brief on-call team on escalation procedures

### Same Day (if time permits)
- [ ] Create custom alert rules for your environment
- [ ] Tune alert thresholds based on your baseline
- [ ] Document your specific SLAs

### Next Day
- [ ] Begin WEST-0105-3 (MAPE-K Integration)
- [ ] Integrate metrics into MAPE-K Monitor phase
- [ ] Start real-time automation with observability data

---

## 💡 Pro Tips for Implementation

### For Creating Dashboards
1. Start with the simplest query first
2. Get one panel working, then add others
3. Use "Refresh" button to test queries
4. Save frequently (auto-save helps)
5. Use meaningful panel titles (people read them!)

### For Alert Rules
1. Test rules in Prometheus UI first
2. Start with one alert rule, add others
3. Use meaningful alert names
4. Include context in annotations
5. Test escalation paths manually

### For Grafana Datasource
1. Click "Save & Test" to verify connection
2. Use "Explore" to test queries before dashboards
3. Set appropriate refresh rates
4. Use templating for flexibility (advanced)

---

## 🎯 Recommended Team Assignment

| Role | Responsibility | Time |
|------|-----------------|------|
| **SRE/Infra** | Deploy Prometheus & AlertManager | 1 hour |
| **Platform Eng** | Create Grafana dashboards | 2 hours |
| **Security Eng** | Configure alert routing to teams | 30 min |
| **QA/Test** | Verify end-to-end functionality | 1 hour |

**Total Team Effort**: ~4-5 hours (can be parallel)

---

## 📞 If You Get Stuck

### Quick Help
1. Check `WEST_0105_QUICK_REFERENCE.md` for common issues
2. Check `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md` for step-by-step guide
3. Look at query examples in `docs/PROMETHEUS_METRICS.md`

### Still Stuck?
1. Check Prometheus logs: `/var/log/prometheus/prometheus.log`
2. Check AlertManager logs: `/var/log/alertmanager/alertmanager.log`
3. Check Grafana logs: `/var/log/grafana/grafana.log`
4. Use curl to test endpoints directly

---

## 🎉 Success Celebration Checklist

When Phase 2 is complete, you can celebrate:
✅ Real-time violation visibility  
✅ SLA-based performance monitoring  
✅ Automated alert routing  
✅ 15 metrics flowing to observability stack  
✅ 2 dashboards providing insight  
✅ 11 alert rules protecting the system  
✅ Team trained on new tools  

---

## 🚀 You're Ready to Start!

Everything is prepared and documented. The path is clear. The tools are ready.

**Next Step**: 
1. Choose Path A (Manual) or Path B (Automated)
2. Open `WEST_0105_2_IMPLEMENTATION_CHECKLIST.md`
3. Follow the 28 steps
4. Deploy observability layer
5. Celebrate Phase 2 completion! 🎉

---

**Questions?** Check the documentation files listed above.  
**Ready to go?** Start at Step 1 of the checklist!  
**Need help?** See troubleshooting section.

---

*Action Plan Created: 2026-01-11*  
*WEST-0105-2 Status: Ready for Implementation*  
*Time Estimate: 4-5 hours*  
*Difficulty: Intermediate (learning opportunity)*
