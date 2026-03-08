//go:build ignore
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);   // Peer IP / ID
    __type(value, __u32); // Connection count
} conn_map SEC(".maps");

SEC("kprobe/tcp_v4_connect")
int BPF_KPROBE(tcp_v4_connect) {
    __u32 dummy_peer = 1;
    __u32 *count = bpf_map_lookup_elem(&conn_map, &dummy_peer);
    __u32 new_count = count ? *count + 1 : 1;
    bpf_map_update_elem(&conn_map, &dummy_peer, &new_count, BPF_ANY);
    return 0;
}

char _license[] SEC("license") = "GPL";