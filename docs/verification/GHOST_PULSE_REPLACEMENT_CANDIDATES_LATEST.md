# x0tta6bl4_pulse Replacement Candidate Preflight

Status: `PASS`

Decision: `REPLACEMENT_CANDIDATES_NOT_READY`

Audit: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json`

Audit sha256: `ab612ccf4d2d514f2d06d6ebe5275757fdf3ab895105fcfa6bfbbe911fd24a5b`

## Claim Boundary

- kernel_attach_verified: `False`
- note: `Replacement candidate preflight only; it never promotes proof-gate claims.`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Summary

- replacement_required: `dpi_lab, whitelist_lab, security_review, production_readiness`
- ready: `none`
- not_ready: `dpi_lab, whitelist_lab, security_review, production_readiness`
- missing_candidates: `none`
- non_file_candidates: `none`
- unsafe_candidates: `none`

## Candidate Intake Plan

- status: `ACTION_REQUIRED`
- ready_claims: `none`
- not_ready_claims: `dpi_lab, whitelist_lab, security_review, production_readiness`
- missing_candidate_paths: `none`
- currently_ready_write_commands: `0`
- post_import_refresh_commands: `9`

## Rows

| Claim | Candidate | Exists | Is File | Symlink | Import Decision | Ready |
| --- | --- | --- | --- | --- | --- | --- |
| dpi_lab | `docs/verification/incoming/dpi_lab.json` | `True` | `True` | `False` | `REJECTED` | `False` |
| whitelist_lab | `docs/verification/incoming/whitelist_lab.json` | `True` | `True` | `False` | `REJECTED` | `False` |
| security_review | `docs/verification/incoming/security_review.json` | `True` | `True` | `False` | `REJECTED` | `False` |
| production_readiness | `docs/verification/incoming/production_readiness.json` | `True` | `True` | `False` | `REJECTED` | `False` |

## Failures

- None
