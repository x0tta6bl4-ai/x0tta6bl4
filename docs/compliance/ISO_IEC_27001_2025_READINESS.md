# ISO/IEC 27001:2025 Readiness Report

Document owner: Security + Platform  
Last updated: 2026-03-04  
Status: In progress (P2 documentation baseline)

## Scope

Scope for this readiness package:

- Repository: `x0tta6bl4`
- Environments: local CI + staging (`staging/docker-compose.quick.yml`)
- Core domains: MaaS API, security controls, release engineering, observability, operational runbooks

Important note:

- In this repository, "`ISO/IEC 27001:2025 readiness`" is used as an internal audit-readiness label.
- Control mapping in this pack is aligned to ISO/IEC 27001 Annex A control structure used by the project documentation set.

## Executive Baseline

| Area | Current status | Evidence baseline | Main gap to close |
|---|---|---|---|
| ISMS context and scope | Partial | `docs/STATUS.md`, `STATUS_REALITY.md`, this file | Formal approved ISMS scope statement with asset boundaries and exclusions |
| Security governance and policy | Partial | `docs/02-security/ci-security-gates-policy.md`, `docs/compliance/ISO_27001_2025_POLICY_INDEX.md` | Complete management approval records and review execution evidence |
| Risk management | Partial | `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`, `docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md`, `docs/compliance/ISO_27001_2025_RISK_ACCEPTANCE_CRITERIA.md` | Periodic management sign-off records for accepted risks |
| Secure engineering and change control | Implemented (technical) | `.github/workflows/golden-smoke-premerge.yml`, `docs/operations/GOLDEN_SMOKE_PREMERGE.md`, `scripts/check_migration_policy.py` | Complete release evidence retention and reproducible build attestations |
| Incident response and continuity | Implemented (Self-healing) | `src/self_healing/mape_k.py`, `docs/META_COGNITIVE_MAPE_K.md` | Autonomous self-healing (MAPE-K) aligned with NIS2/ISO automated response requirements |
| Access control and cryptography | Implemented (PQC) | `src/security/pqc/`, `src/security/spiffe/`, `tests/test_maas_pqc_e2e_microsegmentation.py` | NIST 2026 compliance verified via E2E tests for ML-KEM-768/ML-DSA-65 |
| Logging and monitoring | Implemented | `src/monitoring/v3_metrics.py`, `src/core/structured_logging.py`, `docs/operations/CONFIGURATION_GUIDE.md` | Verified no-sensitive-data logging evidence and complete SLO alert coverage for MaaS |

## 🛠 MaaS-Specific Controls (Compliance 2026)

### 1. Post-Quantum Readiness (ISO 27001:2025 Annex A.8.24)
- **Status:** Fully Implemented.
- **Mechanism:** Hybrid PQC-TLS tunnels using ML-KEM-768 and ML-DSA-65.
- **Evidence:** Successful E2E verification of quantum-resistant micro-segmentation in version 3.4.0.

### 2. Zero-Trust Mesh Identity (ISO 27001:2025 Annex A.8.22)
- **Status:** Implemented via SPIRE/SPIFFE.
- **Mechanism:** Cryptographically verifiable SVIDs for every mesh node with automated rotation every 12h.
- **Evidence:** `src/security/spiffe/production_integration.py` and real-time identity audit logs.

### 3. Automated Resilience (ISO 27001:2025 Annex A.8.16)
- **Status:** Active via MAPE-K loops.
- **Mechanism:** Self-healing network topology updates without manual intervention, maintaining ISO continuity standards.
- **Evidence:** `src/self_healing/mape_k_v3_integration.py` and incident-auto-remediation logs.

## Readiness Decision

Current state is suitable for:

- Internal readiness tracking
- Pilot due diligence with explicit caveats
- Audit preparation workstream kickoff

Current state is not yet sufficient for:

- Claiming completed ISO certification
- Claiming full ISMS audit readiness without outstanding actions in risk treatment plan

## Required Artifacts Before External Audit

1. Approved information security policy set (single source of truth).
2. Formal ISMS scope statement, boundaries, interfaces, and exclusions.
3. Signed risk assessment methodology and risk acceptance criteria.
4. Complete Statement of Applicability with approval records.
5. Internal audit schedule + records + corrective actions.
6. Management review records with decisions and resource allocation.
7. Evidence retention and document control policy (versioning, retention, owners).

## 30/60/90 Day Plan

### Day 0-30

1. Finalize SoA and risk treatment ownership.
2. Build audit-ready evidence bundle from `ISO_27001_2025_EVIDENCE_INDEX.md`.
3. Establish single policy index and review cadence.

### Day 31-60

1. Run one full internal audit simulation.
2. Run one DR and one incident-response drill with recorded outcomes.
3. Close high-priority risks from the treatment plan.

### Day 61-90

1. Perform management review with sign-offs.
2. Validate remediation evidence closure.
3. Freeze readiness package for pre-assessment.

## Linked Documents

- [Statement of Applicability](ISO_27001_2025_SOA.md)
- [Evidence index](ISO_27001_2025_EVIDENCE_INDEX.md)
- [Risk treatment plan](ISO_27001_2025_RISK_TREATMENT_PLAN.md)
- [Policy index](ISO_27001_2025_POLICY_INDEX.md)
- [Risk acceptance criteria](ISO_27001_2025_RISK_ACCEPTANCE_CRITERIA.md)
- [Internal audit program](ISO_27001_2025_INTERNAL_AUDIT_PROGRAM.md)
- [Document control policy](ISO_27001_2025_DOCUMENT_CONTROL_POLICY.md)
