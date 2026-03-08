# ISO/IEC 27001 Evidence Index

Version: 0.1  
Last updated: 2026-03-04  
Purpose: Traceable list of evidence artifacts for readiness and pre-audit.

## Evidence Collection Rules

1. Keep each evidence item traceable to a file path or command output.
2. Store collection date, collector, and commit SHA for each snapshot.
3. Do not include secrets in evidence exports.

## Core Evidence Set

| Evidence ID | Domain | Artifact | Source | Collection method |
|---|---|---|---|---|
| E-001 | Scope/status baseline | Capability and reality status | `docs/STATUS.md`, `STATUS_REALITY.md` | Attach file snapshot with commit SHA |
| E-002 | Release gate policy | Master readiness backlog and open blockers | `plans/MASTER_100_READINESS_TODOS_2026-02-26.md` | Attach file snapshot with commit SHA |
| E-003 | Security gate policy | CI security fail-closed policy | `docs/02-security/ci-security-gates-policy.md` | Attach file snapshot |
| E-004 | Vulnerability management | Security scan workflow definition | `.github/workflows/security-scan.yml` | Export YAML + last run log |
| E-005 | Secure SDLC gate | Golden smoke pre-merge workflow | `.github/workflows/golden-smoke-premerge.yml` | Export YAML + last run log |
| E-006 | Schema/change safety | Migration policy and gate scripts | `docs/operations/MIGRATION_POLICY.md`, `scripts/check_migration_policy.py` | Run script and capture output |
| E-007 | DB recoverability | DB rollback runbook and bootstrap check | `docs/operations/db-migration-rollback-runbook.md`, `scripts/check_db_bootstrap_chain.py` | Run script and capture output |
| E-008 | Incident response | Incident plan and runbooks | `docs/team/INCIDENT_RESPONSE_PLAN.md`, `docs/runbooks/INCIDENT_RESPONSE.md` | Attach docs + drill record |
| E-009 | Continuity/DR | Disaster recovery plan | `docs/operations/DISASTER_RECOVERY_PLAN.md` | Attach plan + drill execution record |
| E-010 | Access control enforcement | API authz controls and tests | `src/api/maas_security.py`, `tests/unit/api/test_maas_rbac_critical_endpoints_unit.py` | Attach test output |
| E-011 | Cryptographic controls | PQC + mTLS implementation paths | `src/security/pqc_hybrid.py`, `src/core/mtls_middleware.py` | Attach code review record + test output |
| E-012 | Logging and monitoring | Structured logging and masking | `src/core/logging_config.py`, `src/core/structured_logging.py` | Attach config snapshot + log sample (sanitized) |
| E-013 | Environment hardening | Default/fail-closed env checks | `scripts/check_env_security_defaults.py` | Run script and capture output |
| E-014 | Operational monitoring | Monitoring setup and runbooks | `docs/operations/CONFIGURATION_GUIDE.md`, `scripts/production_monitor.py` | Attach dashboard snapshots + alert config |
| E-015 | Policy governance | Unified policy ownership index | `docs/compliance/ISO_27001_2025_POLICY_INDEX.md` | Attach approved index and review record |
| E-016 | Risk governance | Risk acceptance criteria and sign-off template | `docs/compliance/ISO_27001_2025_RISK_ACCEPTANCE_CRITERIA.md` | Attach signed acceptance records |
| E-017 | Internal assurance | Internal audit schedule and corrective action register | `docs/compliance/ISO_27001_2025_INTERNAL_AUDIT_PROGRAM.md` | Attach audit run output and CA closure evidence |
| E-018 | Document governance | Document control and retention policy | `docs/compliance/ISO_27001_2025_DOCUMENT_CONTROL_POLICY.md` | Attach policy approval and periodic review record |

## Recommended Collection Commands

```bash
# 1) Security scan logs (local)
python scripts/validate_security_workflows.py

# 2) Env security defaults
python scripts/check_env_security_defaults.py

# 3) Migration safety
python scripts/check_migration_policy.py --depth 3

# 4) DB bootstrap roundtrip
python scripts/check_db_bootstrap_chain.py --validate-downgrade --downgrade-steps 3

# 5) Golden smoke quick gate
bash scripts/golden_smoke_premerge.sh quick

# 6) Compliance package completeness
python3 scripts/ops/check_iso27001_p2_readiness.py
```

## Evidence Packaging Template

```bash
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SHA="$(git rev-parse --short HEAD)"
OUT="evidence/iso27001/${STAMP}_${SHA}"
mkdir -p "${OUT}"

cp docs/compliance/ISO_IEC_27001_2025_READINESS.md "${OUT}/"
cp docs/compliance/ISO_27001_2025_SOA.md "${OUT}/"
cp docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md "${OUT}/"
cp docs/compliance/ISO_27001_2025_EVIDENCE_INDEX.md "${OUT}/"

tar -czf "${OUT}.tar.gz" -C "$(dirname "${OUT}")" "$(basename "${OUT}")"
```

## Open Evidence Gaps

1. Signed management review minutes and explicit approvals.
2. Completed internal audit execution report (program currently planned).
3. Periodic access recertification report.
4. DR drill logs proving target RTO/RPO in current environment.
