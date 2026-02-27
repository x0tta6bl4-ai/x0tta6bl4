// SPDX-License-Identifier: GPL-2.0
/*
 * Supply Chain Validator — XDP eBPF Program
 * =========================================
 * Blocks packets from nodes that have not passed SBOM attestation.
 * 
 * Map layout:
 *   attested_nodes_map : HASH  src_ip(u32) -> is_attested(u8)
 *
 * Logic:
 *   1. Parse IPv4 source address.
 *   2. Lookup in attested_nodes_map.
 *   3. If value == 1, XDP_PASS.
 *   4. Else, XDP_DROP.
 */

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define MAX_NODES 10000

/* Map storing attested node IPs */
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_NODES);
    __type(key,   __u32);  /* src IPv4 address */
    __type(value, __u8);   /* 1 = attested, 0 = not attested */
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} attested_nodes_map SEC(".maps");

SEC("xdp")
int xdp_supply_chain_validator(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    __u32 src_ip = ip->saddr;

    /* Check if node is attested */
    __u8 *is_attested = bpf_map_lookup_elem(&attested_nodes_map, &src_ip);
    
    if (is_attested && *is_attested == 1) {
        return XDP_PASS;
    }

    /* Block non-attested traffic */
    return XDP_DROP;
}

char _license[] SEC("license") = "GPL";
