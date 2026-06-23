# Formal Specification: PQC Key Rotation Safe Handover

**Status**: AlphaProof Nexus Blueprint v1.1
**Context**: x0tta6bl4 Trust Plane Verification

## 1. Abstract State Machine (PQC-ASM)

PQC key rotation transitions through a strict sequence to ensure connectivity is never lost.

| State | Description | Transitions To |
| :--- | :--- | :--- |
| `STABLE` | Current keys are valid and verified. | `GENERATING` (on rotation trigger) |
| `GENERATING` | New PQC key pair is being generated. | `STAGING` (on success) |
| `STAGING` | New keys are staged but not yet active. | `VERIFYING` |
| `VERIFYING` | New keys are self-tested and signed. | `COMMITTING` (on proof) |
| `COMMITTING` | New keys replace old keys in identity file. | `STABLE` |
| `TRUST_FAILURE` | Error during rotation; old keys retained. | `STABLE` (after cleanup) |

## 2. Formal Invariants (Trust Safety)

### T1: `Invariant_Safe_Handover` (Atomic Swap)
$Keys_{new} \text{ replaces } Keys_{old} \iff \text{Proof}(Keys_{new}) = \text{VALID}$
*   The old identity file MUST NOT be overwritten until the new keys have passed the internal verification/signing loop.

### T2: `Invariant_Key_Freshness`
$\forall k \in Keys, \text{Timestamp}(k) \ge \text{Now} - \text{MaxAge}$
*   Keys must be rotated within the `ROTATION_INTERVAL`.

### T3: `Invariant_Signer_Integrity`
$\text{Rotate}(Keys) \implies \text{Sign}(Keys, \text{Algorithm}) \text{ where Algorithm} \in \{\text{ML-DSA-65}, \dots\}$
*   Only approved quantum-resistant algorithms can be used for the rotation signature.

## 3. Nexus Trust Proof

Every rotation emits a `TrustProofFragment`:
1.  **Staging Hash**: $H(Keys_{staged})$.
2.  **Verification Vector**: Metadata from `pqc_signer.py` success.
3.  **Final Commitment**: Atomic move from `.new` to stable path.
