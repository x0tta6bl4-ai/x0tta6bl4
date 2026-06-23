// SPDX-License-Identifier: GPL-2.0
/*
 * Digital Stigmergy Packet Counter — XDP eBPF Program
 * =====================================================
 * Counts packets per source IPv4 address into a BPF LRU hash map.
 * The userspace bridge (stigmergy_bridge.py) reads the map periodically
 * and uses the delta to reinforce pheromone scores in StigmergyRouter.
 *
 * Map layout:
 *   stigmergy_pkt_count  : LRU_HASH  src_ip(u32) -> count(u64)
 *   stigmergy_byte_count : LRU_HASH  src_ip(u32) -> bytes(u64)
 *
 * Build:
 *   clang -O2 -target bpf -c stigmergy_counter.bpf.c -o stigmergy_counter.bpf.o
 *
 * Load (generic XDP mode, no driver support required):
 *   ip link set dev eth0 xdp obj stigmergy_counter.bpf.o sec xdp
 */

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

/* Maximum distinct peers tracked (LRU evicts oldest when full) */
#define MAX_PEERS 4096

/* Per-peer packet counter map */
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, MAX_PEERS);
    __type(key,   __u32);  /* src IPv4 address (network byte order) */
    __type(value, __u64);  /* packet count */
    __uint(pinning, LIBBPF_PIN_BY_NAME);  /* pin at /sys/fs/bpf/stigmergy_pkt_count */
} stigmergy_pkt_count SEC(".maps");

/* Per-peer byte counter map */
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, MAX_PEERS);
    __type(key,   __u32);  /* src IPv4 address */
    __type(value, __u64);  /* byte count */
    __uint(pinning, LIBBPF_PIN_BY_NAME);
} stigmergy_byte_count SEC(".maps");

/*
 * XDP entry point: count packets per source IP, pass all packets.
 * We intentionally never drop traffic here — this is observe-only.
 */
SEC("xdp")
int stigmergy_count_pkts(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;

    /* Validate Ethernet header */
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    /* Only process IPv4 */
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    /* Validate IP header */
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    __u32 src_ip = ip->saddr;
    __u32 pkt_len = bpf_ntohs(ip->tot_len);

    /* Update packet counter */
    __u64 *pkt_cnt = bpf_map_lookup_elem(&stigmergy_pkt_count, &src_ip);
    if (pkt_cnt) {
        __sync_fetch_and_add(pkt_cnt, 1);
    } else {
        __u64 init = 1;
        bpf_map_update_elem(&stigmergy_pkt_count, &src_ip, &init, BPF_ANY);
    }

    /* Update byte counter */
    __u64 *byte_cnt = bpf_map_lookup_elem(&stigmergy_byte_count, &src_ip);
    if (byte_cnt) {
        __sync_fetch_and_add(byte_cnt, (__u64)pkt_len);
    } else {
        __u64 init = pkt_len;
        bpf_map_update_elem(&stigmergy_byte_count, &src_ip, &init, BPF_ANY);
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
