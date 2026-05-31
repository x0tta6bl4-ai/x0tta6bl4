# x0tta6bl4_pulse Local Evidence Bundle

Timestamp: `2026-05-31T00:05:34.973327+00:00`

Decision: `LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED`

## What This Proves

- Local `PulseUDPTransport` can send and receive UDP packets over loopback.
- Seed replay metadata was recorded for deterministic sender-side timing fields.
- Static eBPF source/object artifacts exist if marked present below.
- Read-only kernel inspection was attempted and recorded.
- A local unshaped UDP negative control was captured for timing comparison.

## What This Does Not Prove

- No DPI bypass claim.
- No VK/Yandex/Teams whitelist claim.
- No production-readiness claim.
- No kernel attach claim. Read-only visible data still requires operator
  validation for the exact interface before any attach claim.

## Local Probe

- Status: `VERIFIED_LOCAL`
- Mode: `corporate`
- Requested packets: `8`
- Send successes: `8`
- Received packets: `8`
- Transport evidence status: `EXPERIMENTAL_LOCAL_TIMING_PROFILE`
- Stealth mode: `NOT_VERIFIED`
- Pulse RNG seed: `20260521`
- Timing replay status: `LOCAL_SEED_REPLAYABLE`
- Timing replay sha256: `89d9e727dc6b396ed8b262475a6b4710b4385943c2eeb5ce4b8f5c451721d175`
- Sender planned mean delay ms: `20.052191`
- Sender actual mean gap ms: `21.746567`
- Mean inter-packet gap ms: `21.739938857142857`
- PCAP capture: `NOT_REQUESTED`

## Baseline Comparison

- Baseline status: `VERIFIED_LOCAL`
- Baseline requested packets: `8`
- Baseline received packets: `8`
- Baseline mean inter-packet gap ms: `0.12452685714285715`
- Comparison status: `VERIFIED_LOCAL_COMPARISON`
- Mean gap delta ms: `21.615412`
- Mean gap ratio: `174.58032231715933`


## Static eBPF

- Source status: `True`
- Object status: `True`
- Object ELF magic: `7f454c46`
- Object is ELF: `True`

## Kernel Read-Only Status

- Status: `KERNEL_ATTACH_NOT_VERIFIED`
- pulse_stats map present: `False`
- pulse program visible: `False`
- XDP links visible: `0`

## Gates

- Python compile: `PASS`
- Shell syntax: `PASS`

Raw JSON: `evidence.json`
Packet events: `packet-events.jsonl`, `packet-events.csv`
