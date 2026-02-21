# CI Security Gates Policy

## Purpose

This document defines the fail-closed policy for security checks in CI/CD.

## Canonical Workflow

- Canonical required workflow: `.github/workflows/security-scan.yml`
- Canonical required job/check for branch protection: `Security Scan Summary`

## Blocking Rules

- Bandit: block PR/merge on HIGH or CRITICAL findings.
- Safety: block PR/merge when dependency vulnerabilities are reported.
- Pip-audit: block PR/merge when dependency vulnerabilities are reported.
- Workflow policy: block PR/merge when security workflows contain soft-fail patterns.
- Agent-cycle strict (`agent-2`): block PR/merge when the strict security-agent cycle fails.

## Advisory Rules

- Optional scans in auxiliary workflows (for example benchmark/deploy helpers) may remain non-blocking.
- Advisory scans must not override the canonical required workflow result.

## Branch Protection Configuration

For `main` branch protection, require passing checks for:

1. `Security Scan Summary` (from `security-scan.yml`, includes Bandit/Safety/Pip-audit/Workflow Policy/Agent-cycle strict).
2. Any additional org-mandated checks (tests/build/release).

If `Security Scan Summary` fails, merge must stay blocked until security issues are fixed or policy-approved exceptions are applied.

Automated policy validator:
- `scripts/validate_security_workflows.py`
- Executed by `Security Workflow Policy Check` job in `.github/workflows/security-scan.yml`.

## Finalization Checklist

- [x] Canonical security workflow is fail-closed for Bandit/Safety/Pip-audit.
- [x] Auxiliary security workflows do not bypass canonical security result.
- [ ] GitHub branch protection is configured for `main` with required check `Security Scan Summary`.

GitHub UI path:
`Settings -> Branches -> Branch protection rules -> main -> Require status checks to pass before merging`.

CLI/API option:
`GITHUB_TOKEN=<admin_token> scripts/set_required_security_check.sh --owner x0tta6bl4-ai --repo x0tta6bl4 --branch main`

GitHub Actions option:
- Run workflow `.github/workflows/enforce-branch-protection.yml` (`workflow_dispatch`).
- Provide repository secret `BRANCH_PROTECTION_TOKEN` with admin rights.
