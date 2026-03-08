# RFC: AF_XDP Integration for Zero-Copy Dataplane

**Status:** Draft (Horizon-2)  
**Author:** Gemini CLI (RC1-GUARD)  
**Date:** 2026-03-08

## 1. Objective
Achieve 1,000,000+ PPS processing in user-space (Go) while maintaining the security benefits of eBPF/XDP. This is critical for PQC-heavy workloads where kernel-space processing is too restrictive or complex.

## 2. Background
Current datapath:
- Ingress -> XDP Program (Kernel) -> `XDP_PASS` -> Kernel Stack -> Go App (Socket).
- Overhead: 142k PPS (observed ceiling on virtio-net).

Proposed datapath:
- Ingress -> XDP Program (Kernel) -> `XDP_REDIRECT` to AF_XDP Socket -> Go App (UMEM).
- Benefit: Bypasses the entire kernel networking stack.

## 3. Technical Design

### 3.1 XDP Side
We need to add an `XDP_REDIRECT` path to our existing `xdp_mesh_filter_prog`.
- Use `BPF_MAP_TYPE_XSKMAP` to store AF_XDP socket file descriptors.
- Redirect packets matching `MESH_PORT` (26969) to the socket map index matching the CPU core.

### 3.2 User-space Side (Go)
We will integrate a high-performance AF_XDP library (e.g., `github.com/asavie/xdp` or `cilium/ebpf/afxdp`).
- **UMEM Management:** Allocate a large contiguous memory region for packet buffers.
- **Fill/Completion Rings:** Manage buffer ownership between kernel and user-space.
- **RX/TX Rings:** Handle actual packet data.

### 3.3 Zero-Copy vs. Copy Mode
- **Native XDP (Zero-Copy):** Directly maps NIC hardware buffers to UMEM. Requires Intel `i40e`, `ixgbe`, or `mlx5` drivers.
- **Generic XDP (Copy-Mode):** Kernel copies packets to UMEM. Works on any NIC (including `virtio_net`), but slower than native.

## 4. Hardware Requirements (Dual-NIC Setup)
To benchmark 1M+ PPS honestly, we need:
- **Primary NIC:** Intel X520/X540/X710 (10GbE+) for Native XDP support.
- **Secondary NIC:** For traffic generation (Pktgen/DPDK).
- **Physical Connection:** Direct SFP+ or DAC cable between nodes (no virtualization overhead).

## 5. Proposed Integration API (Go)

```go
type AFXDPWorker struct {
    Iface    string
    SocketMap *ebpf.Map // XSKMAP
    Umem     *xdp.Umem
}

func (w *AFXDPWorker) Start() {
    // 1. Initialize UMEM
    // 2. Create AF_XDP socket
    // 3. Register socket in XSKMAP
    // 4. Poll RX ring
}
```

## 6. Security Considerations
- **Zero-Trust:** AF_XDP still respects the XDP filter logic. Only packets validated by the eBPF program reach user-space.
- **Isolation:** Each tenant can have its own AF_XDP queue for performance isolation.

---
**Verdict:** AF_XDP is the only viable path to 1M+ PPS for x0tta6bl4's user-space-heavy architecture (PQC/GNN).
