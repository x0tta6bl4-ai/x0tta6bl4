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
| Security governance and policy | Partial | `docs/02-security/ci-security-gates-policy.md` | Unified top-level information security policy and policy review cycle |
| Risk management | Partial | `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`, `docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md` | Formal risk acceptance criteria and periodic management sign-off |
| Secure engineering and change control | Implemented (technical) | `.github/workflows/golden-smoke-premerge.yml`, `docs/operations/GOLDEN_SMOKE_PREMERGE.md`, `scripts/check_migration_policy.py` | Complete release evidence retention and reproducible build attestations |
| Incident response and continuity | Partial | `docs/team/INCIDENT_RESPONSE_PLAN.md`, `docs/runbooks/INCIDENT_RESPONSE.md`, `docs/operations/DISASTER_RECOVERY_PLAN.md` | Regularly recorded tabletop/drill evidence with measured RTO/RPO outcomes |
| Access control and cryptography | Partial | `src/core/mtls_middleware.py`, `src/security/pqc_hybrid.py`, `src/security/spiffe/` | Periodic access recertification records and key-management procedure approvals |
| Logging and monitoring | Partial | `src/core/logging_config.py`, `src/core/structured_logging.py`, `docs/operations/CONFIGURATION_GUIDE.md` | Verified no-sensitive-data logging evidence and complete SLO alert coverage |

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
