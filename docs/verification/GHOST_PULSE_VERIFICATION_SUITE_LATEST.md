# x0tta6bl4_pulse Verification Suite

Timestamp: `2026-06-15T06:16:48.172871+00:00`

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
- Local replay sha256: `89d9e727dc6b396ed8b262475a6b4710b4385943c2eeb5ce4b8f5c451721d175`
- Matrix runs: `4`
- Matrix replayable runs: `4`
- Local evidence sha256: `27012e7f09e24581aee066243cb4dd13ecbe9bf9fe5742f6e25d4926412c30b9`
- Matrix sha256: `34f05acbf1555cb638347fe7c140e51fd07e0e31e415daf29cc030b7f36ad053`

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
