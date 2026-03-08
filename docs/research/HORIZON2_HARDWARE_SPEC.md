# Hardware Specification: Horizon-2 High-Performance Testbed

**Status:** Final Draft (Horizon-2)  
**Author:** Gemini CLI (RC1-GUARD)  
**Target:** 1,000,000+ PPS (Zero-Copy AF_XDP)

## 1. Node Configuration (x2 Nodes)

To verify multi-node mesh throughput without external interference, a dual-node direct-link setup is required.

### 1.1 Compute / CPU
- **CPU:** Intel Xeon or Core (8+ physical cores). 
- **Requirement:** Support for DDIO (Data Direct I/O) to allow the NIC to write directly into L3 cache.
- **BIOS Tuning:** Disable C-States, SpeedStep, and Hyper-Threading for deterministic jitter-free benchmarking.

### 1.2 Network Interface Cards (NICs)
The following NICs are verified for Native XDP and Zero-Copy support:

- **Primary Choice:** Intel X710-DA2 (10GbE SFP+).
  - Driver: `i40e`
  - Features: Excellent multi-queue support, mature Native XDP.
- **Secondary Choice:** Intel X520-DA2 (10GbE SFP+).
  - Driver: `ixgbe`
  - Features: Reliable, widely available, supports Native XDP.
- **High-End Choice:** Mellanox ConnectX-4/5 (25GbE/100GbE).
  - Driver: `mlx5_core`
  - Features: Highest PPS ceiling, but more complex driver configuration.

### 1.3 Cabling
- **Type:** SFP+ Direct Attach Copper (DAC) or SFP+ Fiber with LC-LC patch cord.
- **Note:** Avoid RJ45 (10Gbase-T) for high-PPS benchmarks due to higher latency and power consumption.

## 2. Network Topology

```text
[ Node A (Generator) ] <--- DAC Cable ---> [ Node B (DUT - Device Under Test) ]
  IP: 192.168.100.1                          IP: 192.168.100.2
  Role: Pktgen / DPDK-gen                    Role: x0tta6bl4 Agent (AF_XDP)
```

## 3. OS & Kernel (Verification Target)
- **OS:** Ubuntu 24.04 LTS.
- **Kernel:** 6.8.0+ (Mainline or Generic).
- **Boot Params:** `isolcpus=1-3 nohz_full=1-3 rcu_nocbs=1-3` (Reserve cores for XDP processing).

## 4. Verification Command (Pre-Release Gate)
Before claiming 1M+ PPS, the operator must provide:
```bash
# Check driver support
ethtool -i eth0 | grep -E "i40e|ixgbe|mlx5"
# Check multi-queue
ethtool -l eth0
# Check XDP status
ip link show eth0 | grep xdp
```

---
**Verdict:** The Intel X710 is the recommended standard for x0tta6bl4 Horizon-2 production deployment.
