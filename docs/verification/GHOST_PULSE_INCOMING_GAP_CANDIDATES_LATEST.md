# x0tta6bl4_pulse Incoming Gap Candidates

Timestamp: `2026-06-15T05:51:04.394695+00:00`

Status: `PASS`

Decision: `INCOMING_GAP_CANDIDATES_FAIL_CLOSED`

## Summary

- expected_gap_claims: `dpi_lab, whitelist_lab, security_review, production_readiness`
- unexpected_gap_claims: `none`
- rows: `4`

## Rows

| Claim | Candidate | Payload Status | Mode | Import Decision | Row Status |
| --- | --- | --- | --- | --- | --- |
| dpi_lab | `docs/verification/incoming/dpi_lab.json` | `INCOMPLETE` | `EXTERNAL_EVIDENCE_GAP_RECORD` | `REJECTED` | `PASS` |
| whitelist_lab | `docs/verification/incoming/whitelist_lab.json` | `INCOMPLETE` | `EXTERNAL_EVIDENCE_GAP_RECORD` | `REJECTED` | `PASS` |
| security_review | `docs/verification/incoming/security_review.json` | `INCOMPLETE` | `EXTERNAL_EVIDENCE_GAP_RECORD` | `REJECTED` | `PASS` |
| production_readiness | `docs/verification/incoming/production_readiness.json` | `INCOMPLETE` | `EXTERNAL_EVIDENCE_GAP_RECORD` | `REJECTED` | `PASS` |

## Claim Boundary

- kernel_attach_verified: `False`
- note: `Incoming gap candidate verification only; rejected candidates do not prove external claims.`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Failures

- None
