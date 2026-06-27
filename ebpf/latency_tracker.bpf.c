//go:build ignore
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#ifndef IPPROTO_TCP
#define IPPROTO_TCP 6
#endif

#ifndef ETH_P_IP
#define ETH_P_IP 0x0800
#endif

struct latency_value {
    __u64 last_timestamp_ns;  // bpf_ktime_get_ns() of most recent packet
    __u64 pkt_count;          // total packets seen from this peer
};

struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);                  // Source IP (peer identifier)
    __type(value, struct latency_value); // Timestamp + counter
} latency_map SEC(".maps");

SEC("xdp")
int track_latency(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // Parse Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    // Parse IP header
    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // Only track TCP packets for meaningful latency estimation.
    // UDP would require QUIC spin-bit parsing which is protocol-specific.
    if (ip->protocol != IPPROTO_TCP)
        return XDP_PASS;

    // Zero-PII: only use source IP as a peer identifier hash.
    // No payload inspection, no port extraction beyond protocol check.
    __u32 src_ip = ip->saddr;
    if (src_ip == 0)
        return XDP_PASS;

    __u64 now = bpf_ktime_get_ns();

    struct latency_value *existing = bpf_map_lookup_elem(&latency_map, &src_ip);
    if (existing) {
        // Update timestamp and increment counter.
        // Userspace reads consecutive timestamps per peer to compute
        // inter-packet delta as a proxy for network latency/jitter.
        existing->last_timestamp_ns = now;
        existing->pkt_count += 1;
    } else {
        struct latency_value new_val = {
            .last_timestamp_ns = now,
            .pkt_count = 1,
        };
        bpf_map_update_elem(&latency_map, &src_ip, &new_val, BPF_ANY);
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
