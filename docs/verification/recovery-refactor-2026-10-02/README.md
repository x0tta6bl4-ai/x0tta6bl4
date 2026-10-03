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

Follow-up: CI job 110751278424 successfully installed runtime dependencies, then
collection failed because hypothesis was absent. It is now explicitly installed
with the test tools. The global autouse fixture no longer imports governance_script
for unrelated tests; it patches the module only when already loaded. The same
170 unit + 4 integration tests pass under ordinary pytest with root conftest enabled
(see global-fixtures.txt). Full security suite is still pending CI.

### SPIFFE/SPIRE follow-up

Removed production subprocess resolver's TESTING/PYTEST_CURRENT_TEST fallback:
missing executables now fail closed instead of manufacturing a path. Absolute
ip/tc paths now receive the same subcommand validation as bare names. Explicit
absolute executable paths and PATH lookup remain supported as before; this is
not a complete executable trust-policy redesign.

SPIRE filters unsafe inherited injection variables before strict validation,
while retaining its join token. Restored the explicitly named mock X509 helper;
its placeholder bytes are not valid credentials or real SPIRE evidence.

Tests now explicitly provide mocked executable lookup, assert shell=False, and
model process termination independently of poll count. The spine success test
uses a real Unix socket instead of a regular file. No socket test is skipped.

Local evidence: 75 SPIFFE tests passed, 3 failed because this executor denies
AF_UNIX socket creation (spiffe-local.txt); 6 targeted regression tests passed
(spiffe-regressions.txt). Recovery verification remains 170 unit + 4 integration
passed. The three socket cases require CI validation. These are unit tests with
mocked SPIRE processes, not live SPIRE integration or production certification.
