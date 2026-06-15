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

- verified: `kernel_attach, packet_capture, baseline_timing_comparison`
- invalid: `dpi_lab, whitelist_lab, security_review, production_readiness`
- missing: `none`

## Gap Audit

- status: `PASS`
- replacement_required: `dpi_lab, whitelist_lab, security_review, production_readiness`
- expected_replacement_required: `dpi_lab, whitelist_lab, security_review, production_readiness`

## Rows

| Claim | JSON | Markdown | Proof Status | Validation Status | SHA256 |
| --- | --- | --- | --- | --- | --- |
| kernel_attach | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json` | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md` | `VERIFIED` | `VERIFIED` | `3d6ff548e890d4197d7a9bff670f8eacaea4fcfd8e46c58e5938388a65860529` |
| packet_capture | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json` | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.md` | `VERIFIED` | `VERIFIED` | `7ed3bbd885084a012ff7f33b2685558fb3d84ebd6fe1a4b9db2d767dd548aac6` |
| baseline_timing_comparison | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json` | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.md` | `VERIFIED` | `VERIFIED` | `b04869ba8237910191ec24d359338571469f0d262154a795cfcef58738717f4e` |
| dpi_lab | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.md` | `INVALID` | `INVALID` | `d96656ef33dc1fbb3232932486d7808535da2e63f0370fcfcc34f29ed435bba6` |
| whitelist_lab | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json` | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.md` | `INVALID` | `INVALID` | `7ee32071a4ba4e8b0cc381937f5b56b448bcbec0733537f370bd4a17e97c7214` |
| security_review | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json` | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.md` | `INVALID` | `INVALID` | `6a1de9822478d20aa0f98d1be57b28eea5c462870ffe4ee9d3b27571c0df8fa4` |
| production_readiness | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json` | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.md` | `INVALID` | `INVALID` | `8d93de765bc1a05f6f8d39c8c35755d92213c69ce84e62c139435f833627f1da` |

## Failures

- None
