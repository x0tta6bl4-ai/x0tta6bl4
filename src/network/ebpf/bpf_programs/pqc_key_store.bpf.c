/*
 * PQC Key Store eBPF Program for x0tta6bl4
 * Stores and lookups session keys derived from ML-KEM-768
 */

#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

#define MAX_PEERS 1024
#define KEY_SIZE 32 // Size for ML-KEM-768 derived session key

// Structure for the key (peer_id)
struct key_t {
    char id[64];
};

// Structure to store peer key info
struct peer_key_t {
    unsigned char session_key[KEY_SIZE];
    unsigned long long last_updated_ns;
    unsigned int flags;
};

// Map to store keys indexed by peer_id
BPF_HASH(pqc_keys, struct key_t, struct peer_key_t, MAX_PEERS);

/**
 * dummy_pqc_filter - Placeholder for data plane validation
 */
int dummy_pqc_filter(struct __sk_buff *skb) {
    return 1;
}
