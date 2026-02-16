// src/network/ebpf/programs/xdp_mesh_filter.c
// XDP Program for Mesh Packet Filtering and Routing Decisions
// Integrates with batman-adv style mesh routing

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#ifndef IPPROTO_UDP
#define IPPROTO_UDP 17
#endif

#ifndef ETH_P_IP
#define ETH_P_IP 0x0800
#endif

// Map for mesh node destinations (IP -> next hop interface)
// Key: destination IP (u32), Value: next hop interface index (u32)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, __u32);
} mesh_routes SEC(".maps");

// Packet counters for metrics
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 4);
    __type(key, __u32);
    __type(value, __u64);
} packet_stats SEC(".maps");

// Stats indices
#define STATS_TOTAL 0
#define STATS_PASSED 1
#define STATS_DROPPED 2
#define STATS_FORWARDED 3

// Mesh protocol ports (example)
#define MESH_PORT 26969  // batman-adv port
#define SLOT_SYNC_PORT 5000

static __always_inline int is_mesh_packet(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // Parse Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return 0;

    // Only IPv4 for now
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return 0;

    // Parse IP header
    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return 0;

    // Check if UDP
    if (ip->protocol != IPPROTO_UDP)
        return 0;

    // Parse UDP header
    struct udphdr *udp = (void *)ip + sizeof(*ip);
    if ((void *)(udp + 1) > data_end)
        return 0;

    // Check destination port
    __u16 dport = bpf_ntohs(udp->dest);
    if (dport == MESH_PORT || dport == SLOT_SYNC_PORT)
        return 1;

    return 0;
}

SEC("xdp")
int xdp_mesh_filter_prog(struct xdp_md *ctx) {
    __u32 key = STATS_TOTAL;
    __u64 *total = bpf_map_lookup_elem(&packet_stats, &key);
    if (total)
        (*total)++;

    if (!is_mesh_packet(ctx)) {
        // Not mesh packet, pass through
        key = STATS_PASSED;
        __u64 *passed = bpf_map_lookup_elem(&packet_stats, &key);
        if (passed)
            (*passed)++;
        return XDP_PASS;
    }

    // Mesh packet - check routing
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;
    struct ethhdr *eth = data;
    struct iphdr *ip = (void *)eth + sizeof(*eth);

    __u32 dest_ip = ip->daddr;
    __u32 *next_hop_if = bpf_map_lookup_elem(&mesh_routes, &dest_ip);

    if (next_hop_if) {
        // Route exists - forward (in XDP, we can redirect to another interface)
        // For simplicity, pass for now; in full impl, use XDP_REDIRECT
        key = STATS_FORWARDED;
        __u64 *forwarded = bpf_map_lookup_elem(&packet_stats, &key);
        if (forwarded)
            (*forwarded)++;
        return XDP_PASS;  // Or XDP_REDIRECT to *next_hop_if
    } else {
        // No route - drop
        key = STATS_DROPPED;
        __u64 *dropped = bpf_map_lookup_elem(&packet_stats, &key);
        if (dropped)
            (*dropped)++;
        return XDP_DROP;
    }
}

char LICENSE[] SEC("license") = "GPL";