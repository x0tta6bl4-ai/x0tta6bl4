# 📊 Benchmark Execution Instructions

**Date:** December 30, 2025  
**Purpose:** Validate pitch claims with actual benchmark results

---

## 🎯 Overview

This document provides instructions for running benchmarks to validate the performance metrics claimed in the pitch deck.

---

## 📋 Prerequisites

1. **Environment Setup:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Ensure liboqs-python is installed
   pip install liboqs-python==0.14.1
   ```

2. **Production Environment:**
   - x0tta6bl4 service running (Docker or Kubernetes)
   - Service accessible at `http://localhost:8080` (or configure URL)
   - Mesh network with at least 3 nodes for realistic testing

---

## 🚀 Running Benchmarks

### 1. Performance Benchmarks (MTTD, MTTR, PQC Handshake)

**File:** `tests/performance/benchmark_pitch_metrics.py`

#### Run All Benchmarks:
```bash
python tests/performance/benchmark_pitch_metrics.py --all \
  --iterations 10 \
  --pqc-iterations 1000 \
  --output-dir benchmarks/results
```

#### Run Individual Benchmarks:

**MTTD Benchmark:**
```bash
python tests/performance/benchmark_pitch_metrics.py --mttd \
  --iterations 10 \
  --output-dir benchmarks/results
```

**MTTR Benchmark:**
```bash
python tests/performance/benchmark_pitch_metrics.py --mttr \
  --iterations 10 \
  --output-dir benchmarks/results
```

**PQC Handshake Benchmark:**
```bash
python tests/performance/benchmark_pitch_metrics.py --pqc \
  --pqc-iterations 1000 \
  --output-dir benchmarks/results
```

#### Expected Results:

| Metric | Target | Industry | Improvement |
|--------|--------|----------|-------------|
| **MTTD** | 20s | 5-10 min | 15-30x faster |
| **MTTR** | <3 min | 15-30 min | 5-10x faster |
| **PQC Handshake p95** | 0.81ms | 376ms (RSA-2048) | 464x faster |

#### Output:
- JSON results saved to `benchmarks/results/pitch_metrics_benchmark_YYYYMMDD_HHMMSS.json`
- Summary printed to console
- Pass/fail status for each metric

---

### 2. Accuracy Validation Tests

**File:** `tests/validation/test_accuracy_validation.py`

#### Run Accuracy Tests:
```bash
# Using pytest
pytest tests/validation/test_accuracy_validation.py -v

# Or directly
python tests/validation/test_accuracy_validation.py \
  --output-dir benchmarks/results
```

#### Expected Results:

| Metric | Target | Industry | Improvement |
|--------|--------|----------|-------------|
| **Anomaly Detection Accuracy** | 94-98% | 70-80% | +14-18% |
| **Root Cause Accuracy** | >90% | 50-60% | +30-40% |

#### Output:
- JSON results saved to `benchmarks/results/accuracy_validation_YYYYMMDD_HHMMSS.json`
- Detailed metrics: accuracy, precision, recall, F1 score
- Pass/fail status

---

### 3. FIPS 203/204 Compliance Tests

**File:** `tests/compliance/test_fips203_compliance.py`

#### Run Compliance Tests:
```bash
pytest tests/compliance/test_fips203_compliance.py -v
```

#### Expected Results:
- ✅ ML-KEM-768 key generation and encapsulation
- ✅ ML-DSA-65 signature generation and verification
- ✅ Correct key sizes per FIPS 203/204 specifications
- ✅ Legacy name compatibility

---

## 📊 Interpreting Results

### Performance Benchmarks

**MTTD Results:**
```json
{
  "mttd": {
    "mean": 18.5,
    "median": 19.2,
    "min": 15.3,
    "max": 22.1,
    "target": 20.0,
    "passed": true
  }
}
```

**MTTR Results:**
```json
{
  "mttr": {
    "mean": 165.0,
    "median": 160.0,
    "min": 120.0,
    "max": 180.0,
    "target": 180.0,
    "passed": true
  }
}
```

**PQC Handshake Results:**
```json
{
  "pqc_handshake": {
    "mean": 0.75,
    "median": 0.72,
    "p95": 0.81,
    "p99": 0.95,
    "target_p95": 0.81,
    "passed": true
  }
}
```

### Accuracy Validation

**Anomaly Detection:**
```json
{
  "anomaly_detection": {
    "accuracy": 0.96,
    "precision": 0.98,
    "recall": 0.94,
    "f1_score": 0.96,
    "target": 0.94,
    "passed": true
  }
}
```

**Root Cause:**
```json
{
  "root_cause": {
    "accuracy": 0.92,
    "target": 0.90,
    "passed": true
  }
}
```

---

## 🔄 Updating Pitch Decks

After running benchmarks and collecting results:

### 1. Update PITCH.md

Replace placeholder values with actual results:

```markdown
### Production Metrics (Validated)

- **MTTD**: 18.5s average (validated: [date]) ✅
- **MTTR**: 165s average (validated: [date]) ✅
- **PQC Handshake**: 0.75ms average, 0.81ms p95 (validated: [date]) ✅
- **Anomaly Detection Accuracy**: 96% (validated: [date]) ✅
```

### 2. Update PITCH_RU.md

Same updates in Russian version.

### 3. Add Validation Badges

Add to README.md:
```markdown
[![Benchmarks](https://img.shields.io/badge/Benchmarks-Validated-success.svg)](benchmarks/results/)
[![Accuracy](https://img.shields.io/badge/Accuracy-96%25-success.svg)](tests/validation/)
```

---

## 📝 Benchmark Report Template

After running benchmarks, create a report:

```markdown
# Benchmark Results - [Date]

## Environment
- OS: [OS version]
- Python: [version]
- liboqs: [version]
- Nodes: [number]

## Results

### MTTD
- Mean: [X]s
- Target: 20s
- Status: ✅ PASS / ❌ FAIL

### MTTR
- Mean: [X]s
- Target: 180s
- Status: ✅ PASS / ❌ FAIL

### PQC Handshake
- p95: [X]ms
- Target: 0.81ms
- Status: ✅ PASS / ❌ FAIL

### Accuracy
- Anomaly Detection: [X]%
- Target: 94%
- Status: ✅ PASS / ❌ FAIL
```

---

## ⚠️ Troubleshooting

### liboqs Not Available
```bash
# Install liboqs-python
pip install liboqs-python==0.14.1

# Or build from source (see liboqs documentation)
```

### Service Not Running
```bash
# Start service
docker compose up -d

# Or
kubectl apply -f k8s/
```

### Benchmark Timeout
- Increase timeout values in benchmark code
- Check service health: `curl http://localhost:8080/health`
- Verify network connectivity

---

## 📚 Additional Resources

- **FIPS 203/204 Compliance:** `tests/compliance/test_fips203_compliance.py`
- **Performance Benchmarks:** `tests/performance/benchmark_pitch_metrics.py`
- **Accuracy Validation:** `tests/validation/test_accuracy_validation.py`
- **Algorithm Naming:** `ALGORITHM_NAMING_STANDARD.md`

---

*Last Updated: December 30, 2025*

