# x0tta6bl4 Mesh Orchestrator API Guide

## Import Map

```python
# eBPF Telemetry
from src.network.ebpf.ebpf_metrics_collector import EBPFMetricsCollector
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig
from src.network.ebpf.ebpf_loader import EBPFLoader

# PQC Cryptography
from src.security.post_quantum import LibOQSBackend, PQMeshSecurityLibOQS, HybridPQEncryption
from src.crypto.pqc_crypto import PQCCrypto

# DAO Governance
from src.dao.governance import GovernanceEngine, Proposal, VoteType
from src.dao.fl_governance import FLGovernanceDAO, QuadraticVoting

# Self-Healing
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
from src.self_healing.mape_k import MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor

# Mesh Network
from src.network.routing.mesh_router import MeshRouter, RouteEntry, RoutingPacket, PacketType
from src.mesh.network_manager import MeshNetworkManager

# Anomaly Detection
from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector, AnomalyPrediction

# Digital Twin
from src.simulation.digital_twin import MeshDigitalTwin, TwinNode, TwinLink

# SPIFFE Identity
from src.security.spiffe.controller.spiffe_controller import SPIFFEController
from src.security.spiffe.agent.manager import SPIFFEAgentManager

# Zero Trust
from src.security.zero_trust import ZeroTrustValidator
from src.security.device_attestation import DeviceAttestor
from src.security.policy_engine import PolicyEngine
```

## Quick Recipes

### Collect metrics + detect anomalies
```python
collector = EBPFMetricsCollector()
metrics = collector.collect_all_metrics()
detector = GraphSAGEAnomalyDetector(anomaly_threshold=0.6)
prediction = detector.predict(node_id="node-1", features={
    "latency": metrics['network'].latency_ms,
    "cpu": metrics['performance'].cpu_percent / 100,
    "loss_rate": metrics['network'].packet_loss_percent / 100,
})
```

### Run full MAPE-K cycle
```python
mape_k = IntegratedMAPEKCycle(enable_observe_mode=True)
result = mape_k.run_cycle(metrics=raw_metrics_dict)
if result['anomaly_detected']:
    print(f"Root cause: {result['analyzer_results']['root_cause']}")
    print(f"Strategy: {result['planner_results']['strategy']}")
    print(f"Success: {result['executor_results']['success']}")
```

### DAO proposal with quadratic voting
```python
gov = GovernanceEngine(node_id="orchestrator")
proposal = gov.create_proposal(
    title="Reroute traffic",
    description="Node-3 anomaly detected",
    duration_seconds=300,
    quorum=0.33, threshold=0.5
)
gov.cast_vote(proposal.id, "voter-1", VoteType.YES, tokens=100)
# voting_power = sqrt(100) = 10 votes
gov.check_proposals()
```

### PQC key rotation
```python
pq = PQMeshSecurityLibOQS("node-1", kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
keys = pq.get_public_keys()  # Fresh keypair generated
# Distribute keys['kem_public_key'] and keys['sig_public_key'] to peers
```

### Digital twin failure simulation
```python
twin = MeshDigitalTwin("pre-deploy-sim")
twin.create_test_topology(num_nodes=10, connectivity=0.3)
result = twin.simulate_node_failure("node-3", duration_seconds=60)
assert result.mttr_seconds < 180
assert result.connectivity_maintained > 0.95
cascade = twin.predict_cascade_failure("node-3", threshold=0.5)
```

## Packet Types (Mesh Routing)
| Type | Value | Purpose |
|------|-------|---------|
| DATA | 0x01 | User data payload |
| RREQ | 0x02 | Route Request (broadcast) |
| RREP | 0x03 | Route Reply (unicast) |
| RERR | 0x04 | Route Error (link broken) |
| HELLO | 0x05 | Neighbor keepalive |

## PQC Algorithms
| Algorithm | NIST Level | Type | Use |
|-----------|-----------|------|-----|
| ML-KEM-768 | 3 | KEM | Key exchange |
| ML-DSA-65 | 3 | Signature | Beacon/message signing |
| X25519 | Classical | DH | Hybrid TLS classical part |
| Ed25519 | Classical | Signature | Hybrid TLS classical part |
| AES-256-GCM | N/A | AEAD | Data encryption |

## Quadratic Voting Math
```
voting_power = sqrt(tokens_held)

Example:
  100 tokens  → 10 votes
  10000 tokens → 100 votes (not 100x advantage)
  100 people × 100 tokens each = 1000 votes > 1 whale × 10000 tokens = 100 votes
```
