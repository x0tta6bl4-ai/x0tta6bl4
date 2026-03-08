//go:build ignore
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64); // Bytes
} bandwidth_map SEC(".maps");

SEC("xdp")
int monitor_bandwidth(struct xdp_md *ctx) {
    __u32 key = 0;
    __u64 bytes = ctx->data_end - ctx->data;
    __u64 *val = bpf_map_lookup_elem(&bandwidth_map, &key);
    if (val) {
        *val += bytes;
    }
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";