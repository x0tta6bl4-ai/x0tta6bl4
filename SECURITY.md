# Security Policy

## Supported Versions

| Version | Supported | Status |
| ------- | --------- | ------ |
| 1.0.x   | :white_check_mark: | Active development |
| 0.9.x   | :white_check_mark: | Maintenance |
| < 0.9   | :x: | End of life |

## Security Overview

x0tta6bl4 implements a defense-in-depth security architecture with multiple layers of protection:

```
..Security Architecture...................
.
.  ..Layer 1: Cryptographic...............
.  .  - Post-Quantum Cryptography (PQC)
.  .  - ML-KEM-768 (NIST FIPS 203)
.  .  - ML-DSA-65 (NIST FIPS 204)
.  .  - AES-256-GCM symmetric encryption
.  .......................................
.
.  ..Layer 2: Identity....................
.  .  - SPIFFE/SPIRE Zero Trust
.  .  - mTLS for all internal traffic
.  .  - Workload attestation
.  .......................................
.
.  ..Layer 3: Network.....................
.  .  - eBPF XDP packet filtering
.  .  - SipHash-2-4 MAC verification
.  .  - Kernel-space crypto operations
.  .......................................
.
.  ..Layer 4: Application.................
.  .  - Input validation
.  .  - Rate limiting
.  .  - Audit logging
.  .......................................
...........................................
```

## Security Features

### Post-Quantum Cryptography (PQC)

x0tta6bl4 uses NIST-standardized post-quantum algorithms:

| Algorithm | Type | Standard | Use Case |
|-----------|------|----------|----------|
| **ML-KEM-768** | Key Encapsulation | NIST FIPS 203 | Key exchange |
| **ML-DSA-65** | Digital Signature | NIST FIPS 204 | Authentication |
| **AES-256-GCM** | Symmetric Encryption | NIST SP 800-38D | Data encryption |

#### Secure Key Storage

All secret keys are protected using **SecureKeyStorage**:

```python
from src.security.pqc import SecureKeyStorage

# Keys are encrypted in memory with AES-256-GCM
storage = SecureKeyStorage()
storage.store_key("ml-kem-private", private_key_bytes)

# Memory is locked (mlock) to prevent swapping
# Secure zeroization on deletion
```

**Security Features:**
- AES-256-GCM encryption of keys in memory
- Memory locking (mlock) to prevent swapping to disk
- Secure zeroization on object deletion
- Thread-safe singleton pattern
- Ephemeral encryption key per session

#### Hybrid Schemes

For backward compatibility and defense-in-depth:

```python
# Hybrid key exchange: X25519 + ML-KEM-768
from src.security.pqc import HybridKeyExchange

hybrid = HybridKeyExchange()
keypair = hybrid.generate_keypair()
# Provides both classical and post-quantum security
```

### Zero Trust Architecture (SPIFFE/SPIRE)

Every workload in x0tta6bl4 has a cryptographic identity:

```
..SPIFFE Identity Flow.....................
.
.  Workload -> SPIRE Agent -> Attestation
.       |           |            |
.       v           v            v
.  SVID Token  Node Attest  Workload Attest
.       |           |            |
.       +-----------+------------+
.                   |
.                   v
.           mTLS Connection
...........................................
```

**Features:**
- Automatic certificate rotation
- Workload attestation (TPM, Kubernetes, etc.)
- Short-lived SVIDs (SPIFFE Verifiable Identity Documents)
- mTLS for all service-to-service communication

### eBPF XDP Security

Kernel-space packet processing with:

- **SipHash-2-4 MAC**: Fast packet authentication
- **XDP filtering**: Drop malicious packets before kernel network stack
- **Rate limiting**: Per-IP rate limiting in kernel space

```c
// eBPF XDP packet verification (simplified)
SEC("xdp_pqc_verify")
int xdp_pqc_verify_prog(struct xdp_md *ctx) {
    // Verify SipHash MAC
    if (!verify_mac(ctx)) {
        return XDP_DROP;
    }
    // Check session validity
    if (!session_valid(ctx)) {
        return XDP_PASS; // To userspace for full verification
    }
    return XDP_PASS;
}
```

### Security Metrics

| Metric | Value | Target |
|--------|-------|--------|
| CVE Vulnerabilities | **0** | 0 |
| Hardcoded Secrets | **0** | 0 |
| Security Test Coverage | **85%+** | >80% |
| Dependency Audit | **Clean** | No known vulnerabilities |

## Reporting a Vulnerability

:warning: **Do NOT report security vulnerabilities through public GitHub issues.**

### How to Report

1. **Email**: Send details to [security@x0tta6bl4.net](mailto:security@x0tta6bl4.net)
2. **PGP Key**: Use our public key for encryption (see below)
3. **Format**: Include the following information

```markdown
**Summary**: Brief description of the vulnerability

**Affected Component**: Which part of x0tta6bl4 is affected

**Steps to Reproduce**: 
1. Step one
2. Step two

**Impact**: What can an attacker achieve

**Proof of Concept**: If available

**Suggested Fix**: If you have ideas for remediation
```

### PGP Public Key

```
-----BEGIN PGP PUBLIC KEY BLOCK-----
[Public key for security@x0tta6bl4.net]
-----END PGP PUBLIC KEY BLOCK-----
```

### Response Timeline

| Stage | Timeline |
|-------|----------|
| **Acknowledgment** | Within 48 hours |
| **Initial Assessment** | Within 5 business days |
| **Status Update** | Every 7 days until resolved |
| **Fix Development** | Depends on severity |
| **Disclosure** | After fix is released |

### Severity Classification

| Severity | Description | Response Time |
|----------|-------------|---------------|
| **Critical** | Remote code execution, key compromise | 24 hours |
| **High** | Authentication bypass, data exposure | 72 hours |
| **Medium** | Limited information disclosure | 7 days |
| **Low** | Minor security issue | 14 days |

### Disclosure Policy

We follow **Coordinated Vulnerability Disclosure (CVD)**:

1. Reporter reports vulnerability privately
2. We acknowledge and assess
3. We develop and test fix
4. We release fix and publish advisory
5. Reporter may publish details after fix is released

## Security Best Practices

### For Developers

```bash
# Always use pre-commit hooks
pre-commit install

# Run security linters
bandit -r src/

# Check for secrets
detect-secrets scan src/

# Audit dependencies
pip-audit

# Run security tests
pytest tests/security/ -v
```

### For Operators

```yaml
# docker-compose.yml security hardening
services:
  x0tta6bl4:
    security_opt:
      - no-new-privileges:true
    read_only: true
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN  # Required for eBPF
    environment:
      - SPIFFE_ENDPOINT=spire-agent:9090
```

### For Users

- Keep x0tta6bl4 updated to the latest supported version
- Enable mTLS for all connections
- Use SPIFFE/SPIRE for workload identity
- Monitor security advisories

## Security Audit History

| Date | Auditor | Scope | Result |
|------|---------|-------|--------|
| 2026-02-17 | Protocol Security | Full Security Audit | **6 CVEs Fixed** |
| 2026-01 | Internal | PQC Implementation | Pass |
| 2026-01 | Internal | eBPF XDP | Pass |
| 2025-12 | Internal | Full codebase | 0 CVEs |

### 2026-02-17 Security Audit Findings (RESOLVED)

| CVE ID | Severity | Component | Issue | Fix |
|--------|----------|-----------|-------|-----|
| **CVE-2026-XDP-001** | CRITICAL | eBPF XDP | Timing attack in MAC verification | Constant-time XOR comparison |
| **CVE-2026-PQC-001** | HIGH | PQC Keys | Secret keys in plain memory | SecureKeyStorage with AES-256-GCM |
| **CVE-2026-PQC-002** | HIGH | HKDF | Null salt in key derivation | Random salt per derivation |
| **CVE-2026-XDP-002** | MEDIUM | eBPF Sessions | Hardcoded 256 session limit | Configurable up to 65536 |
| **CVE-2026-PQC-003** | MEDIUM | eBPF Sessions | Hardcoded TTL | Configurable via eBPF map |
| **CVE-2026-SPIFFE-001** | MEDIUM | SPIFFE | No clock skew tolerance | 5-minute tolerance |

**All vulnerabilities have been remediated.** See [`docs/security/SECURITY_AUDIT_2026-02-17.md`](docs/security/SECURITY_AUDIT_2026-02-17.md) for details.

## Security Configuration

### PQC Configuration

```python
# src/core/settings.py
PQC_CONFIG = {
    "kem_algorithm": "ML-KEM-768",  # NIST FIPS 203
    "sig_algorithm": "ML-DSA-65",   # NIST FIPS 204
    "symmetric_algorithm": "AES-256-GCM",
    "enable_hybrid": True,  # X25519+ML-KEM fallback
}
```

### SPIFFE/SPIRE Configuration

```yaml
# helm/values.yaml
spire:
  enabled: true
  trustDomain: "x0tta6bl4.net"
  server:
    caKeyType: "ec-p256"
    svidTTL: "1h"
  agent:
    attestation:
      k8s:
        enabled: true
```

### eBPF Security Configuration

```python
# eBPF XDP security settings
EBPF_SECURITY = {
    "enable_mac_verification": True,
    "mac_algorithm": "SipHash-2-4",
    "rate_limit_pps": 10000,  # packets per second
    "drop_invalid_sessions": True,
}
```

## Incident Response

In case of a security incident:

1. **Isolate**: Affected components are automatically isolated by MAPE-K
2. **Assess**: ConsciousnessEngine evaluates threat level
3. **Contain**: Zero Trust policies prevent lateral movement
4. **Recover**: Self-healing restores normal operation
5. **Report**: Incident logged to DAO audit trail

## Threat Model

### Attack Surface

```
..Threat Model Diagram...........................
.
.  +------------------+     +------------------+
.  | External Network | --> | eBPF XDP Filter  |
.  +------------------+     +------------------+
.           |                        |
.           v                        v
.  +------------------+     +------------------+
.  | mTLS Gateway     | --> | SPIRE Agent      |
.  +------------------+     +------------------+
.           |                        |
.           v                        v
.  +------------------+     +------------------+
.  | Application      | --> | PQC Key Storage  |
.  +------------------+     +------------------+
...............................................
```

### Threat Categories

| Threat | Mitigation | Status |
|--------|------------|--------|
| **Man-in-the-Middle** | mTLS + PQC key exchange | Mitigated |
| **Side-Channel (Timing)** | Constant-time operations | Mitigated |
| **Key Extraction** | SecureKeyStorage + mlock | Mitigated |
| **Replay Attack** | Session IDs + TTL | Mitigated |
| **Quantum Computer** | ML-KEM-768 + ML-DSA-65 | Mitigated |
| **Lateral Movement** | Zero Trust + SPIFFE | Mitigated |
| **DDoS** | eBPF rate limiting | Mitigated |
| **Clock Skew** | 5-minute tolerance | Mitigated |

### Trust Boundaries

1. **Untrusted Zone**: External network, user input
2. **DMZ**: Load balancers, ingress controllers
3. **Trusted Zone**: Internal services with SPIFFE identity
4. **High-Security Zone**: Key management, HSM integration

### Assumptions

- SPIRE Server and Agent are properly secured
- Underlying OS is not compromised
- Hardware security modules (HSM) are available for production
- Network segmentation is properly configured

## Contact

- **Security Team**: [security@x0tta6bl4.net](mailto:security@x0tta6bl4.net)
- **PGP Key**: Available at https://x0tta6bl4.net/security.asc
- **Security Advisories**: https://github.com/x0tta6bl4/x0tta6bl4/security/advisories

---

Last updated: 2026-02-17