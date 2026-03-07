# x0tta6bl4 Formal Validation Bundle v1.0

**Date**: 2026-03-07
**Status**: 🟢 DATAPLANE SIGNAL VERIFIED
**Component**: eBPF / XDP Mesh Filter

## 📊 Benchmark Summary
- **Interface**: `enp8s0` (Physical NIC)
- **Duration**: 5s
- **Measured PPS**: 3996 (RX)
- **Target PPS**: 10 (Baseline verified)
- **Artifact**: `ebpf/prod/results/benchmark-20260307T081157Z.json`

## 🛠 Engineering Insights & Topology
1. **No Hardware Loopback**: Interface `enp8s0` does not support internal RX loopback for `pktgen` (TX-only behavior confirmed).
2. **Hybrid Load Generation**: To achieve real RX signal for XDP verification, a background `ping -f` load was injected towards the local gateway during the benchmark.
3. **Bug Fix**: `benchmark-harness.sh` was updated to handle `pktgen` asynchronously, preventing terminal lock during infinite packet generation (`count 0`).
4. **BPF Stats**: Verified via `kernel.bpf_stats_enabled=1` and `run_cnt` delta.

## ⚠️ Known Blockers & Risks
- **EEXIST Panic Risk**: Manual removal of BPF pins in `/sys/fs/bpf/` can cause kernel instability if structures are held. 
- **Recommendation**: Use targeted removal of specific map/prog pins instead of `rm -rf` on the root BPF directory.
- **Scale**: Current 4k PPS is a functional proof, not a stress test. Million-level PPS requires a proper hardware loopback or a dual-NIC tester.

## 📋 Reproduce Runbook
1. Load XDP: `RUN_BENCH=1 sudo -E ebpf/prod/benchmark-harness.sh --iface enp8s0 --duration 5 --target-pps 10`
2. Monitor: `sudo bpftool prog show name xdp_mesh_filter_prog`
3. Verify: Check `ebpf/prod/results/*.json` for `pass: true`.
