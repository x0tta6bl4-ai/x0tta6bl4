# x0tta6bl4_pulse External Evidence Inventory

Status: `FAIL`

Inventory status: `EXTERNAL_EVIDENCE_INVENTORY_INCOMPLETE`

Proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`

## Claim Boundary

- current_runtime_attached: `False`
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `True`
- whitelist_verified: `False`

## Summary

- verified: `kernel_attach, packet_capture, baseline_timing_comparison, dpi_lab`
- invalid: `whitelist_lab, security_review, production_readiness`
- missing: `none`

## Gap Audit

- status: `FAIL`
- replacement_required: `dpi_lab, whitelist_lab, security_review, production_readiness`
- expected_replacement_required: `whitelist_lab, security_review, production_readiness`

## Rows

| Claim | JSON | Markdown | Proof Status | Validation Status | SHA256 |
| --- | --- | --- | --- | --- | --- |
| kernel_attach | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json` | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md` | `VERIFIED` | `VERIFIED` | `3d6ff548e890d4197d7a9bff670f8eacaea4fcfd8e46c58e5938388a65860529` |
| packet_capture | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json` | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.md` | `VERIFIED` | `VERIFIED` | `7ed3bbd885084a012ff7f33b2685558fb3d84ebd6fe1a4b9db2d767dd548aac6` |
| baseline_timing_comparison | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json` | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.md` | `VERIFIED` | `VERIFIED` | `b04869ba8237910191ec24d359338571469f0d262154a795cfcef58738717f4e` |
| dpi_lab | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.md` | `VERIFIED` | `VERIFIED` | `6e0b609abc51bcbf5542ef4f1e6184e258b77318d5caaaeee39f9e0c624051a4` |
| whitelist_lab | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.md` | `INVALID` | `INVALID` | `b808569ccba94bb196d27c0bed666ed822d1b90b01a0318d22768afdb19b736c` |
| security_review | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json` | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.md` | `INVALID` | `INVALID` | `fb286e1d29a295201b4a93e320da6f908f4648c183b68013f2af3f2a40ba46c5` |
| production_readiness | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json` | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.md` | `INVALID` | `INVALID` | `21e4082117593e477d7d7a6721dba6a499bccb77b635db50299ba530e73419f9` |

## Failures

- proof verifier: proof stable fields do not match current suite/external evidence state
- proof verifier: replacement_candidates verifier status must be PASS
- proof verifier: replacement_candidates saved preflight verifier is not PASS
- gap audit verifier: audit stable fields do not match current external evidence state
- gap audit replacement_required does not match external inventory gaps
