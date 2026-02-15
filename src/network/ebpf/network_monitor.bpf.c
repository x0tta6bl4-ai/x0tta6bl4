// SPDX-License-Identifier: Apache-2.0
// Network Monitor eBPF Program for x0tta6bl4
// Monitors network traffic, latency, and packet loss at kernel level

#include <linux/if_packet.h>
#include <linux/skbuff.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

// Maximum number of connections to track
#define MAX_CONNECTIONS 1024
#define MAX_CPUS 128

// Network key structure
struct network_key {
    __u32 saddr;  // Source IP (hashed)
    __u32 daddr;  // Destination IP (hashed)
    __u16 sport;  // Source port
    __u16 dport;  // Destination port
    __u8 protocol; // TCP/UDP
};

// Network metrics structure
struct network_metrics {
    __u64 packets_ingress;
    __u64 packets_egress;
    __u64 bytes_ingress;
    __u64 bytes_egress;
    __u64 packet_loss;
    __u64 retransmissions;
    __u64 connection_errors;
    __u64 last_update_ns;
    __u64 rtt_ns;  // Round-trip time
};

// Network event structure
struct network_event {
    __u32 cpu_id;
    __u64 timestamp_ns;
    __u32 event_type;  // 1=packet, 2=loss, 3=error, 4=latency
    __u32 saddr_hash;
    __u32 daddr_hash;
    __u16 sport;
    __u16 dport;
    __u8 protocol;
    __u64 value;
};

// Connection tracking map
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_CONNECTIONS);
    __type(key, struct network_key);
    __type(value, struct network_metrics);
} connection_map SEC(".maps");

// Per-CPU network events
struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(max_entries, MAX_CPUS);
    __type(key, __u32);
    __type(value, struct network_event);
} network_events SEC(".maps");

// System-wide network metrics
struct system_network_metrics {
    __u64 total_packets_ingress;
    __u64 total_packets_egress;
    __u64 total_bytes_ingress;
    __u64 total_bytes_egress;
    __u64 total_packet_loss;
    __u64 total_retransmissions;
    __u64 total_connection_errors;
    __u64 active_connections;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct system_network_metrics);
} system_network_map SEC(".maps");

// Packet loss tracking
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 256);
    __type(key, __u32);
    __type(value, __u64);
} packet_loss_map SEC(".maps");

// Helper function to hash IP address
static __always_inline __u32 hash_ip(__be32 ip) {
    return ip;
}

// Helper function to get current timestamp
static __always_inline __u64 get_timestamp(void) {
    return bpf_ktime_get_ns();
}

// Helper function to create network key
static __always_inline void create_network_key(
    struct network_key *key,
    __be32 saddr,
    __be32 daddr,
    __be16 sport,
    __be16 dport,
    __u8 protocol
) {
    key->saddr = hash_ip(saddr);
    key->daddr = hash_ip(daddr);
    key->sport = sport;
    key->dport = dport;
    key->protocol = protocol;
}

// TC: Ingress packet monitoring
SEC("tc")
int tc_ingress(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    
    // Parse IP header
    struct iphdr *iph = data;
    if ((void *)(iph + 1) > data_end)
        return TC_ACT_OK;
    
    __be32 saddr = iph->saddr;
    __be32 daddr = iph->daddr;
    __u8 protocol = iph->protocol;
    
    // Parse transport header
    __be16 sport = 0, dport = 0;
    
    if (protocol == IPPROTO_TCP) {
        struct tcphdr *tcph = (void *)(iph + 1);
        if ((void *)(tcph + 1) > data_end)
            return TC_ACT_OK;
        sport = tcph->source;
        dport = tcph->dest;
    } else if (protocol == IPPROTO_UDP) {
        struct udphdr *udph = (void *)(iph + 1);
        if ((void *)(udph + 1) > data_end)
            return TC_ACT_OK;
        sport = udph->source;
        dport = udph->dest;
    } else {
        return TC_ACT_OK;
    }
    
    // Create network key
    struct network_key key;
    create_network_key(&key, saddr, daddr, sport, dport, protocol);
    
    // Update connection metrics
    struct network_metrics *metrics = bpf_map_lookup_elem(&connection_map, &key);
    if (!metrics) {
        // Initialize new connection
        struct network_metrics new_metrics = {
            .packets_ingress = 1,
            .packets_egress = 0,
            .bytes_ingress = skb->len,
            .bytes_egress = 0,
            .packet_loss = 0,
            .retransmissions = 0,
            .connection_errors = 0,
            .last_update_ns = get_timestamp(),
            .rtt_ns = 0
        };
        bpf_map_update_elem(&connection_map, &key, &new_metrics, BPF_ANY);
    } else {
        __sync_fetch_and_add(&metrics->packets_ingress, 1);
        __sync_fetch_and_add(&metrics->bytes_ingress, skb->len);
        metrics->last_update_ns = get_timestamp();
    }
    
    // Update system-wide metrics
    struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_packets_ingress, 1);
        __sync_fetch_and_add(&sys_metrics->total_bytes_ingress, skb->len);
    }
    
    // Send network event
    struct network_event event = {
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 1,  // packet
        .saddr_hash = hash_ip(saddr),
        .daddr_hash = hash_ip(daddr),
        .sport = sport,
        .dport = dport,
        .protocol = protocol,
        .value = skb->len
    };
    
    bpf_perf_event_output(skb, &network_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return TC_ACT_OK;
}

// TC: Egress packet monitoring
SEC("tc")
int tc_egress(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    
    // Parse IP header
    struct iphdr *iph = data;
    if ((void *)(iph + 1) > data_end)
        return TC_ACT_OK;
    
    __be32 saddr = iph->saddr;
    __be32 daddr = iph->daddr;
    __u8 protocol = iph->protocol;
    
    // Parse transport header
    __be16 sport = 0, dport = 0;
    
    if (protocol == IPPROTO_TCP) {
        struct tcphdr *tcph = (void *)(iph + 1);
        if ((void *)(tcph + 1) > data_end)
            return TC_ACT_OK;
        sport = tcph->source;
        dport = tcph->dest;
    } else if (protocol == IPPROTO_UDP) {
        struct udphdr *udph = (void *)(iph + 1);
        if ((void *)(udph + 1) > data_end)
            return TC_ACT_OK;
        sport = udph->source;
        dport = udph->dest;
    } else {
        return TC_ACT_OK;
    }
    
    // Create network key
    struct network_key key;
    create_network_key(&key, saddr, daddr, sport, dport, protocol);
    
    // Update connection metrics
    struct network_metrics *metrics = bpf_map_lookup_elem(&connection_map, &key);
    if (!metrics) {
        // Initialize new connection
        struct network_metrics new_metrics = {
            .packets_ingress = 0,
            .packets_egress = 1,
            .bytes_ingress = 0,
            .bytes_egress = skb->len,
            .packet_loss = 0,
            .retransmissions = 0,
            .connection_errors = 0,
            .last_update_ns = get_timestamp(),
            .rtt_ns = 0
        };
        bpf_map_update_elem(&connection_map, &key, &new_metrics, BPF_ANY);
    } else {
        __sync_fetch_and_add(&metrics->packets_egress, 1);
        __sync_fetch_and_add(&metrics->bytes_egress, skb->len);
        metrics->last_update_ns = get_timestamp();
    }
    
    // Update system-wide metrics
    struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_packets_egress, 1);
        __sync_fetch_and_add(&sys_metrics->total_bytes_egress, skb->len);
    }
    
    // Send network event
    struct network_event event = {
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 1,  // packet
        .saddr_hash = hash_ip(saddr),
        .daddr_hash = hash_ip(daddr),
        .sport = sport,
        .dport = dport,
        .protocol = protocol,
        .value = skb->len
    };
    
    bpf_perf_event_output(skb, &network_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return TC_ACT_OK;
}

// Kprobe: kfree_skb - Packet drop monitoring
SEC("kprobe/kfree_skb")
int BPF_KPROBE(kfree_skb) {
    struct sk_buff *skb = (struct sk_buff *)PT_REGS_PARM1(ctx);
    
    // Get packet length
    __u32 len = 0;
    bpf_probe_read_kernel(&len, sizeof(len), &skb->len);
    
    // Update packet loss tracking
    __u32 key = 0;
    __u64 *loss_count = bpf_map_lookup_elem(&packet_loss_map, &key);
    if (loss_count) {
        __sync_fetch_and_add(loss_count, 1);
    } else {
        __u64 new_count = 1;
        bpf_map_update_elem(&packet_loss_map, &key, &new_count, BPF_ANY);
    }
    
    // Update system-wide metrics
    struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_packet_loss, 1);
    }
    
    // Send network event
    struct network_event event = {
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 2,  // packet loss
        .value = len
    };
    
    bpf_perf_event_output(ctx, &network_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: tcp_retransmit_skb - TCP retransmission monitoring
SEC("tp/tcp/tcp_retransmit_skb")
int trace_tcp_retransmit(struct trace_event_raw_tcp_retransmit_skb *ctx) {
    // Update system-wide metrics
    struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_retransmissions, 1);
    }
    
    // Send network event
    struct network_event event = {
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 3,  // retransmission
        .value = 1
    };
    
    bpf_perf_event_output(ctx, &network_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: inet_sock_set_state - TCP connection state monitoring
SEC("tp/sock/inet_sock_set_state")
int trace_inet_sock_set_state(struct trace_event_raw_inet_sock_set_state *ctx) {
    __u8 oldstate = ctx->oldstate;
    __u8 newstate = ctx->newstate;
    
    // Count active connections (ESTABLISHED state)
    if (newstate == TCP_ESTABLISHED) {
        struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
        if (sys_metrics) {
            __sync_fetch_and_add(&sys_metrics->active_connections, 1);
        }
    } else if (oldstate == TCP_ESTABLISHED) {
        struct system_network_metrics *sys_metrics = bpf_map_lookup_elem(&system_network_map, &(__u32){0});
        if (sys_metrics) {
            __sync_fetch_and_sub(&sys_metrics->active_connections, 1);
        }
    }
    
    return 0;
}

// License string
char _license[] SEC("license") = "GPL";
