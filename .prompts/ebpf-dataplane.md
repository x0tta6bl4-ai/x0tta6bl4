# eBPF/XDP Dataplane — Kernel-Level Packet Processing

## Context

Mesh nodes need to forward packets at line rate. Python is too slow for per-packet processing — the dataplane must run in the Linux kernel via eBPF/XDP. The control plane (routing decisions, peer discovery, crypto session management) stays in Python.

Target NIC: r8169 (Realtek) on Intel i5. This is a consumer-grade NIC without hardware offloading — the dataplane must work entirely in software.

## Architecture Decision

**XDP_TX for forwarding, XDP_DROP for filtering.** AF_XDP ring buffers for zero-copy packet delivery between kernel and userspace Python control plane. The eBPF program is attached to the real network interface and handles:

1. Packet filtering (drop non-mesh traffic early)
2. Forwarding (XDP_TX to output interface)
3. Statistics collection (per-flow byte/packet counters via BPF maps)
4. Load balancing (hash-based flow distribution)

## SPEC

### File: `src/network/ebpf/xdp_program.c`

```
// XDP program compiled to BPF bytecode
// Sections: xdp, xdp_tx, xdp_stats

struct bpf_map_def SEC("maps") packet_stats = {
    .type = BPF_MAP_TYPE_PERCPU_ARRAY,
    .key_size = sizeof(__u32),
    .value_size = sizeof(struct packet_stat),
    .max_entries = 256,
};

SEC("xdp")
int xdp_pass(struct xdp_md *ctx)
    // Default pass-through
    // Returns XDP_PASS for non-mesh traffic
    // Collects stats per ingress interface

SEC("xdp_tx")
int xdp_forward(struct xdp_md *ctx)
    // Forward mesh traffic to output interface
    // Rewrite MAC addresses
    // Returns XDP_TX

SEC("xdp_drop")
int xdp_filter(struct xdp_md *ctx)
    // Drop packets with DPI signatures
    // Returns XDP_DROP or XDP_PASS
```

### Module: `src/network/ebpf/xdp_manager.py`

```
class XDPManager:
    """Userspace control plane for eBPF/XDP programs."""
    
    async def attach(self, interface: str, mode: XDPMode) -> bool
    async def detach(self, interface: str) -> bool
    async def get_stats(self) -> dict[str, InterfaceStats]
    async def update_filter(self, rules: list[FilterRule]) -> bool
    async def get_ring_stats(self) -> RingStats
```

## CONSTRAINTS

1. **Must pass kernel verifier.** Every eBPF program must be accepted by the Linux BPF verifier. No unbounded loops, no pointer arithmetic, max instruction count 4096.
2. **Python control plane only.** The hot path is C/BPF. Python only reads stats and updates config maps.
3. **BCC or bpftrace for development.** Production uses libbpf + BPF skeletons.
4. **No kernel panics.** Bad eBPF programs are rejected by the verifier, but the loading path must handle errors gracefully.

## BENCHMARK TARGETS

| Metric | Target | Hardware |
|--------|--------|----------|
| XDP_TX throughput | 142,000 PPS | r8169 + i5 |
| XDP_DROP raw | 49,000 PPS | r8169 + i5 |
| P50 latency | < 10 μs | Same |
| AF_XDP ring drain | < 1% packet loss | Under 100k PPS |

## EDGE CASES

1. **Interface goes down** — detach gracefully, re-attach on up.
2. **eBPF verifier rejects program** — log verifier output, don't crash Python.
3. **Multiple XDP programs attached** — libbpf priority handling.
4. **Ring buffer overflow** — drop oldest, not newest.
5. **Kernel version < 4.18** — XDP not available, fall back to raw socket.
