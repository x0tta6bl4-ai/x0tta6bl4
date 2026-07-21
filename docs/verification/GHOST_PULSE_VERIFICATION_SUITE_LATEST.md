# x0tta6bl4_pulse Verification Suite

Timestamp: `2026-07-03T21:03:48.050265+00:00`

Decision: `GHOST_PULSE_VERIFICATION_SUITE_INCOMPLETE`

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
- Local replay sha256: `63161b0c98bc3482b730371866c327eb2d5c57bd00eab453a823e97d5d0f77ff`
- Matrix runs: `4`
- Matrix replayable runs: `4`
- Local evidence sha256: `7dd9ba7e8ecfeae4ad1d4e49aec9a6ff3c2dbe12dff8d1adbffacc7ca19ddf72`
- Matrix sha256: `9edf1d51a01c1141470e1c38e95bcdaf9978c24b3dba2699b0cb311f20d2466c`

## Gates

| Gate | Status |
| --- | --- |
| local_evidence_verifier | `FAIL` |
| profile_matrix_verifier | `PASS` |
| seed_replay_verifier | `FAIL` |
| python_compile | `PASS` |
| ghost_core_shell_syntax | `FAIL` |
| false_claim_scan | `PASS` |
| artifact_integrity | `PASS` |
| incoming_gap_candidates_verifier | `PASS` |

## Failures

- local_evidence_verifier did not pass
- seed_replay_verifier did not pass
- ghost_core_shell_syntax did not pass
