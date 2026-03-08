# Performance Optimization Plan: Path to 1M+ PPS

**Status:** RC1.1 Research Phase  
**Current Baseline:** 142k TX / 49 RX PPS (Physical NIC `enp8s0`)  
**Target:** 1,000,000+ PPS (Horizon-2)

## 1. Analysis of Current Bottlenecks

### 1.1 Kernel Stack Overhead
The current XDP program returns `XDP_PASS` for all valid mesh packets. This hands the packet over to the standard Linux networking stack (routing, iptables, socket buffers). The overhead of the kernel stack is the primary reason why we are limited to ~142k PPS.

### 1.2 Obfuscation Logic
The XOR obfuscation loop (64 bytes) is unrolled but still adds instruction cycles per packet. While acceptable for 142k, it will become a factor at 1M+ scale.

## 2. Optimization Strategy (Horizon-2)

### 2.1 Bypassing the Kernel Stack (`XDP_TX` / `XDP_REDIRECT`)
To reach 1M+ PPS, transit traffic must never enter the kernel stack.
- **Action:** Implement `XDP_REDIRECT` logic in `xdp_mesh_filter_prog`.
- **Requirement:** NIC drivers must support XDP redirect (Intel `i40e`, `ixgbe`, or `e1000e` in generic mode).

### 2.2 AF_XDP Zero-Copy
For packets that need user-space processing (e.g., PQC signing in the Go agent), we should use `AF_XDP` sockets with zero-copy mode.
- **Action:** Integrate `github.com/asavie/xdp` or `cilium/ebpf/afxdp` into the 5G/Edge worker.

### 2.3 Hardware Optimization
- **Multi-Queue Support:** Ensure the NIC uses multiple RX/TX queues mapped to different CPU cores.
- **Interrupt Coalescing:** Tune `ethtool -C` to reduce interrupt load.
- **Generic XDP vs. Native XDP:** Move from generic XDP (driver-independent) to native XDP (driver-supported) or Offloaded XDP (on-NIC hardware).

## 3. Implementation Roadmap

### Phase 1: Infrastructure (RC1.1)
- [ ] Add `ethtool` and `irqbalance` monitoring to the exporter.
- [ ] Document NIC queue configuration for `enp8s0`.

### Phase 2: Dataplane Refactoring (Horizon-2)
- [ ] Implement `XDP_REDIRECT` for mesh routing.
- [ ] Benchmark `XDP_DROP` performance to find the hardware theoretical limit.
- [ ] Implement AF_XDP socket bridge for Go workers.

## 4. Hardware Constraints (Found on 2026-03-08)
- **Current NIC:** Realtek `r8169` (Intel hardware required for native XDP).
- **Mode:** Generic XDP (SKB mode) is used. Realtek drivers lack native XDP support in many kernel versions.
- **Queueing:** Single-queue limitation confirmed (`ethtool -l` unsupported).
- **Conclusion:** The 142k PPS baseline is likely the ceiling for the current Realtek hardware. Horizon-2 optimization requires Intel-based server NICs.
