// src/network/ebpf/experimental/xdp_redirect_prototype.c
// Experimental Prototype: XDP_REDIRECT for High-PPS Mesh Routing
//
// This program aims to bypass the Linux kernel networking stack entirely
// for mesh transit traffic by using bpf_redirect_map to forward packets
// out of another physical interface immediately after ingress processing.
// This is the theoretical basis for achieving 1,000,000+ PPS.

#include "../programs/vmlinux/vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#ifndef IPPROTO_UDP
#define IPPROTO_UDP 17
#endif

#ifndef ETH_P_IP
#define ETH_P_IP 0x0800
#endif

// DEVMAP for XDP_REDIRECT
// Maps an interface index (value) to a port index (key)
struct {
    __uint(type, BPF_MAP_TYPE_DEVMAP);
    __uint(key_size, sizeof(__u32));
    __uint(value_size, sizeof(__u32));
    __uint(max_entries, 64);
} tx_ports SEC(".maps");

// Map for mesh node destinations (IP -> egress port index in tx_ports)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, __u32);
} mesh_forwarding_routes SEC(".maps");

// Packet counters for metrics
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 4);
    __type(key, __u32);
    __type(value, __u64);
} perf_stats SEC(".maps");

#define STATS_TOTAL 0
#define STATS_REDIRECTED 1
#define STATS_PASSED 2
#define STATS_DROPPED 3

// Map for next-hop MAC addresses (IP -> MAC)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);
    __type(value, unsigned char[6]);
} neigh_mac_table SEC(".maps");

// Map for egress interface source MACs (Ifindex -> MAC)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 64);
    __type(key, __u32);
    __type(value, unsigned char[6]);
} src_mac_table SEC(".maps");

#define MESH_PORT 26969

static __always_inline void update_stat(__u32 idx) {
    __u64 *val = bpf_map_lookup_elem(&perf_stats, &idx);
    if (val) (*val)++;
}

SEC("xdp")
int xdp_redirect_router(struct xdp_md *ctx) {
    update_stat(STATS_TOTAL);

    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) {
        update_stat(STATS_PASSED);
        return XDP_PASS;
    }

    if (eth->h_proto != bpf_htons(ETH_P_IP)) {
        update_stat(STATS_PASSED);
        return XDP_PASS;
    }

    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end) {
        update_stat(STATS_PASSED);
        return XDP_PASS;
    }

    if (ip->protocol != IPPROTO_UDP) {
        update_stat(STATS_PASSED);
        return XDP_PASS;
    }

    struct udphdr *udp = (void *)ip + sizeof(*ip);
    if ((void *)(udp + 1) > data_end) {
        update_stat(STATS_PASSED);
        return XDP_PASS;
    }

    __u16 dport = bpf_ntohs(udp->dest);
    if (dport == MESH_PORT) {
        __u32 dest_ip = ip->daddr;
        __u32 *tx_port = bpf_map_lookup_elem(&mesh_forwarding_routes, &dest_ip);

        if (tx_port) {
            // 1. Rewrite Destination MAC (Next hop)
            unsigned char *dst_mac = bpf_map_lookup_elem(&neigh_mac_table, &dest_ip);
            if (dst_mac) {
                __builtin_memcpy(eth->h_dest, dst_mac, 6);
            }

            // 2. Rewrite Source MAC (Egress interface MAC)
            unsigned char *src_mac = bpf_map_lookup_elem(&src_mac_table, tx_port);
            if (src_mac) {
                __builtin_memcpy(eth->h_source, src_mac, 6);
            }
            
            update_stat(STATS_REDIRECTED);
            // Bypass kernel stack and send directly out of the matched interface
            return bpf_redirect_map(&tx_ports, *tx_port, 0);
        }
    }

    // Local traffic or unknown destination falls back to the kernel stack
    update_stat(STATS_PASSED);
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
