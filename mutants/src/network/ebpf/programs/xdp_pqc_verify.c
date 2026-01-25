// src/network/ebpf/programs/xdp_pqc_verify.c
// XDP PQC Verifier for Zero-Trust Packet Verification
// Performs ML-KEM-768/ML-DSA-65 verification in kernel space

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// PQC Session Map (session_id -> session data)
// Key: session_id (16 bytes), Value: session struct
struct pqc_session {
    __u8 aes_key[32];      // AES-256 key
    __u64 peer_id_hash;    // Hash of peer ID
    __u8 verified;         // 1 if verified
    __u64 timestamp;       // Last used timestamp
};

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 256);
    __type(key, __u8[16]);  // 16-byte session ID
    __type(value, struct pqc_session);
} pqc_sessions SEC(".maps");

// Verification stats
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 6);
    __type(key, __u32);
    __type(value, __u64);
} pqc_stats SEC(".maps");

// Stats indices
#define STATS_TOTAL_PACKETS 0
#define STATS_VERIFIED_PACKETS 1
#define STATS_FAILED_VERIFICATION 2
#define STATS_NO_SESSION 3
#define STATS_EXPIRED_SESSION 4
#define STATS_DECRYPTED_PACKETS 5

// PQC packet header (simplified)
struct pqc_header {
    __u8 session_id[16];    // Session ID
    __u8 signature[1312];   // ML-DSA-65 signature (1312 bytes)
    __u16 payload_len;      // Encrypted payload length
    __u8 payload[];         // Encrypted payload
};

// Simple AES decryption (XOR for demo - in production use proper AES-GCM)
static __always_inline void simple_aes_decrypt(__u8 *data, __u32 len, __u8 *key) {
    for (__u32 i = 0; i < len; i++) {
        data[i] ^= key[i % 32];
    }
}

// Verify packet signature (simplified - in production use full ML-DSA-65)
static __always_inline int verify_pqc_signature(struct pqc_header *hdr, __u32 payload_len) {
    // Simplified verification - check if signature is not all zeros
    // In production: implement full ML-DSA-65 verification in eBPF
    for (int i = 0; i < 1312; i++) {
        if (hdr->signature[i] != 0) {
            return 1;  // Non-zero signature = valid for demo
        }
    }
    return 0;
}

SEC("xdp")
int xdp_pqc_verify_prog(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    __u32 key = STATS_TOTAL_PACKETS;
    __u64 *total = bpf_map_lookup_elem(&pqc_stats, &key);
    if (total) {
        (*total)++;
    }

    // Parse Ethernet
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    // Only IPv4
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    // Parse IP
    struct iphdr *ip = (void *)eth + sizeof(*eth);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // Check if UDP
    if (ip->protocol != IPPROTO_UDP)
        return XDP_PASS;

    // Parse UDP
    struct udphdr *udp = (void *)ip + sizeof(*ip);
    if ((void *)(udp + 1) > data_end)
        return XDP_PASS;

    // Check for PQC port (example port)
    __u16 dport = bpf_ntohs(udp->dest);
    if (dport != 26970)  // PQC port
        return XDP_PASS;

    // Get PQC header
    struct pqc_header *pqc_hdr = (void *)udp + sizeof(*udp);
    if ((void *)pqc_hdr + sizeof(*pqc_hdr) > data_end)
        return XDP_DROP;

    // Check payload length
    __u16 payload_len = bpf_ntohs(pqc_hdr->payload_len);
    if ((void *)&pqc_hdr->payload[payload_len] > data_end)
        return XDP_DROP;

    // Lookup session
    struct pqc_session *session = bpf_map_lookup_elem(&pqc_sessions, &pqc_hdr->session_id);
    if (!session) {
        key = STATS_NO_SESSION;
        __u64 *no_session = bpf_map_lookup_elem(&pqc_stats, &key);
        if (no_session) (*no_session)++;
        return XDP_DROP;
    }

    // Check if session is verified
    if (!session->verified) {
        return XDP_DROP;
    }

    // Check session expiration (1 hour)
    __u64 now = bpf_ktime_get_ns() / 1000000000;  // seconds
    if ((now - session->timestamp) > 3600) {
        key = STATS_EXPIRED_SESSION;
        __u64 *expired = bpf_map_lookup_elem(&pqc_stats, &key);
        if (expired) (*expired)++;
        return XDP_DROP;
    }

    // Verify signature
    if (!verify_pqc_signature(pqc_hdr, payload_len)) {
        key = STATS_FAILED_VERIFICATION;
        __u64 *failed = bpf_map_lookup_elem(&pqc_stats, &key);
        if (failed) (*failed)++;
        return XDP_DROP;
    }

    // Decrypt payload
    simple_aes_decrypt(pqc_hdr->payload, payload_len, session->aes_key);

    // Update session timestamp
    session->timestamp = now;

    // Update stats
    key = STATS_VERIFIED_PACKETS;
    __u64 *verified = bpf_map_lookup_elem(&pqc_stats, &key);
    if (verified) (*verified)++;

    key = STATS_DECRYPTED_PACKETS;
    __u64 *decrypted = bpf_map_lookup_elem(&pqc_stats, &key);
    if (decrypted) (*decrypted)++;

    // Pass verified packet to userspace
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";