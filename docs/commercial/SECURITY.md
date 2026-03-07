# x0tta6bl4 MaaS — Security Reference

**Version:** v1.0.0 | SOC 2 Type II ready

---

## Post-Quantum Cryptography (PQC)

x0tta6bl4 implements NIST-standardised post-quantum algorithms:

| Algorithm | Role | Standard | Security Level |
|-----------|------|----------|---------------|
| Kyber-768 (ML-KEM) | Key Encapsulation (default) | FIPS 203 | Level 3 (AES-192) |
| Kyber-1024 (ML-KEM) | Key Encapsulation (enterprise) | FIPS 203 | Level 5 (AES-256) |
| Dilithium3 (ML-DSA) | Digital Signatures | FIPS 204 | Level 3 |
| Dilithium5 (ML-DSA) | Digital Signatures (high-sec) | FIPS 204 | Level 5 |

### Key Rotation
- Default rotation interval: **24 hours** (configurable via `pqc.keyRotationHours`)
- Emergency rotation: `POST /mesh/heal` with `strategy: pqc_rekey`
- Session caching: enabled by default to reduce overhead ~30%

### Handshake Flow
```
Client                     Mesh Node
  |--[ClientHello + ML-KEM pk]-->|
  |<--[ServerHello + ciphertext]-|
  |     (shared secret derived)  |
  |--[Encrypted payload]--->     |
  |   All subsequent traffic via AES-256-GCM with PQC-derived session key
```

---

## Zero-Trust Architecture

- **No implicit trust** between any components — all calls require auth
- JWT tokens are PQC-signed (Dilithium3) and validated at every hop
- RBAC roles: `mesh-admin`, `mesh-node`, `mesh-readonly` (see [ENTERPRISE.md](ENTERPRISE.md))
- mTLS between all internal services (Linkerd or Istio sidecar)
- Network policies enforce least-privilege pod-to-pod communication

---

## SBOM (Software Bill of Materials)

All release images include SPDX-format SBOM, cosign-attested:

```bash
# Verify image signature
cosign verify \
  --certificate-identity-regexp "https://gitlab.com/x0tta" \
  --certificate-oidc-issuer https://gitlab.com \
  registry.gitlab.com/x0tta/api-gateway:v1.0.0

# Inspect SBOM
cosign download attestation \
  registry.gitlab.com/x0tta/api-gateway:v1.0.0 \
  | jq '.payload | @base64d | fromjson | .predicate'
```

SBOM artifacts are attached to each GitLab Release and cover:
- All Python/Node.js direct and transitive dependencies
- OS packages (Debian Bookworm base via distroless)
- Go stdlib version

---

## Vulnerability Management

### Pipeline Gates (enforced, non-skippable)
| Scanner | Scope | Fail Condition |
|---------|-------|---------------|
| Trivy | Container images | Any CRITICAL CVE (ignoring unfixed) |
| Snyk | Python + Node.js deps | Any critical patchable vuln |
| detect-secrets | Source code | Any high-entropy secret pattern |
| semgrep | TypeScript / Python | OWASP Top 10 patterns |

### Patch SLA
| Severity | Response Time | Patch Time |
|----------|-------------|------------|
| Critical | 4 hours | 24 hours |
| High | 24 hours | 7 days |
| Medium | 5 days | 30 days |
| Low | 30 days | 90 days |

---

## Audit Logging

All security-relevant events are logged to an append-only audit trail:

```json
{
  "timestamp": "2026-03-06T12:00:00Z",
  "event": "mesh.node.registered",
  "actor": "user:alice@tenant.com",
  "resource": "node-abc123",
  "outcome": "success",
  "ip": "1.2.3.4",
  "pqc_session": "kyber768:session-xyz"
}
```

Audit logs are:
- Written to Loki with tamper-evident chaining (sha256 prev-hash)
- Retained for **90 days** (configurable, SOC 2 requires 1 year)
- Exportable via `GET /audit/events?from=...&to=...` (admin only)

---

## Compliance Checklist (SOC 2 Type II)

| Control | Implementation |
|---------|---------------|
| CC6.1 — Logical access | JWT + RBAC + Zero-Trust mTLS |
| CC6.2 — Auth controls | PQC-signed JWT, MFA enforced via IdP |
| CC6.7 — Encryption | AES-256-GCM + Kyber-768 key exchange (FIPS 203) |
| CC7.1 — Vulnerability scans | Trivy + Snyk in every CI pipeline |
| CC7.2 — Incident response | Alertmanager → PagerDuty → Runbooks |
| CC9.2 — Change management | GitLab MR → review → tag → chaos gate → blue-green |
| A1.1 — Availability SLA | 95% uptime, MTTR < 2.5s, chaos-tested |

---

## Security Contact

Report vulnerabilities: **security@x0tta6bl4.io** (PGP key available on keyserver).

Responsible disclosure: 90-day embargo. CVE coordination via MITRE.
