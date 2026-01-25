# 🛠️ Production Toolkit Guide

**Версия:** 3.0.0  
**Дата:** 30 ноября 2025

---

## 🚀 QUICK START

```bash
# All-in-one toolkit
bash scripts/production_toolkit.sh {tool} [options]
```

---

## 🛠️ AVAILABLE TOOLS

### 1. Health Check Dashboard
**Tool:** `health`

Real-time health status dashboard.

```bash
bash scripts/production_toolkit.sh health
bash scripts/production_toolkit.sh health --interval 5
```

**Features:**
- Health endpoint status
- Metrics endpoint status
- Mesh peers status
- Real-time updates

---

### 2. Production Monitoring
**Tool:** `monitor`

Monitor production deployment with alerting.

```bash
bash scripts/production_toolkit.sh monitor
bash scripts/production_toolkit.sh monitor --duration 60 --interval 10
```

**Features:**
- Real-time metrics monitoring
- Alert detection
- Metrics history
- Automatic alerting

---

### 3. Metrics Collection
**Tool:** `collect`

Collect metrics for analysis.

```bash
bash scripts/production_toolkit.sh collect
bash scripts/production_toolkit.sh collect --duration 30 --interval 10
```

**Features:**
- Continuous metrics collection
- Automatic file saving
- Timestamped metrics
- JSON format

---

### 4. Baseline Comparison
**Tool:** `compare`

Compare current metrics against baseline.

```bash
bash scripts/production_toolkit.sh compare
bash scripts/production_toolkit.sh compare --metrics metrics_20250101.json
```

**Features:**
- Automatic regression detection
- Performance comparison
- Detailed diff report
- Recommendations

---

### 5. Auto-Rollback Monitor
**Tool:** `rollback`

Monitor and automatically trigger rollback.

```bash
bash scripts/production_toolkit.sh rollback
bash scripts/production_toolkit.sh rollback --interval 10
```

**Features:**
- Automatic rollback triggers
- Health monitoring
- Error rate monitoring
- Latency monitoring

---

### 6. Deployment Orchestration
**Tool:** `deploy`

Manage production deployment.

```bash
bash scripts/production_toolkit.sh deploy canary
bash scripts/production_toolkit.sh deploy full
bash scripts/production_toolkit.sh deploy all
```

**Features:**
- Canary deployment
- Gradual rollout
- Full deployment
- Interactive confirmations

---

### 7. Security Audit
**Tool:** `audit`

Run security audit checklist.

```bash
bash scripts/production_toolkit.sh audit
```

**Features:**
- CVE patches check
- PQC fallback check
- Timing attack protection
- DoS protection
- Policy Engine check

---

### 8. Performance Baseline
**Tool:** `baseline`

Establish performance baseline.

```bash
bash scripts/production_toolkit.sh baseline
```

**Features:**
- Performance testing
- Baseline metrics
- Automatic saving
- Pass/fail criteria

---

## 📊 USAGE EXAMPLES

### During Canary Deployment
```bash
# Terminal 1: Deploy canary
bash scripts/production_toolkit.sh deploy canary

# Terminal 2: Monitor
bash scripts/production_toolkit.sh monitor --duration 15

# Terminal 3: Health dashboard
bash scripts/production_toolkit.sh health --interval 5
```

### During Full Deployment
```bash
# Deploy
bash scripts/production_toolkit.sh deploy full

# Monitor with auto-rollback
bash scripts/production_toolkit.sh rollback --interval 10 &

# Collect metrics
bash scripts/production_toolkit.sh collect --duration 1440 --interval 60
```

### Post-Deployment Analysis
```bash
# Compare against baseline
bash scripts/production_toolkit.sh compare --metrics metrics_latest.json

# Review collected metrics
cat metrics_*.json | jq '.'
```

---

## 🔧 ADVANCED USAGE

### Custom Monitoring
```bash
# Monitor specific URL
python3 scripts/production_monitor.py --url http://production.example.com --duration 120
```

### Metrics Analysis
```bash
# Collect metrics
python3 scripts/metrics_collector.py --duration 60 --interval 10

# Compare
python3 scripts/compare_baseline.py --metrics metrics_20250101_120000.json
```

### Health Dashboard
```bash
# Custom interval
python3 scripts/health_check_dashboard.py --interval 3
```

---

## 📝 NOTES

- All tools support `--help` for detailed options
- Metrics files are automatically timestamped
- Baseline comparison requires `baseline_metrics.json`
- Auto-rollback requires deployment system integration

---

**Last Updated:** 30 ноября 2025

