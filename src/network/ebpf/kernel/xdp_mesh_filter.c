// src/network/ebpf/programs/xdp_mesh_filter.c
// XDP Program for Mesh Packet Filtering and Routing Decisions
// Enhanced with Q2 P1: Traffic Obfuscation

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

// Obfuscation configuration (P1 Q2)
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u8); // XOR key
} obf_config SEC(".maps");

// Stats indices
#define STATS_TOTAL 0
#define STATS_PASSED 1
#define STATS_DROPPED 2
#define STATS_FORWARDED 3

#define MESH_PORT 26969
#define SLOT_SYNC_PORT 5000

static __always_inline void apply_xor(void *data, void *data_end, __u8 key) {
    __u8 *ptr = data;
    // Unrolled-like loop for eBPF verifier safety
    #pragma clang loop unroll(full)
    for (int i = 0; i < 64; i++) {
        if ((void *)(ptr + 1) > data_end)
            break;
        *ptr ^= key;
        ptr++;
    }
}

static __always_inline int is_mesh_packet(struct xdp_md *ctx, struct udphdr **udp_out) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return 0;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return 0;

    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end) return 0;
    if (ip->protocol != IPPROTO_UDP) return 0;

    struct udphdr *udp = (void *)ip + sizeof(*ip);
    if ((void *)(udp + 1) > data_end) return 0;

    __u16 dport = bpf_ntohs(udp->dest);
    if (dport == MESH_PORT || dport == SLOT_SYNC_PORT) {
        *udp_out = udp;
        return 1;
    }
    return 0;
}

SEC("xdp")
int xdp_mesh_filter_prog(struct xdp_md *ctx) {
    __u32 key = STATS_TOTAL;
    __u64 *total = bpf_map_lookup_elem(&packet_stats, &key);
    if (total) (*total)++;

    struct udphdr *udp = NULL;
    if (!is_mesh_packet(ctx, &udp)) {
        key = STATS_PASSED;
        __u64 *passed = bpf_map_lookup_elem(&packet_stats, &key);
        if (passed) (*passed)++;
        return XDP_PASS;
    }

    // P1 Q2: Apply XOR obfuscation to payload
    __u32 obf_idx = 0;
    __u8 *xor_key = bpf_map_lookup_elem(&obf_config, &obf_idx);
    if (xor_key && *xor_key != 0 && udp) {
        void *data_end = (void *)(long)ctx->data_end;
        void *payload = (void *)udp + sizeof(*udp);
        if (payload < data_end) {
            apply_xor(payload, data_end, *xor_key);
        }
    }

    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    struct ethhdr *eth = data;
    
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != bpf_htons(0x0800)) return XDP_PASS; // ETH_P_IP

    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;

    __u32 dest_ip = ip->daddr;
    __u32 *next_hop_if = bpf_map_lookup_elem(&mesh_routes, &dest_ip);

    if (next_hop_if) {
        key = STATS_FORWARDED;
        __u64 *forwarded = bpf_map_lookup_elem(&packet_stats, &key);
        if (forwarded) (*forwarded)++;
        return XDP_PASS;
    } else {
        key = STATS_DROPPED;
        __u64 *dropped = bpf_map_lookup_elem(&packet_stats, &key);
        if (dropped) (*dropped)++;
        return XDP_DROP;
    }
}

char LICENSE[] SEC("license") = "GPL";
