# Execution Backlog (Q1 2026, Weeks 7-8)

**Date:** 2026-02-16  
**Scope window:** 2026-02-16 .. 2026-03-01  
**Objective:** convert roadmap items into an executable, dependency-aware sequence.

## Progress Snapshot (2026-02-16)

- ✅ Stream 2 initiated: `.github/workflows/security-scan.yml` switched to fail-closed behavior for Bandit/Safety/Pip-audit checks.
- ✅ Stream 2 expanded: fail-closed security checks propagated to `.github/workflows/ci.yml`, `.github/workflows/ci.yaml`, `.github/workflows/tests.yml`, `.github/workflows/ebpf-ci.yml`, `.github/workflows/spire-integration.yml` (security steps no longer use soft-fail patterns).
- ✅ Stream 2 finalized: `.github/workflows/ebpf-ci.yml` quality gate now blocks on failed `security-scan`, and canonical CI security policy is documented in `docs/02-security/ci-security-gates-policy.md`.
- ✅ Stream 2 hardened: `.github/workflows/deploy-mesh.yml` moved from placeholder script to real blocking scans (Bandit/Safety/Pip-audit/Trivy/TruffleHog).
- ✅ Stream 2 hardened: `.github/workflows/vault-deployment.yml` Trivy scan now blocks on HIGH/CRITICAL findings (`exit-code: 1`).
- ✅ Stream 2 hardened: `scripts/security-scan.sh` replaced with fail-closed scanner wrapper (Snyk/Trivy options).
- ✅ Stream 2 guarded: added automated workflow policy gate (`scripts/validate_security_workflows.py`) to fail CI on security soft-fail regressions.
- ✅ Stream 3 initiated: stable version `3.2.1` aligned in core runtime/test paths (`v3_endpoints`, `v3_metrics`, `ml.__version__`, `core.health`, relevant tests, `Dockerfile.production-simple`, MaaS log marker).
- ✅ Stream 3 extended: minimal runtime entrypoints in `src/core/app_minimal*` and `libx0t/core/app_minimal*` moved to `3.2.1`.
- ⏳ Remaining for Stream 3: full repository sweep of docs/examples/archive references that are not runtime-critical.

### Stream 2 Closure TODO (2026-02-16)

- [x] Make canonical `security-scan.yml` fail-closed for Bandit/Safety/Pip-audit.
- [x] Propagate fail-closed behavior into active CI workflows with security scans.
- [x] Remove placeholder/fake-pass security scan path from mesh deploy workflow.
- [x] Document canonical CI security gate policy in `docs/02-security/`.
- [x] Add repository script to configure required status check (`scripts/set_required_security_check.sh`).
- [x] Add manual GitHub Actions enforcer workflow (`enforce-branch-protection.yml`) for branch protection setup.
- [ ] Configure GitHub branch protection for `main` to require `Security Scan Summary` check.

---

## Prioritization Method

Score per stream:

`Priority Score = Business Impact + Production Risk Reduction + Deadline Urgency + Execution Readiness`

Each factor is 1-5 (max score = 20).

---

## Priority Order

| Priority | Stream | Score | Why now |
|---|---|---:|---|
| P0 | Grant submission completion | 20 | Hard deadline (Feb 20, 2026), immediate external impact |
| P0 | Security gates in CI (fail-closed) | 19 | Security scans run but mostly non-blocking (`|| true`, `continue-on-error`) |
| P0 | Version contract unification (v3 API/metrics/tests/images) | 18 | User-visible semantic drift across runtime, tests, Docker tags |
| P1 | SPIFFE/SPIRE staging validation + e2e checks | 16 | Core security capability exists in code, needs operational proof |
| P1 | Roadmap/documentation source-of-truth cleanup | 14 | Current plans conflict and create execution noise |
| P2 | God-object decomposition kickoff (real top offenders) | 12 | High long-term payoff, but lower immediate business urgency |
| P3 | Kimi/PARL/Vision roadmap execution | 9 | Strategic track, should start after production hygiene/stability |

---

## Stream 1 (P0): Grant Submission Completion

### Tasks
- Record 2-minute demo video per `docs/DEMO_SCRIPT.md`.
- Final grant package check against `docs/FSI_CHECKLIST.md`.
- Submit application and archive submission evidence.

### Owners
- GTM (primary), Architect (content validation), Dev/Ops (demo environment).

### Definition of Done
- Demo video exported and stored in project artifacts.
- Checklist is fully marked done.
- Submission confirmation (ID/email/screenshot) stored in `docs/`.

### Dependencies
- None.

---

## Stream 2 (P0): Security Gates in CI (Fail-Closed)

### Current blockers (fact-based)
- Many workflows run scans with `|| true` or `continue-on-error`.
- Examples: `.github/workflows/security-scan.yml`, `.github/workflows/ci.yml`, `.github/workflows/ci.yaml`, `.github/workflows/tests.yml`, `.github/workflows/ebpf-ci.yml`.

### Tasks
- Define one canonical security workflow and make it required for main branch.
- Remove `|| true` from Bandit/Safety/Pip-audit steps in required workflows.
- Keep optional/non-blocking scans only for auxiliary jobs (nightly/experimental).
- Add severity policy:
  - Block on: critical/high vulnerabilities and high-confidence Bandit findings.
  - Warn-only: medium/low (initially).

### Owners
- Ops (primary), Dev (fixes for failing checks), Architect (policy decisions).

### Definition of Done
- Required workflow fails on real security findings.
- Merge to protected branch is blocked when required security check fails.
- Policy documented in `docs/02-security/` or `docs/05-operations/`.

### Dependencies
- None.

---

## Stream 3 (P0): Version Contract Unification

### Current drift (fact-based)
- Runtime/API values diverge:
  - `src/api/v3_endpoints.py` uses `3.0.0`
  - `src/monitoring/v3_metrics.py` uses `3.0.0`
  - `src/ml/__init__.py` uses `3.3.0`
  - `Dockerfile.production-simple` uses `3.4.0`
  - `libx0t/core/app.py` contains `v3.4-alpha` log string
- Tests encode mixed expectations:
  - `tests/integration/test_v3_api.py`
  - `tests/unit/api/test_v3_endpoints_unit.py`
  - `tests/core/test_health_check.py`
  - `tests/unit/core/test_health.py`

### Tasks
- Approve one policy:
  - `Option A`: API semantic version fixed at `3.0.0`, runtime release separately.
  - `Option B`: API reports project release version (e.g., `3.2.1`).
- Update runtime + tests atomically to selected policy.
- Align Docker image tags and remove stale alpha strings from operational logs.

### Owners
- Architect (policy owner), Dev (implementation), QA/Dev (test updates).

### Definition of Done
- Single documented version policy.
- All affected tests green against policy.
- No stale `3.0.0/3.3.0/3.4.0/v3.4-alpha` leftovers in critical runtime paths.

### Dependencies
- Stream 2 in parallel, no hard dependency.

---

## Stream 4 (P1): SPIFFE/SPIRE Staging Validation

### Current state
- Codebase has extensive SPIFFE/SPIRE implementation.
- Deployment assets exist under `deployment/spire/`.
- Many unit tests exist in `tests/security/` and `tests/unit/test_spiffe_auto_renew.py`.

### Tasks
- Stand up staging using `deployment/spire/docker-compose.yml` (and/or Helm).
- Validate end-to-end:
  - SVID issuance,
  - workload API fetch,
  - mTLS handshake,
  - auto-renew.
- Add one concise runbook for staging bring-up and health checks.

### Owners
- Ops (primary), Security/Dev (test scenario support).

### Definition of Done
- Reproducible staging run command set.
- e2e verification report with timestamps and pass/fail matrix.
- Failover/renew path exercised at least once.

### Dependencies
- Stream 2 recommended before production rollout, not required for staging dry-run.

---

## Stream 5 (P1): Roadmap Source-of-Truth Cleanup

### Problem
- Planning docs contain conflicting statuses (done vs not started).
- Causes duplicate/redundant work and wrong priority calls.

### Tasks
- Pick one canonical planning entrypoint (proposed: `plans/` + `docs/roadmap.md`).
- Mark archived docs as historical and non-authoritative.
- Publish one live status table with:
  - owner,
  - status,
  - next milestone,
  - blocker.

### Owners
- Architect (primary), GTM (external narrative sync).

### Definition of Done
- One canonical roadmap file linked from root-level docs.
- Historical/archival plans clearly labeled.
- No contradictory status for top 10 initiatives.

### Dependencies
- None.

---

## Stream 6 (P2): God-Object Decomposition Kickoff (Reality-Based)

### Actual top files by size (current)
- `src/network/ebpf/telemetry_module.py` (1336)
- `src/core/meta_cognitive_mape_k.py` (1156)
- `src/network/ebpf/metrics_exporter.py` (1151)
- `src/self_healing/mape_k.py` (993)
- `src/network/routing/mesh_router.py` (986)
- `src/self_healing/recovery_actions.py` (882)

### Tasks
- Choose first target by risk/volatility (recommended: `telemetry_module.py`).
- Create module boundary ADR and extraction plan (interfaces first).
- Extract one slice with full test parity before continuing.

### Owners
- Dev (primary), Architect (boundary review), QA (regression checks).

### Definition of Done
- First extraction merged with no behavior regressions.
- Contract tests cover old/new entrypoints.
- Follow-up extraction backlog created.

### Dependencies
- Streams 1-4 have priority.

---

## Not-In-Scope for This 2-Week Window

- Full Kimi/PARL/Vision production rollout.
- Large-scale architectural migration (`v4`-style service split).
- Broad refactor across all large modules simultaneously.

---

## Week-by-Week Execution

### Week 7 (Feb 16-22)
- Complete Stream 1 (grant submission).
- Start Stream 2 (enable blocking security checks in required CI).
- Finalize version policy decision for Stream 3.

### Week 8 (Feb 23-Mar 01)
- Complete Stream 3 (runtime+tests version unification).
- Execute Stream 4 staging validation (SPIFFE/SPIRE e2e).
- Publish Stream 5 canonical roadmap status file.

---

## Immediate Next 3 Actions

1. Approve version policy (`Option A` vs `Option B`) for Stream 3.
2. Select required security workflow to enforce branch protection (recommended: `security-scan.yml`).
3. Assign owners and ETAs for Streams 1-4 in one short standup note.
