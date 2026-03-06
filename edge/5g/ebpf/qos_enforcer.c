#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <linux/in.h> // Для IPPROTO_UDP
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32);   // UDP Port (as Slice ID proxy)
    __type(value, __u32); // Priority (0 = Drop, 1+ = Pass)
} slice_policy_map SEC(".maps");

SEC("xdp")
int xdp_qos_enforcer(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;

    if (ip->protocol != IPPROTO_UDP) return XDP_PASS;

    struct udphdr *udp = (void *)ip + sizeof(*ip);
    if ((void *)(udp + 1) > data_end) return XDP_PASS;

    __u32 port = bpf_ntohs(udp->dest);
    __u32 *policy = bpf_map_lookup_elem(&slice_policy_map, &port);

    if (policy) {
        if (*policy == 0) {
            return XDP_DROP;
        }
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
