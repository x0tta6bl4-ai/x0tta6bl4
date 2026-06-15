# XDP Live Attach Artifact — 2026-06-15

Observed at: `2026-06-15T13:38:55+0300`

## Attach Details

- **Interface:** enp8s0
- **MAC:** 18:c0:4d:ab:68:60
- **PCI:** 0000:08:00.0
- **Kernel:** 6.14.0-37-generic
- **BTF:** present at /sys/kernel/btf/vmlinux
- **XDP mode:** xdpgeneric
- **Program:** xdp_mesh_filter_prog (id 634)
- **Tag:** 57f3b9dd4de50bb5
- **BPF object:** meshcore_x86_bpfel.o (from 2026-05-29)
- **Loader binary:** ebpf/prod/loader (from 2026-05-20)
- **Pinned at:** /sys/fs/bpf/x0tta6bl4-prod/meshcore/xdp_mesh_filter_prog

## Verification Output

```
status: interface=enp8s0
2: enp8s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 xdpgeneric qdisc fq state UP mode DEFAULT group default qlen 1000
    link/ether 18:c0:4d:ab:68:60 brd ff:ff:ff:ff:ff:ff
    prog/xdp id 634 name xdp_mesh_filter tag 57f3b9dd4de50bb5 jited load_time ...
production eBPF loader prepared for interface=enp8s0 kernel>=6.1 object=/mnt/projects/ebpf/prod/meshcore_x86_bpfel.o benchmark_target_pps=>5M_not_measured_here
```

## Status

- XDP program loaded and attached to real NIC enp8s0
- Program is jited and running
- Maps pinned at /sys/fs/bpf/x0tta6bl4-prod/meshcore/
- No verifier errors

## What This Proves

- XDP CO-RE object loads successfully on kernel 6.14.0
- BPF program attaches to real hardware NIC (enp8s0, PCI 0000:08:00.0)
- No kernel verifier rejection
- Live XDP attach artifact for release gate

## What This Does NOT Prove

- PPS throughput (not benchmarked)
- Production traffic delivery
- DPI bypass effectiveness
- Customer traffic handling
