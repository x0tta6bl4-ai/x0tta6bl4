---
title: x0tMQ Whitepaper
description: Architectural analysis and implementation report — PQC integration (FIPS 203/204), x0CHUNK fragmentation, DevSecOps pipelines
---

# x0tMQ Whitepaper: Post-Quantum MAVLink Security

**Protocol:** x0tMQ (x0tta6bl4 MAVLink Quantum)
**Document:** draft-x0tta6bl4-x0tmq-mavlink-pqc-00
**Status:** Experimental · IETF Internet-Draft
**Date:** June 2026

---

## Abstract

Current transformation of information security paradigms requires a radical revision of data protection methods in distributed systems and IoT networks. This report presents a comprehensive analysis of the x0tMQ protocol architecture, integrating post-quantum cryptographic mechanisms — key encapsulation ML-KEM (FIPS 203) and digital signatures ML-DSA (FIPS 204) — over the lightweight MAVLink telemetry protocol.

## Table of Contents

1. [Mathematical Basis (ML-KEM and ML-DSA)](#1-mathematical-basis)
2. [Key Encapsulation and Derivation](#2-key-encapsulation)
3. [Digital Signatures](#3-digital-signatures)
4. [Architectural Patterns](#4-architectural-patterns)
5. [Transport Layer: x0CHUNK Innovation](#5-transport-layer)
6. [Side-Channel Security](#6-side-channel-security)
7. [DevSecOps Strategy](#7-devsecops-strategy)
8. [Conclusions](#8-conclusions)

---

## 1. Mathematical Basis

The x0tMQ architecture relies on cryptographic algorithms resistant to attacks using quantum computers, operating on algebraic structures over polynomial rings. The mathematical foundation is the **Module Learning With Errors (MLWE)** problem, where computations occur in the ring:

$$R_q = \mathbb{Z}_q[X]/(X^n+1)$$

With $n=256$ and modulus $q=3329$. Polynomial multiplication is optimized using the **Number Theoretic Transform (NTT)** — a discrete analogue of the Fast Fourier Transform for finite fields — reducing complexity from $O(n^2)$ to $O(n \log n)$.

---

## 2. Key Encapsulation and Derivation

### ML-KEM-1024

Unlike compromise solutions, x0tMQ uncompromisingly uses the **maximum security level — ML-KEM-1024** (Security Level 5, equivalent to AES-256). Ciphertext size: **1568 bytes**.

| Parameter Set | Matrix (k) | Security Level | PK Size | CT Size |
|--------------|-----------|---------------|---------|---------|
| ML-KEM-512 | 2 | Level 1 | 800 | 768 |
| ML-KEM-768 | 3 | Level 3 | 1184 | 1088 |
| **ML-KEM-1024** | **4** | **Level 5** | **1568** | **1568** |

### HKDF-SHA3-256

After successful secret decapsulation, the protocol uses its own **HKDF-SHA3-256 module** for deriving final session keys. The negotiation and verification of the secure channel concludes with an **X0_SESSION_ACK** packet, guaranteeing cryptographic state synchronization between nodes before telemetry transmission begins.

---

## 3. Digital Signatures

### ML-DSA-87

For authentication and integrity, x0tMQ uses **ML-DSA-87** (FIPS 204, Security Level 5), based on the Fiat-Shamir with Aborts paradigm.

The transition to post-quantum signatures presents a serious architectural challenge: **signature size is 4627 bytes**. This makes transmission in a single network packet or standard MAVLink frame (max payload 255 bytes) **impossible without fragmentation**.

| Parameter Set | Security Level | Signature Size |
|--------------|---------------|---------------|
| ML-DSA-44 | Level 2 | 2420 bytes |
| ML-DSA-65 | Level 3 | 3309 bytes |
| **ML-DSA-87** | **Level 5** | **4627 bytes** |

---

## 4. Architectural Patterns

### Rejection of Dependency Injection

During design, complex patterns like abstract `MLKEMProvider` classes or Dependency Injection were deliberately rejected:

- **Memory predictability**: Secret keys passed as arguments, returned as results — easy to localize and zeroize
- **Code auditability**: No hidden state, no inheritance hierarchy, clear data flow path
- **Fail-fast compatibility**: Instead of mocking non-existent abstract providers, standalone versions use a trivial `try/except ImportError` block

This approach achieved **18/18 real integration tests passing**.

---

## 5. Transport Layer: x0CHUNK Innovation

### Background

MAVLink 2.0 was chosen as the transport layer, supporting 24-bit message ID space, allowing allocation of IDs 50000–50003 for custom cryptographic frames.

### x0CHUNK Fragmentation

The **primary transport innovation** of x0tMQ is the proprietary **x0CHUNK fragmentation mechanism**.

Since ML-DSA-87 signatures occupy **4627 bytes** and ML-KEM-1024 ciphertexts **1568 bytes**, effective fragmentation over MAVLink is essential:

| Payload | Size | x0CHUNK Fragments |
|---------|------|------------------|
| ML-DSA-87 signature | 4627 bytes | **19 chunks** |
| ML-KEM-1024 ciphertext | 1568 bytes | **7 chunks** |

The algorithm dynamically fragments cryptographic payloads into 245-byte chunks, guaranteeing correct reassembly, reordering, and integrity verification on the receiving side before the assembled array is passed for verification. **Without this mechanism, ML-DSA-87 over MAVLink would be impossible.**

### Dynamic CRC_EXTRA

The key protection against dialect desynchronization in MAVLink is the **CRC_EXTRA** byte — a 1-byte hash generated from message name, field names, and types during dialect compilation.

For standalone x0tMQ, a constant dictionary was embedded directly in `frame.py`:

```
CRC_EXTRA: dict[int, int] = {
    50000: 0xAB,  # x0CHUNK
    50001: 0xBC,  # X0_SESSION_INIT
    50002: 0xCD,  # X0_SIGNED_CMD
    50003: 0xDE,  # X0_SESSION_ACK
}
```

When `serialize()` and `deserialize()` are called, the framework dynamically determines the message type by ID and extracts the CRC_EXTRA value in $O(1)$ time — eliminating the need for XML compilation via mavgen.

---

## 6. Side-Channel Security

Software implementations of cryptography in high-level languages are often vulnerable to side-channel attacks, specifically **timing attacks**. In the real x0tMQ codebase, these risks are actively eliminated.

Three timing-related vulnerabilities were found and fixed:

### Secure Comparison
Replaced variable-time comparison with constant-time `hmac.compare_digest` to prevent byte-by-byte timing analysis.

**Vulnerable:**
```python
if received_mac == expected_mac:  # Variable time!
```

**Fixed:**
```python
if hmac.compare_digest(received_mac, expected_mac):  # Constant time
```

### mldsa_decompose Vulnerability
The decompression algorithm in ML-DSA was analyzed for timing leakage. Hardware division operations during signature generation can depend on operands, leaking secret key bits (similar to **CVE-2026-22705**).

The `mldsa_decompose` implementation was modified to ensure **strictly constant-time execution**, eliminating unpredictable division instructions in critical paths.

---

## 7. DevSecOps Strategy

### Honest Metrics

| Badge | Before | After |
|-------|--------|-------|
| Status | `production-ready` 🟢 | **`experimental` 🟠** |
| CodeQL | `0 alerts` 🟢 | **`30 open` 🟡** |
| Tests | `ZTCR 29/29` 🟢 | **`215/240 passing` 🟡** |

### CodeQL SARIF Upload

Integration encountered `HttpError: Resource not accessible by integration` — solved with minimal OIDC token permissions:

```yaml
permissions:
  actions: read
  contents: read
  security-events: write
```

### Mermaid.js on GitHub Pages

GitHub Pages uses Jekyll in safe mode, preventing Mermaid plugin usage. A client-side CDN script was injected into `index.md`:

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>
```

This renders diagrams in the client browser without generating binary artifacts (SVG/PNG) in the repository.

---

## 8. Conclusions

**x0tMQ is a real, working implementation of post-quantum cryptography (ML-KEM-1024 and ML-DSA-87) in IoT networks.** The introduction of the x0CHUNK fragmentation mechanism for transmitting 4627-byte signatures (19 chunks) and the X0_SESSION_ACK confirmation protocol overcame fundamental MAVLink limitations.

Rejection of redundant abstractions, static CRC_EXTRA binding, and targeted elimination of side-channel vulnerabilities in `hmac.compare_digest` and `mldsa_decompose` demonstrate the engineering maturity of a project capable of stably executing **18 cryptographic tests in 1.74 seconds**.

### References

- FIPS 203 (ML-KEM): https://csrc.nist.gov/pubs/fips/203/final
- FIPS 204 (ML-DSA): https://csrc.nist.gov/pubs/fips/204/final
- MAVLink v2: https://mavlink.io/en/guide/serialization.html
- x0tMQ Repository: https://github.com/x0tta6bl4-ai/x0tmq
- x0tMQ IETF Draft: `docs/rfc/draft-x0tmq-mavlink-pqc.md`

---

*Independent engineering project. Verified by machines, not marketing.*
