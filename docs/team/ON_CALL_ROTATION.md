# On-Call Rotation Plan для x0tta6bl4
**Дата:** 2026-01-08  
**Версия:** 3.4.0-fixed2  
**Статус:** ✅ **ACTIVE** (Beta Launch)

---

## 🎯 Overview

**Цель:** Обеспечить 24/7 покрытие для критических инцидентов во время beta launch.

**Принцип:** Простота и эффективность для малой команды.

---

## 📅 Rotation Schedule

### Week 1 (Jan 8-14, 2026)

| День | Primary On-Call | Backup On-Call | Notes |
|------|----------------|----------------|-------|
| Jan 8 (Wed) | Engineer 1 | Engineer 2 | Beta Launch Prep |
| Jan 9 (Thu) | Engineer 2 | Engineer 1 | Beta Launch Prep |
| Jan 10 (Fri) | Engineer 1 | Engineer 2 | Production Readiness Review |
| Jan 11 (Sat) | Engineer 2 | Engineer 1 | **Beta Launch Day 1** |
| Jan 12 (Sun) | Engineer 1 | Engineer 2 | **Beta Launch Day 2** |
| Jan 13 (Mon) | Engineer 2 | Engineer 1 | Sales Outreach |
| Jan 14 (Tue) | Engineer 1 | Engineer 2 | Review Week 1 |

### Week 2+ (After Beta Launch)

**Rotation Pattern:** Weekly rotation (Monday to Monday)

| Week | Primary On-Call | Backup On-Call |
|------|----------------|----------------|
| Week 2 | Engineer 1 | Engineer 2 |
| Week 3 | Engineer 2 | Engineer 1 |
| Week 4 | Engineer 1 | Engineer 2 |

**Note:** Adjust based on team size and availability.

---

## 👥 Team Members

### Current Team (Beta Phase)

**Engineer 1:**
- Primary contact: [TO_BE_FILLED]
- Backup contact: [TO_BE_FILLED]
- Availability: 24/7 during beta launch

**Engineer 2:**
- Primary contact: [TO_BE_FILLED]
- Backup contact: [TO_BE_FILLED]
- Availability: 24/7 during beta launch

**Team Lead:**
- Escalation contact: [TO_BE_FILLED]
- Availability: Business hours + critical escalations

---

## 📱 Communication Channels

### Primary Channels

1. **Telegram:**
   - Group: `@x0tta6bl4_oncall`
   - Critical alerts: Direct messages
   - Status updates: Group chat

2. **Email:**
   - On-call: `oncall@x0tta6bl4.com`
   - Escalation: `team-lead@x0tta6bl4.com`

3. **Phone (Escalation Only):**
   - Team Lead: [TO_BE_FILLED]
   - CTO: [TO_BE_FILLED]

### Alert Routing

- **Critical (SEV-1):** Telegram + Email + Phone (if not acknowledged in 15 min)
- **High (SEV-2):** Telegram + Email
- **Medium (SEV-3):** Telegram
- **Low (SEV-4):** Daily summary email

---

## ⏰ Response Times

### Acknowledgment Times

| Severity | Acknowledgment Time | Escalation Time |
|----------|---------------------|-----------------|
| SEV-1 (Critical) | 5 minutes | 15 minutes |
| SEV-2 (High) | 15 minutes | 1 hour |
| SEV-3 (Medium) | 1 hour | 4 hours |
| SEV-4 (Low) | 1 business day | N/A |

### Resolution Times

| Severity | Target Resolution Time |
|----------|------------------------|
| SEV-1 (Critical) | 4 hours |
| SEV-2 (High) | 24 hours |
| SEV-3 (Medium) | 72 hours |
| SEV-4 (Low) | 1 week |

---

## 🔄 Handoff Procedure

### Daily Handoff (9:00 AM)

**Format:**
```
=== On-Call Handoff - [Date] ===

Primary: [Name]
Backup: [Name]

Active Incidents:
- [Incident ID] - [Status] - [Severity]

Recent Alerts:
- [Alert Name] - [Time] - [Status]

Notes:
- [Any important context]

Next Handoff: [Date] at 9:00 AM
```

### Weekly Handoff (Monday 9:00 AM)

**Format:**
```
=== Weekly On-Call Handoff - Week [N] ===

Previous Week On-Call: [Name]
Current Week On-Call: [Name]

Week Summary:
- Total Alerts: [N]
- Critical Incidents: [N]
- Resolved: [N]
- Open: [N]

Key Learnings:
- [Learning 1]
- [Learning 2]

Action Items:
- [Action 1]
- [Action 2]
```

---

## 📋 On-Call Checklist

### Start of Shift

- [ ] Review active incidents
- [ ] Check monitoring dashboards
- [ ] Verify alert channels (Telegram, Email)
- [ ] Review recent deployments
- [ ] Check system health metrics

### During Shift

- [ ] Acknowledge alerts within SLA
- [ ] Update incident tickets
- [ ] Communicate status updates
- [ ] Document actions taken
- [ ] Escalate when needed

### End of Shift

- [ ] Complete handoff notes
- [ ] Update incident tickets
- [ ] Document learnings
- [ ] Transfer to next on-call

---

## 🚨 Escalation Path

### Level 1: On-Call Engineer
- **Responsibility:** Initial response, triage, mitigation
- **Authority:** Execute runbooks, restart services, rollback

### Level 2: Team Lead
- **Trigger:** SEV-1 not resolved in 15 min, SEV-2 not resolved in 1 hour
- **Responsibility:** Coordinate response, make decisions
- **Authority:** Approve major changes, coordinate with stakeholders

### Level 3: CTO
- **Trigger:** SEV-1 not resolved in 1 hour, security breach, data loss
- **Responsibility:** Strategic decisions, external communication
- **Authority:** Approve emergency changes, customer communication

---

## 📊 Metrics & Reporting

### Daily Metrics

- Total alerts received
- Alerts by severity
- Response times (acknowledgment, resolution)
- Incidents resolved
- Incidents escalated

### Weekly Report

- Weekly summary
- Trends and patterns
- Lessons learned
- Action items
- Improvements needed

---

## 🛠️ Tools & Resources

### Monitoring

- **Prometheus:** http://localhost:9090 (port-forward)
- **Grafana:** http://localhost:3000 (port-forward)
- **Health Endpoint:** http://localhost:8080/health
- **Metrics Endpoint:** http://localhost:8080/metrics

### Incident Management

- **Incident Tracking:** [TO_BE_FILLED]
- **Runbooks:** `docs/operations/runbooks/`
- **Incident Response Plan:** `docs/team/INCIDENT_RESPONSE_PLAN.md`

### Communication

- **Telegram Bot:** [TO_BE_FILLED]
- **Email:** oncall@x0tta6bl4.com
- **Status Page:** [TO_BE_FILLED]

---

## ✅ Beta Launch Specific

### Jan 11-12, 2026 (Beta Launch Days)

**Special Arrangements:**
- **Extended Coverage:** Both engineers on-call simultaneously
- **Response Time:** 5 minutes for all alerts
- **Communication:** Hourly status updates
- **Escalation:** Immediate escalation to Team Lead for any issues

### Post-Launch (Jan 13+)

**Normal Operations:**
- Standard rotation schedule
- Standard response times
- Weekly handoff meetings

---

## 📝 Notes

- **Beta Phase:** Enhanced coverage during first 2 weeks
- **Holidays:** Coordinate coverage in advance
- **Vacation:** Ensure backup coverage
- **Training:** New team members shadow for 1 week before primary on-call

---

**Last Updated:** 2026-01-08  
**Next Review:** After first month of beta launch  
**Owner:** Team Lead

