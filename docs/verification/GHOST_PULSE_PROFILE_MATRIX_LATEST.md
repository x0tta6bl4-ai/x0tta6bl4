# x0tta6bl4_pulse Profile Matrix

Timestamp: `2026-07-11T10:26:02.948454+00:00`

Decision: `PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED`

## What This Proves

- Repeated local loopback timing runs completed for the selected profiles.
- Each selected profile was compared with an unshaped UDP negative control.
- Each row records a seed replay digest for deterministic sender-side timing fields.
- Static eBPF artifacts and read-only kernel status were recorded.

## What This Does Not Prove

- No DPI bypass claim.
- No VK/Yandex/Teams whitelist claim.
- No production-readiness claim.
- No kernel attach claim.

## Aggregates

| Mode | Runs | Successful | Replayable | Planned mean ms | Pulse mean gap ms | Baseline mean gap ms | Ratio mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| corporate | 2 | 2 | 2 | 23.5956875 | 26.07842188888889 | 0.1621962777777778 | 165.04282403799613 |
| whitelist | 2 | 2 | 2 | 63.1895375 | 68.46181411111111 | 0.8800548333333333 | 248.45450846711663 |

## Kernel Read-Only Status

- Status: `KERNEL_EVIDENCE_VISIBLE_READ_ONLY`
- pulse_stats map present: `False`
- pulse program visible: `False`

Raw JSON: `matrix.json`
Rows: `matrix-runs.jsonl`
