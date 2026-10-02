# Recovery follow-up — 2026-10-02

Parent remote commit: 890dc1a0d70c7f6b1744d0fe083eab312d8d1fe1.

170 unit tests and 4 integration tests pass with mocked OS backends. Reproduce:
`bash scripts/validation/verify_recovery_contract.sh` in the previously recorded
Python environment. Local readiness uses --skip-git-check; no live recovery claim.

Rollback now builds an inverse context for scaling and route changes. It uses
explicit previous replicas/route, keeps failed or denied entries, and suppresses
recording the inverse as another rollback. Scaling wrappers no longer fabricate
previous replicas as desired +/- 1. Unsupported inverse actions are refused.
These changes do not establish thread safety, crash persistence, or convergence;
previous state supplied by a caller is not independently observed by this executor.

CI diagnosis from GitHub job 110579350928: dependency setup failed with
Cannot import 'setuptools.build_meta' before tests ran. Unit Tests CI now installs
setuptools/wheel plus the native build prerequisites already used by the successful
primary CI. This fixes the observed setup omission, not every possible downstream
suite failure. Golden Smoke Premerge had no trigger and invalid workflow-level if;
it is now a valid manual-only placeholder, preserving its existing role.

Primary CI run 36924796601 passed on the parent commit. Full unit CI status for
this follow-up must be checked on the new commit; the full suite is not yet certified.
