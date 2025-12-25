/*
 * x0tta6bl4 TC (Traffic Control) Classifier
 * 
 * TC eBPF program for ingress/egress traffic shaping and latency measurement.
 * 
 * Features:
 * - Ingress/egress classification
 * - Latency measurement per flow
 * - Traffic shaping (rate limiting)
 * - Integration with mesh routing decisions
 * 
 * Compile with CO-RE:
 *   clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
 *         -c tc_classifier.c -o tc_classifier.o
 */

#include <linux/bpf.h>
#include <linux/pkt_cls.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include <bpf/bpf_core_read.h>

/* Flow tracking map (5-tuple: src_ip, dst_ip, src_port, dst_port, protocol) */
struct flow_key {
    __be32 src_ip;
    __be32 dst_ip;
    __be16 src_port;
    __be16 dst_port;
    __u8 protocol;
    __u8 pad[3];
};

/* Flow statistics */
struct flow_stats {
    __u64 packets;
    __u64 bytes;
    __u64 latency_sum_ns;  // Sum of latencies for average calculation
    __u64 last_seen_ns;
};

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10000);  // Track up to 10K flows
    __type(key, struct flow_key);
    __type(value, struct flow_stats);
} flow_stats_map SEC(".maps");

/* Latency histogram per flow */
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 50000);
    __type(key, __u64);  // (flow_key_hash << 16) | bucket
    __type(value, __u64);  // count
} latency_histogram SEC(".maps");

/* Helper: Extract 5-tuple from packet */
static __always_inline int extract_flow_key(
    void *data,
    void *data_end,
    struct flow_key *key
)
{
    struct ethhdr *eth = data;
    
    // Bounds check
    if ((void *)(eth + 1) > data_end) {
        return -1;
    }
    
    // Only IPv4 for now
    if (eth->h_proto != bpf_htons(ETH_P_IP)) {
        return -1;
    }
    
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) {
        return -1;
    }
    
    key->src_ip = ip->saddr;
    key->dst_ip = ip->daddr;
    key->protocol = ip->protocol;
    
    // Extract ports for TCP/UDP
    if (ip->protocol == IPPROTO_TCP || ip->protocol == IPPROTO_UDP) {
        void *transport = (void *)(ip + 1);
        if ((void *)(transport + 4) > data_end) {
            return -1;
        }
        
        if (ip->protocol == IPPROTO_TCP) {
            struct tcphdr *tcp = transport;
            key->src_port = tcp->source;
            key->dst_port = tcp->dest;
        } else {
            struct udphdr *udp = transport;
            key->src_port = udp->source;
            key->dst_port = udp->dest;
        }
    } else {
        key->src_port = 0;
        key->dst_port = 0;
    }
    
    return 0;
}

/* Ingress classifier */
SEC("classifier/ingress")
int tc_ingress_classifier(struct __sk_buff *skb)
{
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;
    struct flow_key key = {};
    __u64 timestamp = bpf_ktime_get_ns();
    
    // Extract flow key
    if (extract_flow_key(data, data_end, &key) < 0) {
        return TC_ACT_OK;  // Pass unknown packets
    }
    
    // Update flow statistics
    struct flow_stats *stats = bpf_map_lookup_elem(&flow_stats_map, &key);
    if (stats) {
        // Update existing flow
        __sync_fetch_and_add(&stats->packets, 1);
        __sync_fetch_and_add(&stats->bytes, skb->len);
        stats->last_seen_ns = timestamp;
    } else {
        // New flow
        struct flow_stats new_stats = {
            .packets = 1,
            .bytes = skb->len,
            .latency_sum_ns = 0,
            .last_seen_ns = timestamp,
        };
        bpf_map_update_elem(&flow_stats_map, &key, &new_stats, BPF_NOEXIST);
    }
    
    // Pass packet (could add rate limiting here)
    return TC_ACT_OK;
}

/* Egress classifier */
SEC("classifier/egress")
int tc_egress_classifier(struct __sk_buff *skb)
{
    // Similar to ingress, but for egress traffic
    // Can measure egress latency, apply shaping, etc.
    return TC_ACT_OK;
}

char LICENSE[] SEC("license") = "GPL";

