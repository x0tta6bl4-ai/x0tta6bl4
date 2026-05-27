# x0tta6bl4_pulse Local Evidence Bundle

Timestamp: `2026-05-22T00:53:53.918970+00:00`

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
- Requested packets: `12`
- Send successes: `12`
- Received packets: `12`
- Transport evidence status: `EXPERIMENTAL_LOCAL_TIMING_PROFILE`
- Stealth mode: `NOT_VERIFIED`
- Pulse RNG seed: `20260521`
- Timing replay status: `LOCAL_SEED_REPLAYABLE`
- Timing replay sha256: `63161b0c98bc3482b730371866c327eb2d5c57bd00eab453a823e97d5d0f77ff`
- Sender planned mean delay ms: `40.41809202774685`
- Sender actual mean gap ms: `40.924158963290125`
- Mean inter-packet gap ms: `40.93050981818182`
- PCAP capture: `NOT_REQUESTED`

## Baseline Comparison

- Baseline status: `VERIFIED_LOCAL`
- Baseline requested packets: `12`
- Baseline received packets: `12`
- Baseline mean inter-packet gap ms: `0.18573545454545454`
- Comparison status: `VERIFIED_LOCAL_COMPARISON`
- Mean gap delta ms: `40.74477436363637`
- Mean gap ratio: `220.3699337767793`


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
