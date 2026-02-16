/*
 * x0tta6bl4 Tracepoint Hooks for Network Events
 * 
 * Uses kernel tracepoints for network event observability.
 * 
 * Features:
 * - Trace net:net_dev_xmit (egress)
 * - Trace net:netif_receive_skb (ingress)
 * - Trace sched:sched_switch (context switching)
 * - Low overhead (tracepoints are static, no kprobe overhead)
 * 
 * Compile with CO-RE:
 *   clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
 *         -c tracepoint_net.c -o tracepoint_net.o
 */

/*
 * x0tta6bl4 Tracepoint Hooks for Network Events
 * 
 * Uses kernel tracepoints for network event observability.
 * 
 * Features:
 * - Trace net:net_dev_xmit (egress)
 * - Trace net:netif_receive_skb (ingress)
 * - Trace sched:sched_switch (context switching)
 * - Low overhead (tracepoints are static, no kprobe overhead)
 * 
 * Compile with CO-RE:
 *   clang -O2 -g -target bpf -D__TARGET_ARCH_x86 \
 *         -c tracepoint_net.c -o tracepoint_net.o
 */

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

/* Network device statistics */
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_HASH);
    __uint(max_entries, 64);  // Track up to 64 network interfaces
    __type(key, __u32);  // ifindex
    __type(value, __u64);  // packet count
} net_dev_stats SEC(".maps");

/* Ring buffer for high-throughput event output */
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 512 * 1024);  // 512 KB
} net_events SEC(".maps");

/* Event structure */
struct net_event {
    __u32 ifindex;
    __u32 len;
    __u16 protocol;
    __u8 direction;  // 0=ingress, 1=egress
    __u64 timestamp;
};

/* Trace network device transmit (egress) */
SEC("tracepoint/net/net_dev_xmit")
int trace_net_dev_xmit(struct trace_event_raw_net_dev_template *ctx)
{
    struct net_event event = {};
    __u64 timestamp = bpf_ktime_get_ns();
    
    // CO-RE: Read ifindex from tracepoint context
    __u32 ifindex = 0;
    struct sk_buff *skb = (struct sk_buff *)ctx->skbaddr;
    bpf_core_read(&ifindex, sizeof(ifindex), &skb->dev->ifindex);
    
    // Update per-CPU stats
    __u64 *count = bpf_map_lookup_elem(&net_dev_stats, &ifindex);
    if (count) {
        __sync_fetch_and_add(count, 1);
    } else {
        __u64 initial = 1;
        bpf_map_update_elem(&net_dev_stats, &ifindex, &initial, BPF_NOEXIST);
    }
    
    // Send event to ring buffer (optional, for detailed analysis)
    event.ifindex = ifindex;
    event.direction = 1;  // egress
    event.timestamp = timestamp;
    
    // Reserve space in ring buffer
    struct net_event *ring_event = bpf_ringbuf_reserve(&net_events, sizeof(event), 0);
    if (ring_event) {
        *ring_event = event;
        bpf_ringbuf_submit(ring_event, 0);
    }
    
    return 0;
}

/* Trace network receive (ingress) */
SEC("tracepoint/net/netif_receive_skb")
int trace_netif_receive_skb(struct trace_event_raw_net_dev_template *ctx)
{
    struct net_event event = {};
    __u64 timestamp = bpf_ktime_get_ns();
    
    // CO-RE: Read ifindex
    __u32 ifindex = 0;
    struct sk_buff *skb = (struct sk_buff *)ctx->skbaddr;
    bpf_core_read(&ifindex, sizeof(ifindex), &skb->dev->ifindex);
    
    // Update stats
    __u64 *count = bpf_map_lookup_elem(&net_dev_stats, &ifindex);
    if (count) {
        __sync_fetch_and_add(count, 1);
    } else {
        __u64 initial = 1;
        bpf_map_update_elem(&net_dev_stats, &ifindex, &initial, BPF_NOEXIST);
    }
    
    // Ring buffer event
    event.ifindex = ifindex;
    event.direction = 0;  // ingress
    event.timestamp = timestamp;
    
    struct net_event *ring_event = bpf_ringbuf_reserve(&net_events, sizeof(event), 0);
    if (ring_event) {
        *ring_event = event;
        bpf_ringbuf_submit(ring_event, 0);
    }
    
    return 0;
}

char LICENSE[] SEC("license") = "GPL";

