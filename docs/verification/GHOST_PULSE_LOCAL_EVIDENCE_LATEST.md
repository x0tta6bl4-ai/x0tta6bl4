# x0tta6bl4_pulse Local Evidence Bundle

Timestamp: `2026-07-11T10:25:29.144326+00:00`

Decision: `LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED`

## What This Proves

- Local `PulseUDPTransport` can send and receive UDP packets over loopback.
- Seed replay metadata was recorded for deterministic sender-side timing fields.
- Static eBPF source/object artifacts exist if marked present below.
- Read-only kernel inspection was attempted and recorded.

## What This Does Not Prove

- No DPI bypass claim.
- No VK/Yandex/Teams whitelist claim.
- No production-readiness claim.
- No kernel attach claim. Read-only visible data still requires operator
  validation for the exact interface before any attach claim.

## Local Probe

- Status: `VERIFIED_LOCAL`
- Mode: `corporate`
- Requested packets: `24`
- Send successes: `24`
- Received packets: `24`
- Transport evidence status: `EXPERIMENTAL_LOCAL_TIMING_PROFILE`
- Stealth mode: `NOT_VERIFIED`
- Pulse RNG seed: `20260521`
- Timing replay status: `LOCAL_SEED_REPLAYABLE`
- Timing replay sha256: `0652e3251dbf527e622ec36c588bda0034e02baff827b27d279fe2b52743b153`
- Sender planned mean delay ms: `21.605337`
- Sender actual mean gap ms: `23.094965`
- Mean inter-packet gap ms: `23.09558104347826`
- PCAP capture: `NOT_REQUESTED`


## Static eBPF

- Source status: `True`
- Object status: `True`
- Object ELF magic: `7f454c46`
- Object is ELF: `True`

## Kernel Read-Only Status

- Status: `KERNEL_EVIDENCE_VISIBLE_READ_ONLY`
- pulse_stats map present: `False`
- pulse program visible: `False`
- XDP links visible: `1`

## Gates

- Python compile: `PASS`
- Shell syntax: `PASS`

Raw JSON: `evidence.json`
Packet events: `packet-events.jsonl`, `packet-events.csv`
