---
name: x0tta6bl4-mesh-orchestrator
description: >
  Self-healing mesh orchestration with PQC, Zero-Trust, DAO governance and
  MAPE-K autonomic loop. Use when user says "deploy mesh", "self-heal topology",
  "DAO vote config", "PQC rotate keys", "mesh orchestrate", "crisis recovery",
  "edge setup", "run MAPE-K cycle", "simulate failure", or "mesh status".
  Coordinates eBPF telemetry, GraphSAGE anomaly detection, quadratic voting,
  post-quantum key rotation, and blue-green deployments.
license: Apache-2.0
metadata:
  author: x0tta6bl4 DAO
  version: 2026.02.04-H1
  mcp-server: x0tta6bl4-mcp
  category: mesh-devops
  tags: [mesh, mape-k, pqc, dao, self-healing, ebpf, orchestration]
---

# x0tta6bl4 Mesh Orchestrator

End-to-end orchestration of the x0tta6bl4 self-healing mesh network.
Implements the full MAPE-K autonomic cycle with DAO-governed configuration changes
and post-quantum cryptographic key rotation.

## Instructions (MAPE-K Orchestration Cycle)

### Step 1: Monitor (eBPF Telemetry)

Collect real-time metrics from the mesh network via eBPF probes.

```bash
python3 skills/x0tta6bl4-mesh-orchestrator/scripts/validate-mesh.py --metrics
```

This script collects:
- **Network**: p99 latency, packet loss, throughput (target: latency < 40ms, loss < 1%)
- **Performance**: CPU, memory, context switches, syscalls
- **Security**: failed auth attempts, suspicious file access, privilege escalation
- **Mesh**: peer count, route count, MTTR

Key classes:
```python
from src.network.ebpf.ebpf_metrics_collector import EBPFMetricsCollector
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig

collector = EBPFMetricsCollector()
metrics = collector.collect_all_metrics()
# metrics = {'performance': PerformanceMetrics, 'network': NetworkMetrics, 'security': SecurityMetrics}
```

Thresholds for anomaly detection:
| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| p99 latency | < 40ms | 40-100ms | > 100ms |
| packet loss | < 1% | 1-5% | > 5% |
| CPU usage | < 70% | 70-90% | > 90% |
| memory usage | < 80% | 80-95% | > 95% |
| MTTR | < 3min | 3-5min | > 5min |

### Step 2: Analyze (GraphSAGE + Causal)

If metrics exceed warning thresholds, run anomaly detection:

```python
from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

detector = GraphSAGEAnomalyDetector(anomaly_threshold=0.6)
prediction = detector.predict(node_id="node-1", features={
    "rssi": metrics['network'].latency_ms,
    "snr": 15.0,
    "loss_rate": metrics['network'].packet_loss_percent / 100,
    "latency": metrics['network'].latency_ms,
    "cpu": metrics['performance'].cpu_percent / 100,
    "memory": metrics['performance'].memory_percent / 100,
})
# prediction.is_anomaly, prediction.anomaly_score, prediction.confidence
```

For root cause analysis, use the integrated MAPE-K analyzer:
```python
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle

mape_k = IntegratedMAPEKCycle(enable_observe_mode=True)
result = mape_k.run_cycle(metrics=collected_metrics)
# result['analyzer_results']['root_cause']
```

### Step 3: Plan (DAO Governance)

If anomaly confirmed with high confidence (> 0.8), propose configuration change via DAO:

```bash
python3 skills/x0tta6bl4-mesh-orchestrator/scripts/dao-vote.py \
  --action "topology_update" \
  --title "Auto-heal: reroute around node-3" \
  --duration 300
```

Key governance functions:
```python
from src.dao.governance import GovernanceEngine, VoteType

governance = GovernanceEngine(node_id="orchestrator")
proposal = governance.create_proposal(
    title="Topology update: reroute around failed node",
    description="GraphSAGE detected anomaly score 0.92 on node-3",
    duration_seconds=300,  # 5 min emergency vote
    quorum=0.33,
    threshold=0.5
)
# Quadratic voting: voting_power = sqrt(tokens)
governance.cast_vote(proposal.id, voter_id, VoteType.YES, tokens=100)
governance.check_proposals()  # Tally when expired
```

Decision matrix:
| Confidence | Severity | Action |
|-----------|----------|--------|
| > 0.9 | Critical | Auto-execute (no vote needed) |
| 0.8-0.9 | High | Emergency DAO vote (5 min) |
| 0.6-0.8 | Medium | Standard DAO vote (1 hour) |
| < 0.6 | Low | Log + observe mode |

### Step 4: Execute (Self-Heal + PQC Rotate)

After DAO approval (or auto-execute for critical):

**4a. Self-healing execution:**
```python
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle

mape_k = IntegratedMAPEKCycle()
result = mape_k.run_cycle(metrics)
# result['executor_results']['success'] == True
# result['executor_results']['recovery_time'] < 180  # MTTR < 3 min
```

**4b. PQC key rotation (if security event):**
```python
from src.security.post_quantum import PQMeshSecurityLibOQS

pq = PQMeshSecurityLibOQS(node_id="node-1", kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
new_keys = pq.get_public_keys()
# Distribute new_keys to all peers via mesh routing
```

**4c. Blue-green deployment (if config change):**
```bash
# Apply new K8s config
kubectl apply -f skills/x0tta6bl4-mesh-orchestrator/assets/mesh-deployment.yaml

# Verify health
curl -s http://localhost:8080/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])"
```

### Step 5: Verify + Knowledge Update

After execution, verify recovery:

```bash
python3 skills/x0tta6bl4-mesh-orchestrator/scripts/validate-mesh.py --verify
```

Checks:
- All critical metrics back within normal range
- MTTR < 3 minutes (measured)
- No cascading failures predicted
- PQC keys rotated if security event
- DAO proposal executed if governance-gated

Run digital twin simulation to validate stability:
```python
from src.simulation.digital_twin import MeshDigitalTwin

twin = MeshDigitalTwin("post-heal-sim")
twin.create_test_topology(num_nodes=10)
result = twin.simulate_node_failure("node-3", duration_seconds=60)
assert result.mttr_seconds < 180
assert result.connectivity_maintained > 0.95
```

## Examples

### Example 1: Self-heal after node outage
```
User: "Self-heal mesh after outage on node-3"

Actions:
1. Run validate-mesh.py --metrics → detect node-3 unreachable
2. GraphSAGE anomaly_score=0.95 → auto-execute (critical)
3. MAPE-K executor: reroute traffic via node-2, node-4
4. Rotate PQC keys for affected channels
5. validate-mesh.py --verify → MTTR=2.1min, all green
```

### Example 2: DAO-governed config update
```
User: "DAO vote to update routing algorithm"

Actions:
1. Create proposal via governance.create_proposal()
2. Distribute to all voting nodes
3. Collect quadratic votes for 1 hour
4. If passed: apply new routing config via MAPE-K executor
5. Validate with digital twin simulation
```

### Example 3: PQC key rotation
```
User: "PQC rotate keys for all nodes"

Actions:
1. Generate new ML-KEM-768 + ML-DSA-65 keypairs per node
2. Distribute public keys via authenticated mesh channels
3. Re-establish secure channels with new keys
4. Verify with beacon signing test
5. Log rotation event to audit trail
```

### Example 4: Crisis edge deployment
```
User: "Deploy edge node in disconnected environment"

Actions:
1. Generate offline PQC keypair
2. Pre-load mesh routing table with known peers
3. Deploy via assets/mesh-deployment.yaml with offline=true
4. On reconnect: sync state via CRDT, re-establish PQC channels
5. Run MAPE-K cycle to integrate into mesh
```

## Troubleshooting

### Error: "PQC key invalid"
Cause: ML-KEM-768 keypair expired or corrupted
Solution: Force key rotation:
```python
from src.security.post_quantum import PQMeshSecurityLibOQS
pq = PQMeshSecurityLibOQS("node-id")
new_keys = pq.get_public_keys()  # Generates fresh keypair
```

### Error: "DAO quorum not reached"
Cause: Not enough voting nodes participated
Solution: Lower quorum threshold for emergency or extend voting duration:
```python
proposal = governance.create_proposal(title="...", quorum=0.25, duration_seconds=7200)
```

### Error: "MAPE-K cycle timeout"
Cause: Analysis phase stuck (GraphSAGE model too slow)
Solution: Fall back to rule-based detection:
```python
import src.ml.graphsage_anomaly_detector as mod
mod._TORCH_AVAILABLE = False  # Force rule-based fallback
```

### Error: "Mesh connectivity < 95%"
Cause: Cascading failure after node removal
Solution: Run digital twin prediction before executing:
```python
twin = MeshDigitalTwin("pre-check")
cascade = twin.predict_cascade_failure("failing-node", threshold=0.5)
if len(cascade) > 2:
    print("WARNING: cascade risk, manual review required")
```

## References

Consult these files for detailed API documentation:
- `references/api-guide.md` - Full API patterns for all subsystems
- `references/pqc-algorithms.md` - Post-quantum algorithm details
- `assets/mesh-deployment.yaml` - K8s deployment template
