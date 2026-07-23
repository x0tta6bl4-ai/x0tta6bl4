# PQC Module Release Criteria v1.0 & Verification Gate

**Module**: `src.security.pqc`  
**Platform**: x0tta6bl4 Mesh Network  
**Status**: APPROVED & SEALED  
**Date**: 2026-07-23  

---

## 1. Definition of Done (DoD) Checklist

### Architecture
- [x] **Thin Facade**: `simple.py` serves strictly as a declarative, unified API.
- [x] **Compatibility Layer**: Legacy tuple ordering `(shared_secret, ciphertext)` is isolated inside `compat.py`.
- [x] **Single Responsibility Principle**: Cryptography, key storage, and legacy adapters have isolated responsibilities.
- [x] **No Heuristic Dispatch**: Removed raw byte length comparisons and dynamic `hasattr`/`getattr` lookups.
- [x] **Explicit Type Contracts**: Full support for `PQCKeyPair`, `PQCEncapsulationResult`, and `PQCSignature`.

### Quality & Verification
- [x] **Linter Cleanliness**: 100% compliance with `ruff check`.
- [x] **Unit Testing**: All unit test suites (`test_pqc_core.py`, `test_pqc_unified.py`) passing with Exit Code 0.
- [x] **Property-Based Testing**: Hypothesis fuzzing tests (`test_pqc_invariants_hypothesis.py`) covering 0–4096 byte bounds.
- [x] **Negative Testing**: Bit-flip mutations in messages and signatures strictly fail verification.

### Cryptographic Security & Hardening
- [x] **Cross-Algorithm Injection Defense**: Submitting KEM keys to `sign()` raises immediate `TypeError`.
- [x] **Malformed Ciphertext Resilience**: Robust error handling without CPython crashes (Segmentation Faults).
- [x] **No Broad Exception Traps**: Specific exceptions (`ValueError`, `RuntimeError`, `TypeError`) captured explicitly.
- [x] **Domain Key Check**: Native `PQCKeyPair.is_dsa()` and `PQCKeyPair.is_kem()` methods implemented.

### Documentation
- [x] **ADR-001**: Architecture Decision Record created (`docs/architecture/adr/ADR-001_PQC_Facade_and_Compatibility.md`).
- [x] **Public API Documented**: Clear docstrings and type annotations across all submodules.

---

## 2. Outstanding Roadmap (Post-v1.0 Backlog)

- [ ] **Real liboqs C-Binding CI Job**: Dedicated GitHub Actions pipeline compiling native `liboqs`.
- [ ] **Mutation Testing (`mutmut`)**: Execution of automated mutation suites to measure test killing efficacy.
- [ ] **Differential Testing**: Parallel test harness comparing mock backend output against native `liboqs`.
- [ ] **Zeroization Research**: Evaluation of CPython memory zeroing strategies (`bytearray`, native C wrappers).

---

## 3. Next Major Engineering Focus Allocation

1. **40%** — MAPE-K Self-Healing Automated Evidence Gate & Failure Recovery Proofs.
2. **30%** — End-to-End Validation Framework v2 (Mesh Topology, SVID Rotation, Network drops).
3. **20%** — eBPF Dataplane Benchmarks & Failover Latency Verification (< 1.5s recovery).
4. **10%** — Advanced PQC Hardening (Mutation & Differential Testing).
