/*
 * PQC Key Store eBPF Program — CO-RE compatible
 * XDP program for kernel-space PQC session key lookup.
 *
 * Maps:
 *   pqc_keys    — peer_id → session_key (for XDP fast path)
 *   pkt_stats   — packet counters (total/passed/dropped/key_hit)
 */

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define ETH_P_IP 0x0800
#define MAX_PEERS 10240
#define KEY_SIZE 32
#define MAX_PEER_ID_LEN 64

// Stats indices
#define STATS_TOTAL    0
#define STATS_PASSED   1
#define STATS_DROPPED  2
#define STATS_KEY_HIT  3

// Peer ID key for map lookup
struct pqc_key_t {
    char id[MAX_PEER_ID_LEN];
};

// Session key value stored per peer
struct pqc_value_t {
    unsigned char session_key[KEY_SIZE];
    unsigned long long last_updated_ns;
    unsigned int flags;
    unsigned int hit_count;
};

// Map: peer_id → session key (LRU for automatic eviction)
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, MAX_PEERS);
    __type(key, struct pqc_key_t);
    __type(value, struct pqc_value_t);
} pqc_keys SEC(".maps");

// Packet stats (per-CPU for lock-free updates)
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 4);
    __type(key, __u32);
    __type(value, __u64);
} pkt_stats SEC(".maps");

static __always_inline void incr_stat(__u32 idx) {
    __u64 *val = bpf_map_lookup_elem(&pkt_stats, &idx);
    if (val)
        *val += 1;
}

/*
 * extract_src_ip — parse Ethernet→IP and return source IP in network order.
 * Returns 0 on failure (non-IP or truncated packet).
 */
static __always_inline __u32 extract_src_ip(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return 0;
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return 0;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return 0;

    return ip->saddr;
}

/*
 * xdp_pqc_filter — main XDP program.
 *
 * For each incoming packet:
 *   1. Extract source IP as peer identifier
 *   2. Lookup session key in pqc_keys map
 *   3. If key found → mark packet for fast-path decryption
 *   4. Always PASS (decryption happens in userspace or TC layer)
 */
SEC("xdp")
int xdp_pqc_filter(struct xdp_md *ctx) {
    incr_stat(STATS_TOTAL);

    __u32 src_ip = extract_src_ip(ctx);
    if (src_ip == 0) {
        incr_stat(STATS_PASSED);
        return XDP_PASS;
    }

    // Build lookup key from source IP
    struct pqc_key_t key = {};
    // Pack IP into first 4 bytes of key id
    __u32 ip_net = src_ip; // already in network order
    __builtin_memcpy(&key.id, &ip_net, sizeof(ip_net));

    // Lookup session key
    struct pqc_value_t *val = bpf_map_lookup_elem(&pqc_keys, &key);
    if (val) {
        incr_stat(STATS_KEY_HIT);
        // Key found — packet can use fast-path decryption.
        // The actual decryption is done in TC layer or userspace;
        // XDP only signals that a key is available.
        val->hit_count += 1;
    }

    incr_stat(STATS_PASSED);
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
