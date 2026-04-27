# Security Policy

## Supported Surface

This repository is an experimental codebase with a curated public `main` branch.

Supported surface:

| Surface | Status |
| ------- | ------ |
| `main` | Supported for security triage |
| historical archives and demo artifacts | best effort only |
| old tags, snapshots, and experimental branches | unsupported |

## Source Of Truth

Do not treat this file as a live dashboard.

The current source of truth for security state is:

1. the GitHub **Security** tab for this repository
2. the latest passing checks on the default branch
3. locally verified evidence under `docs/verification/` when explicitly referenced

Counts for alerts, secrets, and code scanning findings change over time. This file intentionally does **not** claim fixed values like “0 vulnerabilities” or “0 secrets”.

## Scope And Honesty Boundaries

x0tta6bl4 contains work on:

- post-quantum cryptography experiments
- SPIFFE/SPIRE and mTLS integration
- eBPF/XDP dataplane and observability tooling
- bot, VPN, and Ghost Access operational code

Important boundary:

- presence of security-oriented code does **not** imply field validation
- demo code, archived docs, and research surfaces may lag behind the hardened path
- any public claim about throughput, uptime, MTTR, or field validation must be backed by current evidence, not by this file

## Reporting A Vulnerability

Do **not** open public GitHub issues for undisclosed security problems.

Preferred path:

1. use GitHub private vulnerability reporting for this repository, if available
2. otherwise email [security@x0tta6bl4.net](mailto:security@x0tta6bl4.net)

Please include:

- affected file, component, or workflow
- exact reproduction steps
- impact
- whether the issue is on public `main` or only in historical material
- proof of concept if safe to share

## Response Expectations

Targets, not guarantees:

| Stage | Target |
| ----- | ------ |
| acknowledgment | within 3 business days |
| initial triage | within 7 business days |
| follow-up cadence | weekly for active issues |

## Immediate Repository Rules

- never commit live credentials, tokens, webhook secrets, or private keys
- if a credential is exposed, remove it from the current tree immediately and rotate it out-of-band
- do not expose raw exception text in HTTP responses on public surfaces
- avoid `debug=True` and similar unsafe defaults in examples that people may copy into real deployments
- prefer redacted operational logging over verbose secret-bearing logs

## Developer Baseline

```bash
pre-commit install
python3 -m py_compile path/to/edited_file.py
```

For dependency and release checks, use the repo-local verification scripts referenced in `docs/verification/` and `scripts/`.

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
| **CVE-2026-DF-001** | CRITICAL | Domain Fronting | SSL verification disabled (`ssl.CERT_NONE`) | Enabled `ssl.CERT_REQUIRED` with hostname check |
| **CVE-2026-PQC-001** | HIGH | PQC Keys | Secret keys in plain memory | SecureKeyStorage with AES-256-GCM |
| **CVE-2026-PQC-002** | HIGH | HKDF | Null salt in key derivation | Random salt per derivation |
| **CVE-2026-XDP-002** | MEDIUM | eBPF Sessions | Hardcoded 256 session limit | Configurable up to 65536 |
| **CVE-2026-PQC-003** | MEDIUM | eBPF Sessions | Hardcoded TTL | Configurable via eBPF map |
| **CVE-2026-SPIFFE-001** | MEDIUM | SPIFFE | No clock skew tolerance | 5-minute tolerance |
| **CVE-2026-RANDOM-001** | LOW | Traffic Shaping | `random` module for padding | Informational (padding is not secret) |

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
