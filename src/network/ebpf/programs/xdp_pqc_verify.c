// src/network/ebpf/programs/xdp_pqc_verify.c
// BCC Minimalist Fast-Path for PQC Mesh Network

struct session_key {
    unsigned char id[16];
};

struct pqc_session {
    unsigned char mac_key[16];
    unsigned long long peer_id_hash;
    unsigned char verified;
    unsigned long long timestamp;
    unsigned long long last_seq;
    unsigned long long window_bitmap;
};

BPF_HASH(pqc_sessions, struct session_key, struct pqc_session, 65536);

int xdp_pqc_verify_prog(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    // Ethernet
    if (data + 14 > data_end) return 2; // XDP_PASS

    // IP Check (very raw)
    unsigned char *ip = data + 14;
    if (data + 14 + 20 > data_end) return 2;
    if (ip[9] != 17) return 2; // Not UDP

    // UDP Check
    unsigned char *udp = ip + 20;
    if (data + 14 + 20 + 8 > data_end) return 2;
    
    // Dest Port 26970 (0x695A)
    unsigned short dport = (udp[2] << 8) | udp[3];
    if (dport != 26970) return 2;

    // PQC Header
    unsigned char *session_id_ptr = udp + 8;
    if (data + 14 + 20 + 8 + 16 > data_end) return 1; // XDP_DROP

    struct session_key key = {};
    #pragma unroll
    for (int i = 0; i < 16; i++) {
        key.id[i] = session_id_ptr[i];
    }

    struct pqc_session *session = pqc_sessions.lookup(&key);
    if (!session || !session->verified) {
        return 1; // XDP_DROP
    }

    return 2; // XDP_PASS
}
