# 🧪 Beta Testing Guide

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4  
**Цель:** Руководство для beta testers

---

## 📋 Overview

Beta testing программа для x0tta6bl4 v3.4 позволяет протестировать систему в реальных условиях перед коммерческим запуском.

**Цель:** Привлечь 20-50 beta testers для тестирования в течение 2-3 месяцев.

---

## 🎯 Что Тестировать

### Core Functionality
- [ ] Mesh network connectivity
- [ ] Post-Quantum Cryptography (PQC) handshakes
- [ ] SPIFFE/SPIRE identity management
- [ ] MAPE-K self-healing cycles
- [ ] Health check endpoints

### Advanced Features
- [ ] Federated Learning (если доступно)
- [ ] RAG Pipeline (если доступно)
- [ ] GraphSAGE anomaly detection
- [ ] eBPF observability (если доступно)

### Infrastructure
- [ ] Kubernetes deployment
- [ ] Monitoring (Prometheus/Grafana)
- [ ] Alerting
- [ ] Logging

---

## 🚀 Getting Started

### 1. Access Beta Environment

```bash
# Get beta access credentials
# (Provided separately to beta testers)

# Connect to staging cluster
kubectl config use-context staging
```

### 2. Check System Status

```bash
# Port forward to service
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4 8000:8000

# Check health
curl http://localhost:8000/health

# Check dependencies
curl http://localhost:8000/health/dependencies
```

### 3. Run Basic Tests

```bash
# Health check
curl http://localhost:8000/health | jq '.'

# Dependencies status
curl http://localhost:8000/health/dependencies | jq '.'

# Metrics
curl http://localhost:8000/metrics
```

---

## 📊 Test Scenarios

### Scenario 1: Basic Connectivity

**Goal:** Verify basic mesh network connectivity

**Steps:**
1. Deploy 2 nodes
2. Verify beacon exchange
3. Check mesh topology
4. Verify PQC handshakes

**Expected:**
- Nodes can communicate
- Beacons exchanged successfully
- PQC handshakes complete

---

### Scenario 2: Self-Healing

**Goal:** Test MAPE-K self-healing capabilities

**Steps:**
1. Deploy system
2. Introduce failure (kill pod, network partition)
3. Observe MAPE-K cycle
4. Verify automatic recovery

**Expected:**
- Failure detected within 20s
- Recovery action executed
- System returns to healthy state

---

### Scenario 3: Dependency Health

**Goal:** Test graceful degradation

**Steps:**
1. Deploy with all dependencies
2. Remove optional dependency (e.g., torch)
3. Check health status
4. Verify system continues working

**Expected:**
- Health check shows degraded status
- System continues operating
- Warnings logged appropriately

---

### Scenario 4: Load Testing

**Goal:** Test under load

**Steps:**
1. Deploy system
2. Run load test script
3. Monitor metrics
4. Check for performance issues

**Expected:**
- System handles load
- Response times acceptable
- No errors under load

---

## 🐛 Reporting Issues

### Issue Template

```markdown
**Environment:**
- Version: 3.4.0
- Namespace: x0tta6bl4-staging
- Node: <node-id>

**Issue:**
- Description: <what happened>
- Steps to reproduce: <steps>
- Expected: <expected behavior>
- Actual: <actual behavior>

**Logs:**
```
<paste logs>
```

**Health Status:**
```
<paste health check output>
```
```

### Reporting Channels

- **GitHub Issues:** https://github.com/x0tta6bl4/x0tta6bl4/issues
- **Email:** beta@x0tta6bl4.io
- **Slack:** #beta-testing channel

---

## 📈 Metrics to Monitor

### Application Metrics
- Request rate
- Response time (p95, p99)
- Error rate
- Health check status

### Infrastructure Metrics
- CPU usage
- Memory usage
- Network throughput
- Pod restarts

### Security Metrics
- PQC handshake success rate
- SPIFFE certificate expiry
- Failed authentication attempts

---

## ✅ Success Criteria

### Beta Testing Success

- [ ] 20+ active beta testers
- [ ] System stable for 30+ days
- [ ] <1% error rate
- [ ] <500ms p95 latency
- [ ] All critical issues resolved
- [ ] Positive feedback from 80%+ testers

---

## 🎁 Beta Tester Benefits

- Early access to advanced features
- Direct feedback channel to developers
- Recognition in release notes
- Priority support
- Potential discounts on commercial launch

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

