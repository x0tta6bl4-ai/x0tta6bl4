# Architecture Invariants — Formal Specification

Each invariant defines:
1. **What** must always hold
2. **How** to verify it (procedure)
3. **What** constitutes a violation
4. **What** the proof artifact looks like

---

## I1: No Routing Loops

**Statement:** A packet must never visit the same node twice in its path from source to destination.

**Verification Procedure:**
1. Capture packets at each hop using tcpdump
2. For each packet, record: (source_ip, dest_ip, hop_ip, ttl, timestamp, packet_hash)
3. Build directed graph of packet flow
4. Check for cycles using DFS
5. Assert: no node appears twice in any path

**Violation Condition:** Any packet traverses the same IP twice.

**Proof Artifact:** `proofs/i1_loop_check.json` — graph edges, cycle detection result

**Source:** RFC 791 (IP TTL), RFC 2460 (IPv6 Hop Limit)

---

## I2: No Packet Duplication

**Statement:** Each packet must be delivered exactly once.

**Verification Procedure:**
1. At ingress, assign sequence number (monotonic counter)
2. At egress, record received sequence numbers
3. Check: received == sent (no gaps, no duplicates)
4. For N packets, assert: len(set(received)) == N

**Violation Condition:** Any sequence number appears more than once, or total received > total sent.

**Proof Artifact:** `proofs/i2_duplication_check.json` — sequence numbers, counts

**Source:** RFC 1122 (Host Requirements), RFC 2001 (TCP)

---

## I3: Session Continuity

**Statement:** An active session must survive node failure without application-level reset.

**Verification Procedure:**
1. Establish TCP session through VPN
2. Send continuous stream (1 packet/sec for 60s)
3. At T=30s, inject F1 (node crash) or F3 (partition)
4. Measure: packets lost, session reset, recovery time
5. Assert: session continues after recovery (no RST, no reconnection)

**Violation Condition:** Application receives TCP RST or must re-establish connection.

**Proof Artifact:** `proofs/i3_session_check.json` — timeline, packet loss, recovery

**Source:** RFC 5482 (TCP User Timeout), RFC 793 (TCP)

---

## I4: Zero Trust Policy Preserved

**Statement:** Every inter-node communication is authenticated and encrypted.

**Verification Procedure:**
1. Capture traffic at each hop using tcpdump
2. Parse TLS handshakes (ClientHello, ServerHello)
3. Verify: certificate chain valid, SNI matches, ALPN negotiated
4. For PQC: verify ML-KEM-768 key exchange, ML-DSA-65 signature
5. Assert: no plaintext inter-node traffic

**Violation Condition:** Any inter-node packet without TLS/PQC encryption.

**Proof Artifact:** `proofs/i4_trust_check.json` — captured handshakes, verification results

**Source:** RFC 8446 (TLS 1.3), NIST FIPS 203/204

---

## I5: Eventually Consistent Topology

**Statement:** After all failures resolve, all nodes converge to the same routing table within bounded time.

**Verification Procedure:**
1. Record routing tables on all nodes at T=0
2. Inject F3 (partition) for 30s
3. Resolve partition
4. Record routing tables at T+10s, T+20s, T+30s
5. Assert: at some T_converge, all routing tables are identical

**Violation Condition:** Routing tables remain divergent after 60s.

**Convergence Bound:** T_converge < 60s (configurable)

**Proof Artifact:** `proofs/i5_convergence_check.json` — routing tables, timestamps, convergence time

**Source:** RFC 3567 (IS-IS), RFC 2328 (OSPF)

---

## I6: Bounded Recovery Time

**Statement:** System recovers from any single failure within the declared SLA.

**Verification Procedure:**
1. Inject failure F_x
2. Measure: T_detect (time to detect), T_recover (time to full recovery)
3. Total = T_detect + T_recover
4. Repeat N=30+ times
5. Assert: p95(Total) < SLA

**SLA (model hypothesis, not measured):**
- T_detect: ~1s (healthcheck interval)
- T_recover: ~0.5s (route convergence)
- Total: < 2s (PASS), 2-5s (WARNING), >5s (FAIL)

**Note:** These are model-derived estimates. Actual values require measurement.

**Proof Artifact:** `proofs/i6_recovery_check.json` — recovery times, percentiles

**Source:** Internal model (see evaluation_gate.py SLA Rationale)

---

## I7: Monotonic Packet Delivery

**Statement:** Packets are delivered in order within a single session.

**Verification Procedure:**
1. Send N numbered packets at known intervals
2. Record arrival order at receiver
3. Assert: arrival_order == sorted(arrival_order)

**Violation Condition:** Any out-of-order delivery at the mesh layer.

**Proof Artifact:** `proofs/i7_ordering_check.json` — sent/received sequence

**Source:** RFC 793 (TCP), RFC 6298 (RTT Calculation)
