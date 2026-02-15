# Performance Metrics Validation Plan

## Overview
This document outlines the plan for validating performance metrics in a staging environment.

## Metrics to Validate

### 1. PQC Handshake Performance
- **Target:** 0.81ms p95
- **Measurement:** Time for key encapsulation and decapsulation
- **Tool:** Custom benchmark script
- **Location:** `benchmarks/pqc_handshake_benchmark.py`

### 2. Anomaly Detection Accuracy
- **Target:** 96% accuracy
- **Measurement:** F1 score on labeled dataset
- **Tool:** GraphSAGE evaluation script
- **Location:** `src/ml/graphsage_anomaly_detector.py`

### 3. GraphSAGE Accuracy
- **Target:** 97% accuracy
- **Measurement:** Node classification accuracy
- **Tool:** GraphSAGE evaluation
- **Location:** `src/ml/graphsage_anomaly_detector.py`

### 4. MTTD (Mean Time To Detect)
- **Target:** 18.5s
- **Measurement:** Time from anomaly injection to detection
- **Tool:** MAPE-K orchestrator metrics
- **Location:** `src/mape_k_orchestrator.py`

### 5. MTTR (Mean Time To Recover)
- **Target:** 2.75min
- **Measurement:** Time from detection to recovery
- **Tool:** MAPE-K recovery planner
- **Location:** `src/p03_recovery/recovery_executor.py`

## Validation Environment

### Staging Setup
```bash
# 1. Deploy to staging
kubectl config use-context staging
helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 -f helm/x0tta6bl4/values-staging.yaml

# 2. Wait for pods to be ready
kubectl rollout status deployment/x0tta6bl4-staging -n staging

# 3. Port-forward for local testing
kubectl port-forward svc/x0tta6bl4-staging -n staging 8080:8080
```

### Load Generation
```bash
# Use k6 for load testing
k6 run benchmarks/load_tests/api_load_test.js

# Use locust for user simulation
locust -f benchmarks/load_tests/user_simulation.py --host=http://localhost:8080
```

## Validation Scripts

### PQC Handshake Benchmark
```python
import time
from src.security.post_quantum import LibOQSBackend

def benchmark_pqc_handshake(iterations=1000):
    backend = LibOQSBackend()
    
    # Key generation
    start = time.time()
    for _ in range(iterations):
        public_key, private_key = backend.generate_keypair()
    keygen_time = (time.time() - start) / iterations
    
    # Encapsulation
    start = time.time()
    for _ in range(iterations):
        ciphertext, shared_secret = backend.encapsulate(public_key)
    encap_time = (time.time() - start) / iterations
    
    # Decapsulation
    start = time.time()
    for _ in range(iterations):
        shared_secret = backend.decapsulate(ciphertext, private_key)
    decap_time = (time.time() - start) / iterations
    
    return {
        "keygen_ms": keygen_time * 1000,
        "encap_ms": encap_time * 1000,
        "decap_ms": decap_time * 1000,
        "total_ms": (keygen_time + encap_time + decap_time) * 1000
    }
```

### Anomaly Detection Validation
```python
from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

def validate_anomaly_detection(test_data, labels):
    detector = GraphSAGEAnomalyDetector()
    predictions = detector.predict(test_data)
    
    f1 = f1_score(labels, predictions)
    precision = precision_score(labels, predictions)
    recall = recall_score(labels, predictions)
    
    return {
        "f1_score": f1,
        "precision": precision,
        "recall": recall,
        "target_f1": 0.96,
        "passed": f1 >= 0.96
    }
```

### MTTD/MTTR Validation
```python
from src.mape_k_orchestrator import MAPEKOrchestrator
import time

def validate_mttd_mttr():
    orchestrator = MAPEKOrchestrator()
    
    # Inject anomaly
    start_time = time.time()
    orchestrator.inject_anomaly("node_failure")
    
    # Wait for detection
    detection_time = None
    while detection_time is None:
        metrics = orchestrator.get_metrics()
        if metrics.get("anomaly_detected"):
            detection_time = time.time()
    
    mttd = detection_time - start_time
    
    # Wait for recovery
    recovery_time = None
    while recovery_time is None:
        metrics = orchestrator.get_metrics()
        if metrics.get("system_recovered"):
            recovery_time = time.time()
    
    mttr = recovery_time - detection_time
    
    return {
        "mttd_seconds": mttd,
        "mttd_target": 18.5,
        "mttr_seconds": mttr,
        "mttr_target": 165,  # 2.75min
        "mttd_passed": mttd <= 18.5,
        "mttr_passed": mttr <= 165
    }
```

## Success Criteria

### All Metrics Must Pass
- ✅ PQC Handshake <= 0.81ms p95
- ✅ Anomaly Detection F1 >= 0.96
- ✅ GraphSAGE Accuracy >= 0.97
- ✅ MTTD <= 18.5s
- ✅ MTTR <= 2.75min

### Additional Requirements
- ✅ No errors during 24h stability test
- ✅ <1% error rate under load
- ✅ <500ms p95 response time
- ✅ >99.9% uptime

## Execution Timeline

### Week 1: Setup
- Deploy staging environment
- Configure monitoring
- Set up load generation tools

### Week 2: PQC Validation
- Run PQC handshake benchmarks
- Validate against target
- Document results

### Week 3: AI/ML Validation
- Validate anomaly detection
- Validate GraphSAGE accuracy
- Document results

### Week 4: MAPE-K Validation
- Validate MTTD
- Validate MTTR
- Document results

### Week 5: Integration Testing
- Run 24h stability test
- Run load tests
- Document results

## Reporting

### Validation Report Format
```markdown
# Performance Validation Report

Date: YYYY-MM-DD
Environment: Staging

## Results

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| PQC Handshake | 0.81ms | X.XXms | ✅/❌ |
| Anomaly Detection | 96% | XX% | ✅/❌ |
| GraphSAGE Accuracy | 97% | XX% | ✅/❌ |
| MTTD | 18.5s | XXs | ✅/❌ |
| MTTR | 2.75min | XXmin | ✅/❌ |

## Conclusion

Overall Status: ✅ PASSED / ❌ FAILED

Recommendations: ...
```
