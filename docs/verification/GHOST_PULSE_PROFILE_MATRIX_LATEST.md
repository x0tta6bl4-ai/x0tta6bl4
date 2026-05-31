# x0tta6bl4_pulse Profile Matrix

Timestamp: `2026-05-31T00:05:39.259442+00:00`

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
| corporate | 2 | 2 | 2 | 21.92387 | 24.9997514 | 0.1438761 | 176.27767383514487 |
| whitelist | 2 | 2 | 2 | 57.163855 | 63.0343963 | 0.1288291 | 489.2461460398216 |

## Kernel Read-Only Status

- Status: `KERNEL_ATTACH_NOT_VERIFIED`
- pulse_stats map present: `False`
- pulse program visible: `False`

Raw JSON: `matrix.json`
Rows: `matrix-runs.jsonl`
