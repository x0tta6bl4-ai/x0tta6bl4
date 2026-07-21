# Traceability Matrix

Every requirement traces through: Invariant → Implementation → Test → Evidence → Report.

This matrix allows any engineer to follow the chain from requirement to proof.

---

## Requirement → Invariant → Test → Evidence

| Requirement | Invariant | Implementation | Property Test | Benchmark Suite | Evidence Format |
|:------------|:----------|:---------------|:--------------|:----------------|:----------------|
| **R1: No routing loops** | I1 | `src/network/routing/` | `test_invariants.py::test_no_routing_loops` | Suite V4 (topology) | `evidence/i1_loop_check.json` |
| **R2: No packet duplication** | I2 | `src/network/transport/` | `test_invariants.py::test_packet_duplication` | Suite V2 (loss) | `evidence/i2_duplication_check.json` |
| **R3: Session continuity** | I3 | `src/network/resilience/` | `test_invariants.py::test_session_continuity` | Suite V1 (failure) | `evidence/i3_session_check.json` |
| **R4: Zero trust preserved** | I4 | `src/security/pqc/` | `test_invariants.py::test_zero_trust` | Suite V5 (PQC) | `evidence/i4_trust_check.json` |
| **R5: Topology convergence** | I5 | `src/network/mesh/` | `test_invariants.py::test_convergence` | Suite V7 (partition) | `evidence/i5_convergence_check.json` |
| **R6: Bounded recovery** | I6 | `src/network/self_healing/` | `test_invariants.py::test_recovery_time` | Suite V1 (failure) | `evidence/i6_recovery_check.json` |
| **R7: Packet ordering** | I7 | `src/network/transport/` | `test_invariants.py::test_packet_ordering` | Suite V2 (loss) | `evidence/i7_ordering_check.json` |

---

## Failure Type → Test Suite → Invariant Coverage

| Failure | Test Suite | Invariant Check |
|:--------|:-----------|:----------------|
| F1 Node Crash | V1, V6 | I3 (Session), I6 (Recovery) |
| F2 Kernel Panic | V1, V7 | I3 (Session), I5 (Convergence) |
| F3 Network Partition | V1, V4, V7 | I1 (Loops), I3 (Session), I5 (Convergence) |
| F4 Packet Loss | V2, V6 | I2 (Duplication), I7 (Ordering) |
| F5 High Latency | V2, V6 | I6 (Recovery) |
| F6 DNS Failure | V3 | I5 (Convergence) |
| F7 Certificate Expiry | V5 | I4 (Zero Trust) |
| F8 PQC Handshake | V5 | I4 (Zero Trust) |
| F9 Registry Loss | V4, V7 | I5 (Convergence) |
| F10 Byzantine | V7 | I1 (Loops), I5 (Convergence) |

---

## SLA Threshold → Rationale → Validation

| Metric | SLA | Rationale Source | Validation Required |
|:-------|:----|:-----------------|:--------------------|
| Recovery Time | < 2s (PASS) | Model: MAPE-K (5s) + detect (1s) + converge (0.5s) | Suite V1, N=30 |
| Session Survival | > 99.5% (PASS) | Production: 500 users × 0.5% = 2.5 affected | Suite V1, N=30 |
| PQC Overhead | < 50ms (PASS) | Measured: gen (25ms) + encaps (15ms) + verify (5ms) | Suite V5, N=30 |
| Loss Degradation | < 15% (PASS) | Theory: TCP retransmission at 20% loss | Suite V2, N=30 |

---

## Version Chain (for each evidence artifact)

```json
{
  "spec_version": "1.0",
  "runner_version": "1.0",
  "git_commit": "518b1052",
  "kernel": "6.14.0-37-generic",
  "tcp_cc": "bbr",
  "hypothesis_version": "6.x",
  "python_version": "3.12"
}
```

---

## How to Read This Matrix

**Top-down (Requirement → Evidence):**
1. Start with a requirement (e.g., "No routing loops")
2. Find the invariant (I1)
3. Find the implementation (src/network/routing/)
4. Find the property test (test_no_routing_loops)
5. Find the benchmark suite (V4)
6. Find the evidence artifact (i1_loop_check.json)

**Bottom-up (Evidence → Requirement):**
1. Start with an evidence artifact
2. Find which benchmark produced it
3. Find which invariant it checks
4. Find which requirement it satisfies
