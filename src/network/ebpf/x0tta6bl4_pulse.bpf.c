// Minimal x0tta6bl4_pulse XDP source marker for evidence inventory.
//
// Claim boundary: this source file and the retained object file are static
// local artifacts. They do not prove that an XDP program is attached, that a
// pulse_stats map is live, that packets traversed a real dataplane, or that
// production readiness is achieved.

#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} pulse_stats SEC(".maps");

SEC("xdp")
int xdp_x0tta6bl4_pulse(struct xdp_md *ctx)
{
    __u32 key = 0;
    __u64 *counter = bpf_map_lookup_elem(&pulse_stats, &key);

    if (counter) {
        __sync_fetch_and_add(counter, 1);
    }
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
