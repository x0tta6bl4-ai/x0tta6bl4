# x0tta6bl4_pulse Kernel Attach Evidence

Observed at: `2026-05-22T20:17:21.575656+00:00`

Status: `VERIFIED`

## Measurements

- Interface: `x0rp021`
- Interface seen by ip link: `True`
- Interfaces seen by full scan: `16`
- Interfaces with XDP in full scan: `['x0rp021']`
- XDP attached: `True`
- Pulse marker visible in bpftool output: `True`
- Interface visible in bpftool net: `True`
- Map packet counter delta: `488`

## eBPF Artifact Preflight

- Status: `READY_FOR_CONTROLLED_ATTACH_TEST`
- Source: `src/network/ebpf/x0tta6bl4_pulse.bpf.c`
- Object: `src/network/ebpf/x0tta6bl4_pulse.o`
- Object is eBPF: `True`
- Object has XDP section: `True`
- Object has BTF section: `True`
- Object contains pulse_stats: `True`
- Object contains pulse function: `True`
- Preflight blockers: ``

## Collection Options

- bpftool sudo: `True`
- bpftool privilege mode: `sudo_noninteractive`
- sudo non-interactive unavailable: `False`

## Collection Diagnostics

- Status: `READY_FOR_PROOF`
- Blockers: `none`
- bpftool permission denied: `False`

## Candidate Import Readiness

- Status: `READY_TO_STAGE_CANDIDATE`
- Candidate path: `docs/verification/incoming/kernel_attach.json`
- Can stage candidate: `True`
- Blocking reasons: `none`

## Failures

- None
