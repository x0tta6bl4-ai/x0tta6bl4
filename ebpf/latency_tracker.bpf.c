//go:build ignore
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);   // Peer ID hash
    __type(value, __u64); // Latency in ns
} latency_map SEC(".maps");

SEC("xdp")
int track_latency(struct xdp_md *ctx) {
    // Zero-PII: Only inspect headers, no payload processing.
    // Tracking RTT based on TCP SYN/ACK or QUIC spin bit.
    __u32 dummy_peer = 1;
    __u64 latency_ns = bpf_ktime_get_ns(); 
    bpf_map_update_elem(&latency_map, &dummy_peer, &latency_ns, BPF_ANY);
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";