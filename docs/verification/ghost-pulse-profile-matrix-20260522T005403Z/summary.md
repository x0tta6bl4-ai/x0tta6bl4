# x0tta6bl4_pulse Profile Matrix

Timestamp: `2026-05-22T00:54:13.741112+00:00`

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
| corporate | 2 | 2 | 2 | 39.998892694869824 | 40.529315499999996 | 0.2929085 | 158.2894681562993 |
| whitelist | 2 | 2 | 2 | 783.3044611244208 | 644.7120938 | 0.1717038 | 3729.861347845559 |

## Kernel Read-Only Status

- Status: `KERNEL_ATTACH_NOT_VERIFIED`
- pulse_stats map present: `False`
- pulse program visible: `False`

Raw JSON: `matrix.json`
Rows: `matrix-runs.jsonl`
