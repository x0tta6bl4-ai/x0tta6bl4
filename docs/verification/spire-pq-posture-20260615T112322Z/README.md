=== SPIRE PQ Posture Analysis ===

Date: 20260615T112322Z

## Status: PARTIAL

## What Exists

1. **SPIRE HA Runtime with PQC Plugin** (2026-05-19)
   - 3 SPIRE servers with HA configuration
   - PQC plugin loaded as UpstreamAuthority
   - Agent node attestation successful
   - X509-SVID created for workload

2. **PQC SPIFFE Bridge** (src/security/pqc_spiffe.py)
   - Bridges SPIRE X.509 SVIDs with PQC (ML-DSA/Dilithium)
   - Generates PQC-SVID bundles with ZKP attestation

## What's Missing

1. **PQ OIDs in leaf SVID** — The PQC plugin is an UpstreamAuthority (CA), not a leaf SVID modifier.
   - Leaf SVIDs are standard X.509 without PQ OIDs
   - No evidence of PQ OIDs embedded in leaf certificates

2. **ML-KEM in SPIRE mTLS handshake** — No evidence of ML-KEM key exchange in TLS handshake.
   - Standard TLS 1.3 with classical key exchange
   - No ML-KEM encapsulation in handshake

3. **Detached PQ Attestation** — PQC public keys are attested separately, not embedded in X.509.
   - PQC-SVID bundle contains separate PQ keys
   - ZKP attestation proves PQ key ownership
   - But this is NOT the same as PQ OIDs in leaf SVID

## Release Gate Assessment

The release gate states:

> 8. SPIRE PQ posture is currently evidenced as 'standard leaf SVID + detached PQ attestation artifact';
> this does not justify claims about PQ OIDs inside the leaf or ML-KEM inside the SPIRE/TLS handshake.

This assessment is accurate:
- ✅ Standard leaf SVID (X.509) exists
- ✅ Detached PQ attestation artifact exists (PQC-SVID bundle)
- ❌ PQ OIDs inside leaf SVID — NOT evidenced
- ❌ ML-KEM inside SPIRE/TLS handshake — NOT evidenced

## Conclusion

Blocker #8 cannot be fully closed without:
1. SPIRE plugin that embeds PQ OIDs in leaf SVIDs
2. Or evidence of ML-KEM in SPIRE mTLS handshake

Current state: 'standard leaf SVID + detached PQ attestation artifact'

### Artifacts

- SPIRE HA logs: `docs/verification/live002-spire-ha-runtime-20260519-real-pqc-bundle/logs/`
- PQC SPIFFE bridge: `src/security/pqc_spiffe.py`
- This document: `docs/verification/spire-pq-posture-20260615T112322Z/README.md`
