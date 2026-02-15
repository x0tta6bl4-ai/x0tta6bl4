# Chaos Mesh Design for x0tta6bl4 MAPE-K Self-Healing

## Overview

This document defines chaos engineering scenarios to validate the MAPE-K self-healing loop
in the x0tta6bl4 mesh network.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Chaos Mesh Controller                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ NetworkChaos│  │  PodChaos   │  │ StressChaos │  │  IOChaos    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└─────────┼────────────────┼────────────────┼────────────────┼────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      x0tta6bl4 Mesh Network                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  mesh-node-1 │◄─►│  mesh-node-2 │◄─►│  mesh-node-3 │               │
│  │  (MAPE-K)    │  │  (MAPE-K)    │  │  (MAPE-K)    │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│         │                │                │                          │
│         ▼                ▼                ▼                          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Prometheus + Grafana                          ││
│  │  - x0tta6bl4_pqc_verifications_total                            ││
│  │  - x0tta6bl4_pqc_anomalies_total                                ││
│  │  - x0tta6bl4_mapek_healing_actions_total                        ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Chaos Scenarios

### Scenario 1: Network Partition (Split Brain)

**Objective**: Test MAPE-K response to network partitions between mesh nodes.

**Chaos Type**: `NetworkChaos` - partition

**Injection**:
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: mesh-network-partition
  namespace: x0tta6bl4
spec:
  action: partition
  mode: all
  selector:
    namespaces:
      - x0tta6bl4
    labelSelectors:
      app: mesh-node
  direction: both
  target:
    selector:
      namespaces:
        - x0tta6bl4
      labelSelectors:
        zone: zone-b
    mode: all
  duration: "60s"
```

**Expected MAPE-K Response**:
| Phase | Action |
|-------|--------|
| Monitor | Detect peer heartbeat failures, increment `mesh_peer_unreachable` counter |
| Analyze | Identify network partition pattern (multiple peers unreachable simultaneously) |
| Plan | Select alternative routing paths via BATMAN-adv, prepare for split-brain resolution |
| Execute | Activate backup routes, mark affected sessions for re-verification |
| Knowledge | Record partition event, update routing preference weights |

**Verification Criteria**:
- [ ] `x0tta6bl4_mapek_anomalies_detected{type="network_partition"}` incremented
- [ ] `x0tta6bl4_mesh_routes_recalculated` incremented
- [ ] No data loss after partition heals
- [ ] PQC sessions re-established within 30s of partition healing

---

### Scenario 2: PQC Verification Failures (Simulated Attack)

**Objective**: Test MAPE-K response to repeated PQC signature verification failures.

**Chaos Type**: Custom `PQCChaos` via sidecar injection

**Injection Method**:
Inject invalid signatures into mesh traffic via eBPF tc program.

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pqc-verification-failure
  namespace: x0tta6bl4
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - x0tta6bl4
    labelSelectors:
      component: pqc-verifier
  duration: "30s"
```

**Alternative - Script Injection**:
```python
# chaos_pqc_inject.py - Run inside mesh-node pod
import secrets
from src.network.ebpf.pqc_verification_daemon import PQCVerificationEvent

def inject_invalid_signatures(daemon, count=10):
    """Inject invalid PQC signatures to trigger MAPE-K response"""
    for i in range(count):
        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=b"INVALID" * 100,  # Invalid signature
            payload_hash=secrets.token_bytes(32),
            pubkey_id=secrets.token_bytes(16),  # Unknown pubkey
            timestamp=time.time_ns()
        )
        daemon.submit_event(event)
        time.sleep(0.1)
```

**Expected MAPE-K Response**:
| Phase | Action |
|-------|--------|
| Monitor | `pqc_verifications_failed` counter spikes |
| Analyze | Detect HIGH_FAILURE_RATE anomaly, identify source session/peer |
| Plan | Generate `invalidate_session` and `rotate_keys` actions |
| Execute | Invalidate compromised sessions, trigger PQC key rotation |
| Knowledge | Record attack pattern, update threat intelligence |

**Verification Criteria**:
- [ ] `x0tta6bl4_pqc_anomalies_total{type="verification_failed"}` > 5
- [ ] `x0tta6bl4_pqc_anomalies_total{type="high_failure_rate"}` = 1
- [ ] Session invalidation triggered within 5s
- [ ] Key rotation initiated if failures > threshold

---

### Scenario 3: Node Crash and Recovery

**Objective**: Test MAPE-K self-healing when mesh nodes crash unexpectedly.

**Chaos Type**: `PodChaos` - pod-kill

**Injection**:
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: mesh-node-crash
  namespace: x0tta6bl4
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - x0tta6bl4
    labelSelectors:
      app: mesh-node
  duration: "1m"
  scheduler:
    cron: "@every 5m"  # Recurring chaos
```

**Expected MAPE-K Response**:
| Phase | Action |
|-------|--------|
| Monitor | Kubernetes detects pod termination, peer nodes detect heartbeat loss |
| Analyze | Correlate pod death with session failures, classify as node crash |
| Plan | Redistribute load, prepare session migration |
| Execute | Migrate active sessions to healthy nodes, update routing tables |
| Knowledge | Record node failure, update availability metrics |

**Verification Criteria**:
- [ ] Pod restarts within Kubernetes restart policy
- [ ] Sessions migrated to surviving nodes
- [ ] No request failures visible to external clients
- [ ] MAPE-K healing action logged

---

### Scenario 4: Latency Injection (Degraded Network)

**Objective**: Test MAPE-K adaptive response to network latency.

**Chaos Type**: `NetworkChaos` - delay

**Injection**:
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: mesh-latency-injection
  namespace: x0tta6bl4
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - x0tta6bl4
    labelSelectors:
      app: mesh-node
  delay:
    latency: "200ms"
    jitter: "50ms"
    correlation: "50"
  duration: "2m"
```

**Expected MAPE-K Response**:
| Phase | Action |
|-------|--------|
| Monitor | `pqc_verification_latency_seconds` histogram shifts right |
| Analyze | Detect latency SLO violation, identify affected routes |
| Plan | Adjust timeouts, select lower-latency paths |
| Execute | Update routing weights, extend verification timeouts |
| Knowledge | Record latency patterns, correlate with network topology |

**Verification Criteria**:
- [ ] Histogram buckets show increased latency
- [ ] No verification timeouts (adaptive timeout adjustment)
- [ ] Route preference updated after sustained latency

---

### Scenario 5: CPU/Memory Stress (Resource Exhaustion)

**Objective**: Test MAPE-K response to resource pressure on mesh nodes.

**Chaos Type**: `StressChaos`

**Injection**:
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: mesh-resource-stress
  namespace: x0tta6bl4
spec:
  mode: one
  selector:
    namespaces:
      - x0tta6bl4
    labelSelectors:
      app: mesh-node
  stressors:
    cpu:
      workers: 4
      load: 80
    memory:
      workers: 2
      size: "512MB"
  duration: "1m"
```

**Expected MAPE-K Response**:
| Phase | Action |
|-------|--------|
| Monitor | CPU/memory metrics spike, request latency increases |
| Analyze | Correlate resource exhaustion with degraded performance |
| Plan | Trigger horizontal scaling, shed non-critical load |
| Execute | Request HPA scale-up, drop low-priority verifications |
| Knowledge | Record resource patterns, optimize resource requests |

**Verification Criteria**:
- [ ] HPA triggers scale-up (if configured)
- [ ] Critical PQC verifications continue
- [ ] Graceful degradation (no crashes)

---

## Implementation Order

1. **Phase 1**: Network Partition + Node Crash (basic resilience)
2. **Phase 2**: PQC Verification Failures (security testing)
3. **Phase 3**: Latency + Stress (performance under pressure)

## Prometheus Alerts for Chaos Testing

```yaml
groups:
  - name: x0tta6bl4-chaos-alerts
    rules:
      - alert: PQCVerificationFailureSpike
        expr: rate(x0tta6bl4_pqc_anomalies_total{type="verification_failed"}[1m]) > 0.1
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "PQC verification failure rate exceeded threshold"

      - alert: MeshNodeUnreachable
        expr: x0tta6bl4_mesh_peer_status{status="unreachable"} > 0
        for: 10s
        labels:
          severity: warning
        annotations:
          summary: "Mesh peer unreachable"

      - alert: MAPEKHealingTriggered
        expr: increase(x0tta6bl4_mapek_healing_actions_total[5m]) > 0
        labels:
          severity: info
        annotations:
          summary: "MAPE-K self-healing action executed"
```

## Test Execution Script

```bash
#!/bin/bash
# run_chaos_tests.sh

set -e

NAMESPACE="x0tta6bl4"

echo "=== Phase 1: Network Partition Test ==="
kubectl apply -f chaos-mesh/scenarios/network-partition.yaml
sleep 70  # Wait for chaos + recovery
kubectl delete -f chaos-mesh/scenarios/network-partition.yaml

echo "Verifying MAPE-K response..."
kubectl exec -n $NAMESPACE deploy/mesh-node -- \
  curl -s localhost:8080/metrics | grep mapek_healing

echo "=== Phase 2: PQC Failure Injection ==="
kubectl apply -f chaos-mesh/scenarios/pqc-failure.yaml
sleep 40
kubectl delete -f chaos-mesh/scenarios/pqc-failure.yaml

echo "Verifying PQC anomaly detection..."
kubectl exec -n $NAMESPACE deploy/mesh-node -- \
  curl -s localhost:8080/metrics | grep pqc_anomalies

echo "=== All chaos tests completed ==="
```

## Directory Structure for CLI-Agent Implementation

```
chaos-mesh/
├── CHAOS_MESH_DESIGN.md          # This document
├── scenarios/
│   ├── network-partition.yaml    # Scenario 1
│   ├── pqc-failure.yaml          # Scenario 2
│   ├── node-crash.yaml           # Scenario 3
│   ├── latency-injection.yaml    # Scenario 4
│   └── resource-stress.yaml      # Scenario 5
├── alerts/
│   └── prometheus-rules.yaml     # Alert definitions
├── scripts/
│   ├── run_chaos_tests.sh        # Test runner
│   └── chaos_pqc_inject.py       # PQC failure injector
└── dashboards/
    └── chaos-grafana.json        # Grafana dashboard for chaos monitoring
```

## Next Steps for CLI-Agent

1. Create `chaos-mesh/scenarios/` directory
2. Implement YAML manifests for each scenario
3. Create Prometheus alert rules
4. Write test execution script
5. Validate against local Kind/Minikube cluster
