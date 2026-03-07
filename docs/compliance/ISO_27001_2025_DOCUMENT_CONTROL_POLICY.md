# ISO/IEC 27001 Document Control Policy (P2)

Version: 0.1  
Last updated: 2026-03-04  
Status: Draft

## Purpose

Define how compliance documents are created, approved, versioned, retained, and referenced for audit readiness.

## Scope

Applies to all policy, risk, audit, and evidence documents under:

- `docs/compliance/`
- `docs/operations/` (security/continuity runbooks referenced by compliance)
- `docs/governance/proposals/` when used as compliance evidence inputs

## Versioning Rules

1. Each compliance document must include `Version`, `Last updated`, and `Status`.
2. Material changes require version increment and changelog note in commit message.
3. Documents must be referenced from `ISO_27001_2025_EVIDENCE_INDEX.md` when used as evidence.

## Ownership Rules

1. Every document must have an owner role (Security, Platform, Product, or Management).
2. Owner is responsible for quarterly review and stale-content remediation.
3. Unowned documents are considered non-compliant for audit purposes.

## Retention Rules

| Artifact type | Retention period | Storage reference |
|---|---|---|
| Policy documents | 3 years | Git history + release snapshots |
| Audit reports | 3 years | Compliance evidence bundles |
| Drill logs and test outputs | 18 months | Evidence bundles + linked proposal artifacts |
| Risk acceptance records | 3 years | Risk treatment plan attachments |

## Change and Approval Workflow

1. Draft changes in a PR with explicit control mapping impact.
2. Security review validates control intent and evidence linkage.
3. Management review (when required) records approval decision.
4. Update evidence index after merge.
