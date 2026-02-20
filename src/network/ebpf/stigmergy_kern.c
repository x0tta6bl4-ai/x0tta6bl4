#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <bpf/bpf_helpers.h>

// --- Maps ---

// Map: Neighbor IP -> Pheromone Score (u32)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);   // IPv4 Address
    __type(value, __u32); // Score (0-10000)
} pheromone_map SEC(".maps");

// --- Helpers ---

// Simple linear reward function
static void reinforce(__u32 peer_ip, __u32 amount) {
    __u32 *score = bpf_map_lookup_elem(&pheromone_map, &peer_ip);
    if (score) {
        // Atomic add to prevent race conditions
        __sync_fetch_and_add(score, amount);
    } else {
        // Initial score
        __u32 initial = 100;
        bpf_map_update_elem(&pheromone_map, &peer_ip, &initial, BPF_NOEXIST);
    }
}

// --- Main XDP Program ---

SEC("xdp_stigmergy")
int xdp_prog(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // 1. Parse Ethernet
    struct ethhdr *eth = data;
    if (data + sizeof(*eth) > data_end)
        return XDP_PASS;

    if (eth->h_proto != __constant_htons(ETH_P_IP))
        return XDP_PASS;

    // 2. Parse IP
    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // 3. Stigmergy Logic: Detect "Success" signals
    // For TCP, an ACK is a sign that the path works.
    if (ip->protocol == IPPROTO_TCP) {
        struct tcphdr *tcp = (void *)ip + (ip->ihl * 4);
        if ((void *)(tcp + 1) > data_end)
            return XDP_PASS;

        if (tcp->ack) {
            // Reinforce the sender (Source IP) because they successfully replied
            reinforce(ip->saddr, 10); // +10 score for ACK
        }
    }
    
    // TODO: UDP implementation (needs app-level headers or custom protocol)

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
