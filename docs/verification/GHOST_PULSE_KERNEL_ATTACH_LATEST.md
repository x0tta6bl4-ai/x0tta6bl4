# x0tta6bl4_pulse Kernel Attach Evidence

Observed at: `2026-06-07T04:32:36.434907+00:00`

Status: `INCOMPLETE`

## Measurements

- Interface: `docker0`
- Interface seen by ip link: `True`
- Interfaces seen by full scan: `11`
- Interfaces with XDP in full scan: `[]`
- XDP attached: `False`
- Pulse marker visible in bpftool output: `False`
- Interface visible in bpftool net: `False`
- Map packet counter delta: `0`

## eBPF Artifact Preflight

- Status: `ACTION_REQUIRED`
- Source: `src/network/ebpf/x0tta6bl4_pulse.bpf.c`
- Object: `src/network/ebpf/x0tta6bl4_pulse.o`
- Object is eBPF: `True`
- Object has XDP section: `True`
- Object has BTF section: `False`
- Object contains pulse_stats: `True`
- Object contains pulse function: `True`
- Preflight blockers: `pulse_object_missing_btf_section`

## Collection Options

- bpftool sudo: `False`
- bpftool privilege mode: `direct`
- sudo non-interactive unavailable: `False`

## Collection Diagnostics

- Status: `ACTION_REQUIRED`
- Blockers: `xdp_attach_not_visible, bpftool_permission_denied, pulse_program_not_visible, bpftool_net_missing_interface, pulse_stats_counter_not_positive`
- bpftool permission denied: `True`

## Candidate Import Readiness

- Status: `ACTION_REQUIRED`
- Candidate path: `docs/verification/incoming/kernel_attach.json`
- Can stage candidate: `False`
- Blocking reasons: `kernel_evidence_not_verified, xdp_attach_not_visible, bpftool_permission_denied, pulse_program_not_visible, bpftool_net_missing_interface, pulse_stats_counter_not_positive`

## Failures

- ip link did not show an XDP attach on interface: docker0
- bpftool output did not contain an x0tta6bl4_pulse marker
- bpftool net output did not include interface: docker0
- pulse map packet counter did not increase
- command failed: bpftool prog show
- command failed: bpftool net
- command failed: bpftool map show name pulse_stats
- command failed: bpftool map dump name pulse_stats
- command failed: bpftool map dump name pulse_stats
