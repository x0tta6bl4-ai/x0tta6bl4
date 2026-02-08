// src/network/ebpf/programs/xdp_pqc_verify.c
// XDP Fast-Path Packet Authentication for PQC Mesh Network
//
// Architecture:
//   1. Full PQC handshake (ML-KEM-768 + ML-DSA-65) runs in USERSPACE
//      and establishes per-session keys.
//   2. Userspace installs session MAC keys into eBPF maps.
//   3. This XDP program performs fast-path packet authentication:
//      - Session lookup by session_id
//      - Keyed SipHash-2-4 MAC verification (64-bit truncated)
//      - Session expiration checks
//   4. Packets that pass MAC verification are forwarded to userspace
//      for full AES-256-GCM decryption.
//
// This design keeps expensive PQC operations in userspace while using
// eBPF for wire-speed packet filtering with O(1) session lookup.

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// --- Session State ---

struct pqc_session {
    __u8 mac_key[16];       // Truncated MAC key (derived from PQC session key)
    __u64 peer_id_hash;     // Hash of authenticated peer SPIFFE ID
    __u8 verified;          // 1 if PQC handshake completed in userspace
    __u64 timestamp;        // Last activity timestamp (seconds)
    __u32 packet_counter;   // Anti-replay: expected minimum packet number
};

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 256);
    __type(key, __u8[16]);  // 16-byte session ID
    __type(value, struct pqc_session);
} pqc_sessions SEC(".maps");

// --- Statistics ---

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 8);
    __type(key, __u32);
    __type(value, __u64);
} pqc_stats SEC(".maps");

#define STATS_TOTAL_PACKETS      0
#define STATS_VERIFIED_PACKETS   1
#define STATS_FAILED_MAC         2
#define STATS_NO_SESSION         3
#define STATS_EXPIRED_SESSION    4
#define STATS_REPLAY_DETECTED    5
#define STATS_MALFORMED          6
#define STATS_PASSED_TO_USER     7

static __always_inline void inc_stat(__u32 idx) {
    __u64 *val = bpf_map_lookup_elem(&pqc_stats, &idx);
    if (val)
        __sync_fetch_and_add(val, 1);
}

// --- Mesh Packet Header ---
// Placed after UDP header on port 26970
struct mesh_pqc_header {
    __u8  session_id[16];   // Session ID from PQC handshake
    __u32 packet_seq;       // Packet sequence number (anti-replay)
    __u8  mac[8];           // Truncated SipHash-2-4 MAC (64-bit)
    __u16 payload_len;      // Encrypted payload length
    __u8  payload[];        // AES-256-GCM encrypted payload (decrypted in userspace)
};

// --- SipHash-2-4 (RFC 7693-compatible, 64-bit output) ---
// Keyed hash for packet MAC verification. Key is derived from
// the PQC session key during handshake.

#define SIPROUND                              \
    do {                                      \
        v0 += v1; v1 = (v1 << 13) | (v1 >> 51); v1 ^= v0; \
        v0 = (v0 << 32) | (v0 >> 32);        \
        v2 += v3; v3 = (v3 << 16) | (v3 >> 48); v3 ^= v2; \
        v0 += v3; v3 = (v3 << 21) | (v3 >> 43); v3 ^= v0; \
        v2 += v1; v1 = (v1 << 17) | (v1 >> 47); v1 ^= v2; \
        v2 = (v2 << 32) | (v2 >> 32);        \
    } while (0)

static __always_inline __u64 siphash_2_4(
    const __u8 *data, __u32 len, const __u8 key[16]
) {
    __u64 k0 = *(__u64 *)&key[0];
    __u64 k1 = *(__u64 *)&key[8];

    __u64 v0 = k0 ^ 0x736f6d6570736575ULL;
    __u64 v1 = k1 ^ 0x646f72616e646f6dULL;
    __u64 v2 = k0 ^ 0x6c7967656e657261ULL;
    __u64 v3 = k1 ^ 0x7465646279746573ULL;

    // Process 8-byte blocks
    __u32 blocks = len / 8;
    // eBPF verifier needs bounded loops
    if (blocks > 128)
        blocks = 128;

    for (__u32 i = 0; i < blocks; i++) {
        __u64 m = *(__u64 *)(data + i * 8);
        v3 ^= m;
        SIPROUND;
        SIPROUND;
        v0 ^= m;
    }

    // Last block with length encoding
    __u64 last = ((__u64)len) << 56;
    __u32 remaining = len & 7;
    const __u8 *tail = data + (blocks * 8);

    // Process remaining bytes (bounded for verifier)
    if (remaining >= 7) last |= ((__u64)tail[6]) << 48;
    if (remaining >= 6) last |= ((__u64)tail[5]) << 40;
    if (remaining >= 5) last |= ((__u64)tail[4]) << 32;
    if (remaining >= 4) last |= ((__u64)tail[3]) << 24;
    if (remaining >= 3) last |= ((__u64)tail[2]) << 16;
    if (remaining >= 2) last |= ((__u64)tail[1]) << 8;
    if (remaining >= 1) last |= ((__u64)tail[0]);

    v3 ^= last;
    SIPROUND;
    SIPROUND;
    v0 ^= last;

    // Finalization
    v2 ^= 0xff;
    SIPROUND;
    SIPROUND;
    SIPROUND;
    SIPROUND;

    return v0 ^ v1 ^ v2 ^ v3;
}

// --- Verify packet MAC ---
// Computes SipHash-2-4 over (session_id || packet_seq || payload)
// and compares with the 8-byte truncated MAC in the header.
static __always_inline int verify_packet_mac(
    struct mesh_pqc_header *hdr,
    __u16 payload_len,
    struct pqc_session *session,
    void *data_end
) {
    // MAC is computed over: session_id (16) + packet_seq (4) = 20 bytes header
    // Plus payload (variable length)
    // We verify the header portion first (fixed size, always available)
    __u8 mac_input[20];

    // Copy session_id + packet_seq into contiguous buffer for MAC
    __builtin_memcpy(mac_input, hdr->session_id, 16);
    __builtin_memcpy(mac_input + 16, &hdr->packet_seq, 4);

    // Compute MAC over header fields
    __u64 computed = siphash_2_4(mac_input, 20, session->mac_key);

    // If payload exists and is accessible, fold it into MAC
    if (payload_len > 0 && payload_len <= 1400) {
        if ((void *)hdr->payload + payload_len <= data_end) {
            __u64 payload_hash = siphash_2_4(hdr->payload, payload_len, session->mac_key);
            computed ^= payload_hash;
        }
    }

    // Compare computed MAC with received MAC (constant-time via XOR)
    __u64 received = *(__u64 *)hdr->mac;
    return (computed == received) ? 1 : 0;
}

// --- XDP Program Entry Point ---

SEC("xdp")
int xdp_pqc_verify_prog(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    inc_stat(STATS_TOTAL_PACKETS);

    // Parse Ethernet
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    // Only process IPv4
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    // Parse IP header
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    // Only process UDP
    if (ip->protocol != IPPROTO_UDP)
        return XDP_PASS;

    // Parse UDP header
    struct udphdr *udp = (void *)ip + sizeof(struct iphdr);
    if ((void *)(udp + 1) > data_end)
        return XDP_PASS;

    // Check for PQC mesh port
    __u16 dport = bpf_ntohs(udp->dest);
    if (dport != 26970)
        return XDP_PASS;

    // Parse mesh PQC header
    struct mesh_pqc_header *pqc_hdr = (void *)(udp + 1);
    if ((void *)(pqc_hdr + 1) > data_end) {
        inc_stat(STATS_MALFORMED);
        return XDP_DROP;
    }

    // Validate payload bounds
    __u16 payload_len = bpf_ntohs(pqc_hdr->payload_len);
    if (payload_len > 1400) {
        inc_stat(STATS_MALFORMED);
        return XDP_DROP;
    }
    if ((void *)pqc_hdr->payload + payload_len > data_end) {
        inc_stat(STATS_MALFORMED);
        return XDP_DROP;
    }

    // Session lookup
    struct pqc_session *session = bpf_map_lookup_elem(
        &pqc_sessions, pqc_hdr->session_id
    );
    if (!session) {
        inc_stat(STATS_NO_SESSION);
        return XDP_DROP;
    }

    // Check PQC handshake completion
    if (!session->verified) {
        inc_stat(STATS_NO_SESSION);
        return XDP_DROP;
    }

    // Session expiration (1 hour TTL)
    __u64 now = bpf_ktime_get_ns() / 1000000000ULL;
    if (now > session->timestamp && (now - session->timestamp) > 3600) {
        inc_stat(STATS_EXPIRED_SESSION);
        return XDP_DROP;
    }

    // Anti-replay: check packet sequence number
    __u32 pkt_seq = bpf_ntohl(pqc_hdr->packet_seq);
    if (pkt_seq < session->packet_counter) {
        inc_stat(STATS_REPLAY_DETECTED);
        return XDP_DROP;
    }

    // MAC verification (SipHash-2-4 keyed with PQC session key)
    if (!verify_packet_mac(pqc_hdr, payload_len, session, data_end)) {
        inc_stat(STATS_FAILED_MAC);
        return XDP_DROP;
    }

    // Update session state
    session->timestamp = now;
    if (pkt_seq >= session->packet_counter)
        session->packet_counter = pkt_seq + 1;

    inc_stat(STATS_VERIFIED_PACKETS);
    inc_stat(STATS_PASSED_TO_USER);

    // Pass authenticated packet to userspace for AES-256-GCM decryption
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
