# ISO/IEC 27001 Internal Audit Program (P2)

Version: 0.1  
Last updated: 2026-03-04  
Status: Draft audit program

## Audit Scope

The internal audit program covers:

- MaaS application and API controls.
- CI/CD security and release controls.
- Staging operations and incident handling.
- Cryptography and access control enforcement.
- Evidence retention and document control.

## Audit Schedule

| Audit window | Theme | Owner | Output |
|---|---|---|---|
| 2026-03-15 to 2026-03-22 | Readiness baseline simulation | Security + Platform | Internal audit report v0.1 |
| 2026-04-01 to 2026-04-07 | Incident and DR control testing | Platform Ops | Drill report + corrective actions |
| 2026-04-20 to 2026-04-26 | Access and cryptographic controls | Security | Control effectiveness report |

## Audit Procedure

1. Define audit objective and control set.
2. Collect evidence from `ISO_27001_2025_EVIDENCE_INDEX.md`.
3. Sample implementation artifacts, logs, and runbooks.
4. Record findings by severity (Major, Minor, Observation).
5. Create corrective action records with due dates.

## Finding Classification

| Severity | Description | SLA for action plan |
|---|---|---|
| Major | Control absent or ineffective for critical objective | 7 calendar days |
| Minor | Control partially implemented or inconsistent | 14 calendar days |
| Observation | Improvement recommendation without immediate failure | 30 calendar days |

## Corrective Actions

| Finding ID | Severity | Owner | Due date | Status | Evidence |
|---|---|---|---|---|---|
| CA-000 | Template | TBD | TBD | Open | Add link to remediation PR and verification output |
