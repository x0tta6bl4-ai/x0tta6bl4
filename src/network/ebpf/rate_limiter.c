/*
 * x0tta6bl4 eBPF Rate Limiter
 * Limits bandwidth for specific interfaces/nodes.
 * Strategy: Drop packets if rate exceeds threshold.
 */

#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/pkt_cls.h>

struct config {
    u64 max_bytes_per_sec;
    u64 last_time;
    u64 tokens;
};

BPF_HASH(limit_config, u32, struct config);

int handle_egress(struct __sk_buff *skb) {
    u32 key = 0;
    u64 now = bpf_ktime_get_ns();
    struct config *cfg = limit_config.lookup(&key);

    if (!cfg) return TC_ACT_OK;
    if (cfg->max_bytes_per_sec == 0) return TC_ACT_OK; // No limit

    // Token bucket logic
    u64 elapsed = now - cfg->last_time;
    u64 new_tokens = (elapsed * cfg->max_bytes_per_sec) / 1000000000;
    
    cfg->tokens += new_tokens;
    if (cfg->tokens > cfg->max_bytes_per_sec) {
        cfg->tokens = cfg->max_bytes_per_sec;
    }
    cfg->last_time = now;

    if (cfg->tokens >= skb->len) {
        cfg->tokens -= skb->len;
        return TC_ACT_OK;
    } else {
        // Soft-lock: drop packet if no tokens left
        return TC_ACT_SHOT;
    }
}
