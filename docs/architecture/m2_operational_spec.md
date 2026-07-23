# Operational Specification: Milestone M2 (Autonomous Self-Healing Mesh on Real Network)

**Version**: 1.1  
**Framework**: Validation Laboratory Level 3 & Level 4 (Operational Infrastructure)  
**Date**: 2026-07-23  

---

## 1. Goal & Hypothesis

> **Core Objective**: Confirm that all platform invariants (I1–I6) validated synthetically in Milestone M1 are strictly preserved in an operational container environment with real network traffic, kernel-level packet drops (`tc netem`), process crashes, and SPIFFE identity verification.

---

## 2. Standardized Failure Catalogue (Failure IDs)

| Failure ID | Failure Description | Trigger Mechanism | Target Invariants | Priority |
| :---: | :--- | :--- | :---: | :---: |
| **F-001** | **Packet Loss (80%)** | `tc netem loss 80%` | I1, I2, I4 | ⭐⭐⭐⭐⭐ |
| **F-002** | **High Latency (300ms)** | `tc netem delay 300ms 50ms` | I2, I4 | ⭐⭐⭐⭐⭐ |
| **F-003** | **Node Crash** | `kill -9 <daemon_pid>` | I1, I2, I3, I4 | ⭐⭐⭐⭐⭐ |
| **F-004** | **Network Partition** | `docker network disconnect` | I1, I4 | ⭐⭐⭐⭐ |
| **F-005** | **Invalid / Forged SVID** | Unsigned control packet injection | I5, I6 | ⭐⭐⭐⭐ |

---

## 3. Environment & Network Topology

```
+------------------------------------+       Virtual Mesh Link       +------------------------------------+
|            Node Alpha              | <===========================> |             Node Beta              |
|  (Container: x0tta6bl4-node-a)     |       (veth / bridge)         |  (Container: x0tta6bl4-node-b)     |
|  IP: 172.28.0.2                    |                               |  IP: 172.28.0.3                    |
|  SPIFFE: spiffe://mesh/node-a      |                               |  SPIFFE: spiffe://mesh/node-b      |
+------------------------------------+                               +------------------------------------+
```

---

## 4. MTTR Granular Timing Breakdown

$$MTTR = t_{\text{detect}} + t_{\text{analyze}} + t_{\text{plan}} + t_{\text{execute}}$$

- $t_{\text{detect}}$: Time for eBPF ring buffer telemetry anomaly detection.
- $t_{\text{analyze}}$: Time for MAPE-K anomaly classification.
- $t_{\text{plan}}$: Time for recovery action selection and policy check.
- $t_{\text{execute}}$: Time for route rerouting or service restart execution.

---

## 5. Invariant Evidence & Target SLA Matrix (M2)

| ID | Invariant Name | Operational Success Criteria | Evidence Source File |
| :---: | :--- | :--- | :--- |
| **I1** | **No Routing Loops** | Route graph remains acyclic after failover. | `mesh_topology.json` |
| **I2** | **MTTR SLA (< 1.5s)** | Failover & reroute completes in `MTTR < 1.500s`. | `mapek_telemetry.prom` |
| **I3** | **Knowledge Monotonicity** | Knowledge base pattern count grows: $N_{\text{after}} > N_{\text{before}}$. | `knowledge_export.json` |
| **I4** | **Session Continuity** | Active TCP stream survives link drop without socket reset. | `traffic_capture.pcap` |
| **I5** | **Zero Trust Integrity** | Control plane actions require valid PQC-signed SVIDs. | `svid_audit.json` |
| **I6** | **PQC Cryptography** | Key exchange & signatures verify with zero byte errors. | `pqc_signature.pem` |

---

## 6. Enriched Machine-Readable Report Schema (`results/milestone_m2_report.json`)

```json
{
  "milestone": "M2_Autonomous_Self_Healing_Mesh_Real_Network",
  "validation_id": "val-m2-20260723-100900",
  "failure_id": "F-001",
  "timestamp": "2026-07-23T10:09:00Z",
  "environment": {
    "platform": "docker-l3-operational",
    "kernel": "Linux 6.8.0-generic",
    "docker_version": "26.1.0",
    "liboqs_version": "0.10.0",
    "cpu_arch": "x86_64",
    "memory_gb": 16
  },
  "component_reality_matrix": {
    "pqc_api": "REAL",
    "mape_k_engine": "REAL",
    "validation_framework": "REAL",
    "ebpf_kernel_dataplane": "REAL",
    "packet_loss_injection": "REAL_TC_NETEM",
    "multi_node_routing": "REAL_DOCKER_NETWORK"
  },
  "recovery_details": {
    "action_executed": "dynamic_route_reroute",
    "trigger_reason": "packet_loss_exceeded_80_percent"
  },
  "invariants": {
    "I1_No_Routing_Loops": "PASS",
    "I2_MTTR_SLA": "PASS",
    "I3_Knowledge_Monotonicity": "PASS",
    "I4_Session_Continuity": "PASS",
    "I5_Zero_Trust_Integrity": "PASS",
    "I6_PQC_Safety": "PASS"
  },
  "timings_ms": {
    "detect_ms": 120.4,
    "analyze_ms": 85.2,
    "plan_ms": 42.1,
    "execute_ms": 195.3,
    "total_mttr_ms": 443.0,
    "sla_threshold_ms": 1500.0
  },
  "evidence": {
    "telemetry": "results/m2_evidence/mapek_telemetry.prom",
    "pcap": "results/m2_evidence/traffic_capture.pcap",
    "logs": "results/m2_evidence/mapek_execution.log",
    "knowledge": "results/m2_evidence/knowledge_export.json"
  },
  "verdict": "MILESTONE_M2_REAL_NETWORK_PASSED"
}
```
