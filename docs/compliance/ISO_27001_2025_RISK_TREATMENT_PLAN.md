# ISO/IEC 27001 Risk Treatment Plan

Version: 0.1  
Last updated: 2026-03-04  
Status: Active risk treatment register for readiness.

## Treatment Method

- Risk scale (qualitative): `High`, `Medium`, `Low`.
- Priority: High risks require owner + dated action + verification artifact.
- Closure rule: risk can be closed only with evidence linked in `ISO_27001_2025_EVIDENCE_INDEX.md`.

## Active Risks

| Risk ID | Risk statement | Severity | Related controls | Treatment action | Owner | Target date | Verification artifact |
|---|---|---|---|---|---|---|---|
| R-001 | ISMS governance artifacts are fragmented and not approved as a single policy set | High | A.5.1, A.5.2 | Publish unified IS policy index with approvers and review cadence (draft done, approval pending) | Security Lead | 2026-03-21 | `docs/compliance/ISO_27001_2025_POLICY_INDEX.md` + approval record |
| R-002 | No formalized risk acceptance criteria and management sign-off workflow | High | Clause 6, Clause 9 | Define risk acceptance thresholds and sign-off process (draft done, sign-off pending) | Product + Security | 2026-03-28 | `docs/compliance/ISO_27001_2025_RISK_ACCEPTANCE_CRITERIA.md` + signed acceptance record |
| R-003 | Incident/DR procedures exist but drill evidence is incomplete for audit trail | High | A.5.24, A.5.26, A.5.30, A.8.13 | Run one incident drill + one DR drill and store outcomes | Platform Ops | 2026-03-31 | Drill reports with measured RTO/RPO |
| R-004 | Log hardening is present, but proof of no-sensitive-data leakage is incomplete | Medium | A.8.15, A.8.16 | Add repeatable log scrubbing validation and retain results | Platform | 2026-03-24 | Validation output + retained report |
| R-005 | Access recertification process is not documented as a periodic control | Medium | A.5.15, A.5.18 | Define quarterly access review for critical roles and APIs | Security + API Owners | 2026-04-04 | Access review report template + first run |
| R-006 | Cloud/supplier shared-responsibility matrix is not formalized | Medium | A.5.23, A.5.31 | Create supplier security responsibility matrix and legal register | Operations + Legal | 2026-04-11 | Approved supplier matrix |
| R-007 | Reproducible build attestations are not yet part of standard release evidence | Medium | A.8.25, A.8.32 | Add build reproducibility check and release attestation record | Release Engineering | 2026-04-18 | CI attestation artifact linked in release |

## Already Mitigated (Baseline)

| Control area | Mitigation in place | Evidence |
|---|---|---|
| Migration safety | Idempotent + downgrade policy checks in CI | `scripts/check_migration_policy.py`, `scripts/check_db_bootstrap_chain.py` |
| Security scanning | Bandit/Safety/pip-audit in dedicated workflow | `.github/workflows/security-scan.yml` |
| Runtime contract gates | Golden smoke pre-merge + API compatibility checks | `scripts/golden_smoke_premerge.sh`, `scripts/check_api_model_compat.py` |
| Env secret defaults | Fail-closed checks for insecure env defaults | `scripts/check_env_security_defaults.py` |

## Review Cadence

- Weekly: risk status review in engineering/security sync.
- Bi-weekly: update treatment status and evidence links.
- Monthly: management review of open high risks.
