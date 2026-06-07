# x0tta6bl4_pulse External Evidence Inventory

Status: `PASS`

Inventory status: `EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS`

Proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`

## Claim Boundary

- current_runtime_attached: `False`
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Summary

- verified: `kernel_attach, packet_capture, baseline_timing_comparison, security_review`
- invalid: `dpi_lab, whitelist_lab, production_readiness`
- missing: `none`

## Gap Audit

- status: `PASS`
- replacement_required: `dpi_lab, whitelist_lab, production_readiness`
- expected_replacement_required: `dpi_lab, whitelist_lab, production_readiness`

## Rows

| Claim | JSON | Markdown | Proof Status | Validation Status | SHA256 |
| --- | --- | --- | --- | --- | --- |
| kernel_attach | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json` | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md` | `VERIFIED` | `VERIFIED` | `3d6ff548e890d4197d7a9bff670f8eacaea4fcfd8e46c58e5938388a65860529` |
| packet_capture | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json` | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.md` | `VERIFIED` | `VERIFIED` | `7ed3bbd885084a012ff7f33b2685558fb3d84ebd6fe1a4b9db2d767dd548aac6` |
| baseline_timing_comparison | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json` | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.md` | `VERIFIED` | `VERIFIED` | `b04869ba8237910191ec24d359338571469f0d262154a795cfcef58738717f4e` |
| dpi_lab | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.md` | `INVALID` | `INVALID` | `3ee85d5afde5222ff62308ca5f4c83c190ed2758567f5513ad9c98c63a71555e` |
| whitelist_lab | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.md` | `INVALID` | `INVALID` | `731098b1527639d43882102c8d5a12387dcb8feb6decb0771d7cf5e6d843a051` |
| security_review | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json` | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.md` | `VERIFIED` | `VERIFIED` | `e0ad08455f32d00be59ca1b0e92f5a8ddf80c1f8dfdb48ef1037f2f91f1725bf` |
| production_readiness | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json` | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.md` | `INVALID` | `INVALID` | `fde275c1d1d01803e2460e3927c7da8febf51d93c9a6d29dc9b7223dabf6bd2b` |

## Failures

- None
