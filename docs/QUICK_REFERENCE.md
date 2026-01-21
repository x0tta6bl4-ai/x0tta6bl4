# ⚡ Quick Reference Guide

**Версия:** 3.0.0  
**Дата:** 30 ноября 2025

---

## 🚀 QUICK COMMANDS

### Health & Status
```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Health dashboard
bash scripts/production_toolkit.sh health
```

### Deployment
```bash
# Canary deployment
bash scripts/production_toolkit.sh deploy canary

# Full deployment
bash scripts/production_toolkit.sh deploy all

# Staging deployment
python3 scripts/staging_deployment.py
```

### Monitoring
```bash
# Production monitoring
bash scripts/production_toolkit.sh monitor --duration 60

# Metrics collection
bash scripts/production_toolkit.sh collect --duration 30

# Auto-rollback
bash scripts/production_toolkit.sh rollback
```

### Testing
```bash
# Security audit
bash scripts/production_toolkit.sh audit

# Performance baseline
bash scripts/production_toolkit.sh baseline

# Load test
python3 scripts/run_load_test.py

# Chaos tests
python3 tests/chaos/staging_chaos_test.py
```

### Comparison
```bash
# Compare against baseline
bash scripts/production_toolkit.sh compare
```

---

## 🚨 EMERGENCY COMMANDS

### Rollback
```bash
# Manual rollback
docker-compose -f staging/docker-compose.staging.yml down
docker-compose -f staging/docker-compose.staging.yml up -d --scale control-plane=1

# Auto-rollback monitor
bash scripts/production_toolkit.sh rollback
```

### Service Restart
```bash
# Restart service
docker restart x0tta6bl4-staging

# Check logs
docker logs x0tta6bl4-staging --tail 100
```

### Health Check
```bash
# Quick health check
curl -f http://localhost:8080/health || echo "Service down!"

# Detailed status
bash scripts/production_toolkit.sh health
```

---

## 📊 KEY METRICS

### Targets
- **Error Rate:** < 0.1%
- **Latency P95:** < 100ms
- **Throughput:** > 6,800 req/sec
- **Memory:** < 2.4GB
- **CPU:** < 80%

### Baseline (Locked)
- Success Rate: 100.00%
- Latency P95: 40.38ms
- Memory: 49.12MB
- CPU: 6.79%

---

## 🔗 IMPORTANT LINKS

### Documentation
- Launch Readiness: `LAUNCH_READINESS_REPORT.md`
- Deployment Guide: `docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md`
- On-Call Runbook: `docs/team/ON_CALL_RUNBOOK.md`
- Incident Response: `docs/team/INCIDENT_RESPONSE_PLAN.md`

### Scripts
- Production Toolkit: `scripts/production_toolkit.sh`
- Deployment: `scripts/run_week2_deployment.sh`
- Validation: `scripts/run_sprint1.sh`

---

## 📞 ESCALATION

### Level 1: On-Call Engineer
- Monitor metrics
- Execute runbook
- Trigger rollback if needed

### Level 2: Team Lead
- Coordinate response
- Make decisions
- Communicate

### Level 3: CTO
- Executive decisions
- External communication

---

**Last Updated:** 30 ноября 2025

