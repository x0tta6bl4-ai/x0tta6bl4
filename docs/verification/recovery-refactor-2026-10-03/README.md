# MAPE-K startup and CI dependencies

The MAPE-K executor now imports its canonical recovery implementation regardless
of previous imports. ImportError still disables actions; constructor failures
remain visible instead of silently selecting another executor. Explicit event
buses are preserved even when they are falsey.

Verified locally: 148 MAPE-K unit tests, including a fresh interpreter startup,
constructor failure visibility, and bus propagation. Recovery validation script:
174 unit tests + 4 integration tests passed. The cold-start regressions are now
part of that CI script. These tests do not execute live recovery backends.

Remaining failures in the broader self-healing suite include manager event
metadata/context propagation and missing action_cooldown_seconds support; the
whole suite is not green.

Previous remote head d9dfb638780e277a1f917f16fc8ac7db091f991d advanced security
CI to 769 passed, 102 skipped, 3 failures and 2 errors. The reported blockers
required liboqs. Native liboqs 0.16.0 is now pinned to upstream commit
5a1a854b0dc9f2141bdc771c555ee60c37950183, with liboqs-python 0.16.0.1, and a
real signature/tamper preflight before pytest. Validation of that installation
and remaining security tests is pending CI; no cryptographic test is replaced
by a success mock.

Dependency sources:
- https://github.com/open-quantum-safe/liboqs/tree/5a1a854b0dc9f2141bdc771c555ee60c37950183
- https://github.com/open-quantum-safe/liboqs-python/releases/tag/0.16.0.1

## Follow-up: native PQC contract and bounded cooldown

Remote CI at b195760cdece15330da1dc46d05206529732f2f6 passed its native
liboqs build/signature preflight and primary CI workflow. The full security
suite advanced to 928 passed, 11 skipped, 5 failures: three facade invariants
and two scanner executable fixtures.

The simple PQC facade now returns signature bytes as documented, normalizes
ML-DSA-65 keypairs, and rejects incompatible typed keys before calling native
code. Secret keys are excluded from PQCKeyPair repr. Six facade/scanner tests
pass locally; these are representation/fixture tests, not native crypto proof.
Native tamper Hypothesis tests are retained for CI verification.

Manager cooldown is now finite and uses an injectable monotonic clock. It
applies globally to this manager instance, including failed/raising backends;
expiry permits retry while an anomaly persists. Zero disables the time delay.
Execution receives the manager's authoritative node ID and its event bus.
Exception paths clean up timing records and re-raise the original error.

157 selected tests passed (followup-tests.txt); recovery script passed 181 unit
and 4 integration tests (recovery-tests.txt). Remaining manager event schema,
verification lifecycle and downstream evidence-correlation failures are not
claimed fixed. Healthy telemetry alone is not a dataplane restoration proof.
