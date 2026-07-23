# x0tta6bl4_pulse Verification Suite

Timestamp: `2026-07-11T10:26:08.254049+00:00`

Decision: `GHOST_PULSE_VERIFICATION_SUITE_VERIFIED_STEALTH_NOT_VERIFIED`

## Suite Scope

- Latest local evidence verifier.
- Latest profile matrix verifier.
- Seed replay verifier.
- Static false-claim scan.
- Latest-vs-bundle artifact hash consistency.
- Fail-closed incoming gap candidate verifier.

## What This Does Not Prove

- No DPI bypass claim.
- No VK/Yandex/Teams whitelist claim.
- No production-readiness claim.
- No kernel attach claim.

## Summary

- Local seed: `20260521`
- Local replay: `LOCAL_SEED_REPLAYABLE`
- Local replay sha256: `0652e3251dbf527e622ec36c588bda0034e02baff827b27d279fe2b52743b153`
- Matrix runs: `4`
- Matrix replayable runs: `4`
- Local evidence sha256: `0762bb39d3475da0f0bd43d91d3a20f8accad57a2f9cba1ff60f776bf59bdc87`
- Matrix sha256: `8fcbda2a9326cd6379dc817cda9577a37c7cc0c0bdb9729dee02998f8fe59f27`

## Gates

| Gate | Status |
| --- | --- |
| local_evidence_verifier | `PASS` |
| profile_matrix_verifier | `PASS` |
| seed_replay_verifier | `PASS` |
| python_compile | `PASS` |
| ghost_core_shell_syntax | `PASS` |
| false_claim_scan | `PASS` |
| artifact_integrity | `PASS` |
| incoming_gap_candidates_verifier | `PASS` |

## Failures

- None
