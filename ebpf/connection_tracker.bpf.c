//go:build ignore
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);   // Destination IP (network byte order)
    __type(value, __u32); // Connection count per peer
} conn_map SEC(".maps");

// Global connection counter (all peers combined)
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} conn_total SEC(".maps");

SEC("kprobe/tcp_v4_connect")
int BPF_KPROBE(tcp_v4_connect, struct sock *sk) {
    // Extract destination IP from the socket's connected address.
    // sk->__sk_common.skc_daddr holds the 4-byte IPv4 destination in network order.
    __u32 dst_ip = 0;
    bpf_probe_read(&dst_ip, sizeof(dst_ip), &sk->__sk_common.skc_daddr);

    if (dst_ip == 0)
        return 0;

    // Per-peer connection count
    __u32 *count = bpf_map_lookup_elem(&conn_map, &dst_ip);
    __u32 new_count = count ? *count + 1 : 1;
    bpf_map_update_elem(&conn_map, &dst_ip, &new_count, BPF_ANY);

    // Global counter
    __u32 total_key = 0;
    __u64 *total = bpf_map_lookup_elem(&conn_total, &total_key);
    if (total) {
        *total += 1;
    }

    return 0;
}

char _license[] SEC("license") = "GPL";
