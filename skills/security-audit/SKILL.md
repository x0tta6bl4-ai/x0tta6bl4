---
name: security-audit
description: >
  Performs comprehensive security audit of x0tta6bl4 codebase covering
  post-quantum cryptography, zero-trust policies, SPIFFE identity, and
  OWASP Top 10. Use when user says "security audit", "check security",
  "review crypto", "scan for vulnerabilities", "PQC compliance check",
  or "zero-trust review".
metadata:
  author: x0tta6bl4
  version: 1.0.0
  category: security
  tags: [security, pqc, zero-trust, spiffe, audit]
---

# Security Audit for x0tta6bl4

## Instructions

CRITICAL: This audit must be thorough. Do not skip any section.
Quality is more important than speed.

### Phase 1: Cryptographic Compliance

Check post-quantum cryptography implementation:

1. **Key Encapsulation** (NIST FIPS 203):
   - Verify ML-KEM-768 is used (not classical RSA/ECDH alone)
   - Check: `src/security/pqc/`, `src/crypto/pqc_crypto.py`
   - Red flag: Any XOR cipher, RC4, DES, or custom crypto

2. **Digital Signatures** (NIST FIPS 204):
   - Verify ML-DSA-65 is used for signing
   - Check: `src/security/post_quantum.py`
   - Red flag: Hardcoded keys, missing signature verification

3. **Hybrid TLS**:
   - Verify classical + PQC hybrid mode
   - Check: `src/security/pqc/hybrid_tls.py`
   - Red flag: PQC-only without classical fallback

4. **Encryption at rest/transit**:
   - Must use AES-256-GCM (not AES-CBC, not XOR)
   - Check: `src/security/ebpf_pqc_gateway.py`
   - Verify nonce is 12 bytes, never reused

### Phase 2: Zero-Trust Validation

Review zero-trust architecture:

1. **SPIFFE Identity**:
   - Check `src/security/spiffe/` for proper SVID management
   - Verify certificate rotation is automatic
   - Verify trust domain validation in `spiffe_controller.py`

2. **Policy Engine**:
   - Check `src/security/policy_engine.py` for ABAC rules
   - Verify no bypass paths (all endpoints require auth)
   - Red flag: `if True`, hardcoded tokens, disabled auth checks

3. **Device Attestation**:
   - Check `src/security/device_attestation.py`
   - Verify trust scores use weighted average (not simple mean)
   - Verify adaptive trust decay on anomalies

4. **Certificate Validation**:
   - Check `src/security/spiffe/certificate_validator.py`
   - Must use `cert.verify_directly_issued_by()` (not name matching)
   - Verify chain-of-trust traversal

### Phase 3: OWASP Top 10 Scan

Check application code for common vulnerabilities:

1. **Injection** (A03:2021):
   - SQL: Check for raw SQL strings, f-string queries
   - Command: Check for `os.system()`, `subprocess.run(shell=True)`
   - Search: `src/api/`, `src/core/app.py`

2. **Broken Auth** (A07:2021):
   - Check admin token verification in `src/api/users.py`, `src/api/vpn.py`
   - Verify bcrypt for password hashing (not MD5/SHA1)
   - Check session token entropy (must be cryptographically random)

3. **Sensitive Data Exposure** (A02:2021):
   - Search for hardcoded secrets: API keys, passwords, tokens
   - Check `.env` files are in `.gitignore`
   - Verify no secrets in logs (`logger.info/debug`)

4. **Security Misconfiguration** (A05:2021):
   - Check CORS settings in middleware
   - Verify debug mode is off in production
   - Check for default credentials

5. **SSRF** (A10:2021):
   - Check any URL-fetching code accepts user input
   - Verify allowlists for external connections

### Phase 4: Network Security

1. **Traffic Obfuscation**:
   - Check `src/network/obfuscation/` for proper implementation
   - Verify no plaintext fallback paths
   - Check domain fronting configuration

2. **eBPF Programs**:
   - Check `src/network/ebpf/` for safe BPF program loading
   - Verify eBPF verifier is not bypassed

3. **Mesh Routing**:
   - Check `src/network/routing/mesh_router.py`
   - Verify TTL enforcement (prevent infinite loops)
   - Verify route authentication

## Output Format

Present findings as:

```markdown
## Security Audit Results

### Critical (must fix immediately)
- [Finding]: [File:Line] - [Description]

### High (fix before next release)
- [Finding]: [File:Line] - [Description]

### Medium (fix in next sprint)
- [Finding]: [File:Line] - [Description]

### Low (informational)
- [Finding]: [File:Line] - [Description]

### Passed Checks
- [Check]: [Status]
```

## References

Consult these files for context:
- `src/security/` - All security modules
- `src/network/obfuscation/` - Traffic obfuscation
- `src/api/` - API endpoints (attack surface)
- `tests/unit/security/` - Security test coverage
