# Reddit Posts

## r/selfhosted

**Title:** "x0tta6bl4 — self-healing VPN mesh with post-quantum crypto (open source)"

```
I've been building a VPN platform that goes beyond "just encrypt traffic." It uses:

- **Post-quantum cryptography** (ML-KEM-768 + ML-DSA-65) — resistant to future quantum computers
- **eBPF/XDP** — packet filtering at kernel level, no userspace overhead
- **Self-healing** — if a node goes down, the system detects, plans, and recovers automatically
- **Zero-trust** — SPIRE/SPIFFE for workload identity, not just IP-based trust

Runs locally with Docker Compose:
```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
docker compose -f deploy/docker-compose/compose.yaml up -d
curl -s http://localhost:9100/health
```

Looking for people who want to test it, break it, or contribute. The self-healing loop (MAPE-K) is the most interesting part — it's inspired by IBM's autonomic computing framework but applied to VPN mesh networking.

GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
```

## r/netsec

**Title:** "Post-quantum VPN mesh with self-healing: ML-KEM-768 + eBPF XDP dataplane"

```
Technical breakdown of x0tta6bl4's security architecture:

**PQC Hybrid TLS:**
- Key exchange: ML-KEM-768 (NIST FIPS 203) + X25519 (classical fallback)
- Signatures: ML-DSA-65 (NIST FIPS 204) + ECDSA
- Tested against liboqs reference implementation

**eBPF/XDP:**
- BPF_MAP_TYPE_PERCPU_ARRAY for per-CPU packet counters
- XDP_TX for forwarded packets, XDP_DROP for blocked traffic
- 142k PPS TX on r8169 NIC (commodity hardware)

**Self-healing (MAPE-K):**
- Monitor: GNN anomaly detection (GraphSAGE, 95% accuracy)
- Analyze: classify anomaly type (node failure, link degradation, etc.)
- Plan: generate signed recovery command (HMAC for dev, JWT-SVID for prod)
- Execute: apply recovery action (reroute, restart, isolate)
- Verify: confirm recovery succeeded

**Zero-trust:**
- SPIRE server + agent for workload attestation
- SVIDSigner for cross-node PBFT consensus on healing commands

Open source, Apache 2.0. Currently pilot-ready, no production traffic.
GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
```

## r/privacy

**Title:** "Self-healing VPN with post-quantum encryption — open source for journalists and activists"

```
I built this for people under surveillance who need infrastructure that can't be easily taken down.

x0tta6bl4 is a VPN mesh that:
- Uses post-quantum crypto (ML-KEM-768) so recorded traffic can't be decrypted by future quantum computers
- Self-heals: if one node goes down, others detect and recover automatically
- Bypasses DPI with steganographic DNS and decoy SNI
- Zero-trust: each node proves its identity cryptographically (SPIFFE/SPIFFE)

The project is specifically designed for sanctioned environments where:
- Cloud providers are unavailable
- Budget is zero
- Infrastructure needs to survive seizures and blocks

Open source under Apache 2.0. Looking for security researchers and privacy advocates to test it.

GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
```
