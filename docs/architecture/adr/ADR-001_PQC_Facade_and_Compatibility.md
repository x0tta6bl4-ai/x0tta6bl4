# ADR-001: PQC Facade & Compatibility Adapter Architecture

## Status
Accepted (2026-07-23)

## Context
The x0tta6bl4 platform utilizes NIST FIPS 203 (ML-KEM-768) and FIPS 204 (ML-DSA-65) post-quantum cryptography standards. 
As legacy modules and older test suites depended on tuple-based contracts `(shared_secret, ciphertext)` and simple class interfaces, a compatibility layer was needed without compromising the type-safety of the modern canonical `src.security.pqc` package.

## Decision
1. **Single Responsibility Principle for Adapters**:
   - `src.security.pqc.simple.PQC` serves purely as an ultra-thin, declarative facade.
   - Normalization of legacy tuple formats `(ciphertext, shared_secret)` -> `(shared_secret, ciphertext)` is strictly encapsulated within `src.security.pqc.compat.PQCKeyExchange.encapsulate_legacy()`.

2. **Strict Type Annotations**:
   - Avoid `typing.Any` and dynamic `hasattr`/`getattr` lookups.
   - Use explicit `isinstance` checks against `PQCKeyPair` and `PQCEncapsulationResult` data classes.

3. **Verification Invariants**:
   - Every PQC interface modification must be verified using Property-Based testing (Hypothesis) ensuring roundtrip equality (`decapsulate(encapsulate(pk)) == shared_secret`).

## Consequences
- **Positive**: Clean separation of responsibilities, zero heuristic length-based logic, strict type-checking compatibility with `mypy` and `ruff`.
- **Negative**: Maintainers must preserve `encapsulate_legacy()` until all historical test callers migrate to `PQCEncapsulationResult`.
