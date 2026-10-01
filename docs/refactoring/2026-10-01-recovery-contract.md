# Refactoring programme: recovery contract, increment 1

Base: `f77b49308f1085e0003e037f63119e382efd2d66`.
This is a scoped first increment, not a completed repository-wide refactor.

## Why this first

Recovery metrics cannot be trusted when a log-only action is reported as success.
The inspected code also treated `RecoveryResult(success=False)` as a circuit-breaker
success, and public async convenience methods bypassed policy and history.
The local source tree contains multiple MAPE-K implementations; replacing them
all before establishing execution contracts would increase regression risk.

## Behaviour and compatibility

- `RecoveryActionType` is a Python 3.11+ `StrEnum`, preserving string values while
  restoring enum iteration and `.value` expected by existing tests.
- Canonical action strings (including `scale_up` and `scale_down`) are parsed before
  legacy free-text aliases. Dispatch is centralized; scale up/down share one handler.
- Missing restart/routing/scaling/protocol backends and unimplemented cache,
  failover and quarantine actions return **false**, with `method=unavailable`.
  This intentionally changes old simulated-success behaviour. A fake backend in
  an orchestration unit test must be explicit.
- Async convenience methods retain their signatures and call the synchronous
  policy/rate-limit/circuit-breaker/history path. They remain blocking wrappers;
  no thread-safety or asynchronous execution guarantee is introduced.
- Scaling honors deployment name and namespace and rejects invalid replica counts.
  A zero exit status proves command submission only, not convergence or recovery.
- The generic breaker accepts an optional failure predicate. The recovery executor
  uses it to count unsuccessful results. Half-open probes require fresh consecutive
  successes. False results are not automatically retried (avoid duplicate effects).
- Durations use `time.monotonic`; timestamps remain wall-clock timestamps.
- Rate-limit denials update `last_result` and history. Event-publication failures
  are logged without retrying already-completed commands. Durable event delivery
  remains unimplemented; consumers must not infer delivery from execute's return.
- Legacy import exports remain available. No new runtime dependency was introduced.

## Verification and limits

Run `bash scripts/validation/verify_recovery_contract.sh` using the project's Python
3.11+ development environment. The tests mock backend probes and command execution;
the integration tests use a real local EventBus. `--confcutdir` intentionally excludes
unrelated global fixtures that replace cryptographic and other dependencies.

Evidence is in `docs/verification/recovery-refactor-2026-10-01/`.
The original two-file isolated suite returned 85 passed / 13 failed. Old tests
patched a removed shim's `datetime`, assumed enum behaviour absent in production,
expected never-emitted events, or mocked the wrong command layer. These tests were
migrated; orchestration tests now provide explicit successful fake handlers.

The regular global-fixture test invocation initially failed during setup on
`src.dao.governance_script`. The full test suite, live Docker/systemd/Kubernetes,
PQC, eBPF, latency/scalability benchmarks and production readiness are not certified
by this increment. Local readiness was run with `--skip-git-check`; its result is
limited to the four checks it actually performs.

## Subsequent increments (not implemented here)

1. Establish a full-suite baseline with dependency versions locked and crypto mocks
   separated from real security tests; audit packaging/import side effects.
2. Map callers across `src/core/mape_k`, `src/self_healing/mape_k` and integration
   variants; choose a canonical synchronous contract before consolidating copies.
3. Separate command execution, postcondition verification and learning records;
   require verified evidence before feedback changes policy.
4. Replace free-text recovery selection with typed commands and explicit backend
   interfaces. Audit rollback: current string-based inverse commands do not prove
   restoration of the original state. Add idempotency keys and an event outbox.
5. Audit script execution's local fallback, timeout ambiguity, breaker/rate-limiter
   concurrency and wall-clock cooldowns. Do not increase automatic retries until
   idempotency and reconciliation are defined.
6. Review PQC/identity, network adapters and eBPF independently with their own
   integration environments; then consolidate API/configuration and deployment.
7. Run fault injection, deterministic replay and before/after benchmarks under a
   frozen protocol before claiming performance or reliability improvements.

## Design references

These are established practices checked against current primary documentation,
not claims that a new paper automatically justifies an architecture rewrite:

- Python monotonic clocks: https://docs.python.org/3/library/time.html#time.monotonic
- Result classification for circuit breakers:
  https://github.com/resilience4j/resilience4j/blob/master/resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/CircuitBreakerConfig.java

No claim of speedup or adoption of the “latest innovation” is made without a
controlled comparison on this project's workloads.
