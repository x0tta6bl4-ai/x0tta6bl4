# x0tta6bl4_pulse Replacement Candidate Preflight

Status: `PASS`

Decision: `REPLACEMENT_CANDIDATES_NOT_READY`

Audit: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json`

Audit sha256: `12c870afa2251e82fdef630bf31362a47af8961f903dc0baf042c476138b5688`

## Claim Boundary

- kernel_attach_verified: `False`
- note: `Replacement candidate preflight only; it never promotes proof-gate claims.`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Summary

- replacement_required: `kernel_attach, dpi_lab, whitelist_lab, production_readiness`
- ready: `kernel_attach`
- not_ready: `dpi_lab, whitelist_lab, production_readiness`
- missing_candidates: `none`
- non_file_candidates: `none`
- unsafe_candidates: `none`

## Candidate Intake Plan

- status: `ACTION_REQUIRED`
- ready_claims: `kernel_attach`
- not_ready_claims: `dpi_lab, whitelist_lab, production_readiness`
- missing_candidate_paths: `none`
- currently_ready_write_commands: `1`
- post_import_refresh_commands: `9`

## Rows

| Claim | Candidate | Exists | Is File | Symlink | Import Decision | Ready |
| --- | --- | --- | --- | --- | --- | --- |
| kernel_attach | `docs/verification/incoming/kernel_attach.json` | `True` | `True` | `False` | `READY_TO_IMPORT` | `True` |
| dpi_lab | `docs/verification/incoming/dpi_lab.json` | `True` | `True` | `False` | `REJECTED` | `False` |
| whitelist_lab | `docs/verification/incoming/whitelist_lab.json` | `True` | `True` | `False` | `REJECTED` | `False` |
| production_readiness | `docs/verification/incoming/production_readiness.json` | `True` | `True` | `False` | `REJECTED` | `False` |

## Failures

- None
