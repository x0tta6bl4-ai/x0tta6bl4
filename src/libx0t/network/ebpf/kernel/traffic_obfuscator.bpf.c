// SPDX-License-Identifier: Apache-2.0
// Traffic Obfuscator eBPF Program for x0tta6bl4
// Performs kernel-level XOR obfuscation to bypass DPI

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/pkt_cls.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// Maximum payload size to obfuscate in one go (instruction limit)
#define MAX_OBFUSCATION_LEN 256

// Obfuscation config map
struct obfuscation_config {
    __u8 xor_key[32];
    __u32 enabled;
    __u32 mode; // 0=XOR, 1=RESERVED
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct obfuscation_config);
} config_map SEC(".maps");

// Helper to apply XOR
static __always_inline void apply_xor(void *data, __u32 len, __u8 *key, __u32 key_len) {
    __u8 *d = data;
    for (__u32 i = 0; i < MAX_OBFUSCATION_LEN; i++) {
        if (i >= len) break;
        d[i] ^= key[i % key_len];
    }
}

SEC("tc")
int tc_obfuscate(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    
    // Read config
    __u32 zero = 0;
    struct obfuscation_config *conf = bpf_map_lookup_elem(&config_map, &zero);
    if (!conf || !conf->enabled)
        return TC_ACT_OK;

    // Parse Ethernet header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return TC_ACT_OK;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return TC_ACT_OK;

    // Parse IP header
    struct iphdr *iph = (void *)(eth + 1);
    if ((void *)(iph + 1) > data_end)
        return TC_ACT_OK;

    // Only obfuscate TCP/UDP for now
    void *payload = NULL;
    __u32 payload_len = 0;

    if (iph->protocol == IPPROTO_TCP) {
        struct tcphdr *tcph = (void *)(iph + 1);
        if ((void *)(tcph + 1) > data_end)
            return TC_ACT_OK;
        payload = (void *)(tcph + 1);
        payload_len = bpf_ntohs(iph->tot_len) - (iph->ihl * 4) - (tcph->doff * 4);
    } else if (iph->protocol == IPPROTO_UDP) {
        struct udphdr *udph = (void *)(iph + 1);
        if ((void *)(udph + 1) > data_end)
            return TC_ACT_OK;
        payload = (void *)(udph + 1);
        payload_len = bpf_ntohs(udph->len) - sizeof(struct udphdr);
    } else {
        return TC_ACT_OK;
    }

    if (!payload || payload_len == 0)
        return TC_ACT_OK;

    // Cap payload length to safety limits
    if (payload_len > MAX_OBFUSCATION_LEN)
        payload_len = MAX_OBFUSCATION_LEN;

    // Verify bounds again before writing
    if ((void *)payload + payload_len > data_end)
        return TC_ACT_OK;

    // Apply XOR obfuscation
    apply_xor(payload, payload_len, conf->xor_key, 32);

    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
