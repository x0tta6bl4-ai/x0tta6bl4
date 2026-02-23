---
name: mape-k-troubleshoot
description: >
  Diagnoses and fixes issues in the MAPE-K self-healing loop of x0tta6bl4.
  Use when user says "self-healing broken", "MAPE-K not working",
  "node not recovering", "healing loop stuck", "MTTR too high",
  "auto-recovery failed", or "diagnose self-healing".
metadata:
  author: x0tta6bl4
  version: 1.0.0
  category: operations
  tags: [mape-k, self-healing, troubleshooting, autonomic]
---

# MAPE-K Self-Healing Troubleshooting

## Overview

x0tta6bl4 uses the MAPE-K (Monitor-Analyze-Plan-Execute over Knowledge) autonomic
computing loop for self-healing. Target MTTR is under 3 minutes.

Key files:
- `src/core/mape_k_loop.py` - Core MAPE-K implementation
- `src/self_healing/mape_k.py` - Self-healing integration
- `src/self_healing/mape_k_integrated.py` - Full integrated loop
- `src/core/health.py` - Health check providers

## Instructions

### Step 1: Identify the Stuck Phase

The MAPE-K loop has 4 phases. Determine which phase is failing:

**Monitor phase issues:**
- Symptoms: No metrics being collected, stale data
- Check: `src/monitoring/metrics.py`, `src/monitoring/prometheus_client.py`
- Verify Prometheus scraping is active on port 9090

**Analyze phase issues:**
- Symptoms: Anomalies not detected, false positives
- Check: `src/ml/graphsage_anomaly_detector.py`
- Verify anomaly threshold (default 0.6, adjustable)
- Check if model is in observe-only mode: `src/ml/graphsage_observe_mode.py`

**Plan phase issues:**
- Symptoms: Correct detection but no recovery plan generated
- Check: Planning logic in `src/self_healing/mape_k_integrated.py`
- Verify action policies are not too restrictive

**Execute phase issues:**
- Symptoms: Plan generated but not executed
- Check: Circuit breaker state (may be open after too many failures)
- Check: SPIFFE identity valid (execution requires authenticated context)

### Step 2: Check Health Endpoints

```bash
# Overall health
curl -s http://localhost:8080/health

# Detailed status with MAPE-K state
curl -s http://localhost:8080/api/v1/mesh/status

# Prometheus metrics for MAPE-K
curl -s http://localhost:9090/api/v1/query?query=mape_k_cycle_duration_seconds
```

```python
# Programmatic health check (no server required)
from src.core.health import get_health_with_dependencies
import json
print(json.dumps(get_health_with_dependencies(), indent=2))
```

### Step 3: Review Logs

```bash
# Docker
docker-compose logs --tail=100 app | grep -i "mape\|heal\|anomal"

# Kubernetes
kubectl logs -n x0tta6bl4 deployment/proxy-api --tail=100 | grep -i "mape\|heal"

# Local
grep -i "mape\|heal\|anomal" /var/log/x0tta6bl4/app.log
```

Look for these patterns:
- `MAPE-K cycle completed` - Loop is running
- `Anomaly detected` - Analysis phase working
- `Recovery plan generated` - Planning phase working
- `Executing recovery action` - Execute phase working
- `Circuit breaker OPEN` - Executions halted (too many failures)

### Step 4: Iterative Fix

Based on the stuck phase, apply fixes:

#### Fix Monitor Phase
1. Verify metrics collection:
   ```python
   from src.monitoring.metrics import MetricsRegistry
   # MetricsRegistry exposes individual class-level Prometheus objects.
   # Check key MAPE-K counters directly:
   print(MetricsRegistry.mapek_cycles_total)       # Counter
   print(MetricsRegistry.mapek_anomalies_detected) # Counter
   print(MetricsRegistry.mapek_cycle_duration)     # Histogram
   print(MetricsRegistry.self_healing_mttr_seconds)# Histogram
   # Full list: inspect.getmembers(MetricsRegistry, lambda v: not callable(v))
   ```
2. Check Prometheus target is up: `http://localhost:9090/targets`
3. Verify health providers are registered in `src/core/health.py`

#### Fix Analyze Phase
1. Check GraphSAGE model state:
   ```python
   from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector
   detector = GraphSAGEAnomalyDetector()
   # If model is None, torch not available - falls back to rule-based
   print(f"Model: {detector.model}, Threshold: {detector.anomaly_threshold}")
   ```
2. Adjust threshold if too high (missing anomalies) or too low (false positives)
3. Check if observe mode is stuck: disable with `detector.observe_mode = False`

#### Fix Plan Phase
1. Verify recovery strategies are registered
2. Check if action quotas are exhausted
3. Verify SPIFFE identity for cross-node recovery

#### Fix Execute Phase
1. Reset circuit breaker if stuck open:
   ```python
   from src.self_healing.recovery_actions import RecoveryActionExecutor
   executor = RecoveryActionExecutor()
   # Check circuit breaker state
   print(executor.get_circuit_breaker_status())
   # {'enabled': True, 'state': 'open'/'closed'/'half_open', 'failures': N, ...}
   # Circuit breaker auto-resets after timeout; force reset by re-instantiating
   ```
2. Inspect recovery action history:
   ```python
   history = executor.get_action_history(limit=20)  # List[RecoveryResult]
   for r in history:
       print(f"{r.action_type.value}: success={r.success}, duration={r.duration_seconds:.2f}s")
   print(executor.get_success_rate())  # Overall 0.0–1.0
   ```
3. Check SPIFFE certificate expiry
4. Verify target node is reachable

### Step 5: Validate Fix

After applying fix, verify the loop completes:

```bash
# Watch for a full MAPE-K cycle
curl -s http://localhost:8080/api/v1/mesh/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'MAPE-K status: {data.get(\"mape_k_status\", \"unknown\")}')
print(f'Last cycle: {data.get(\"last_mape_k_cycle\", \"never\")}')
"
```

Re-run if the issue persists. Check each phase sequentially until
the full loop completes within the 3-minute MTTR target.

## Common Issues

### Circuit breaker stuck open
Cause: Too many consecutive recovery failures
Solution: Fix the underlying failure first, then wait for circuit breaker
half-open timeout or restart the service

### GraphSAGE model not loading
Cause: torch-geometric not installed or GPU not available
Solution: Falls back to rule-based detection automatically. Install
torch-geometric for ML-based detection: `pip install torch-geometric`

### MAPE-K cycle too slow (MTTR > 3 min)
Cause: Analysis phase taking too long, or network latency
Solution: Reduce anomaly detection batch size, increase monitoring frequency
