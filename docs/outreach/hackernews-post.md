# HackerNews / Lobste.rs Post Draft

## Title options (pick one)

1. "Show HN: Self-healing VPN with post-quantum crypto and eBPF dataplane"
2. "Show HN: x0tta6bl4 — autonomous mesh VPN that heals itself after failures"
3. "Show HN: Post-quantum ML-KEM-768 + eBPF at 142k PPS in an open-source VPN"

## Post body

```
I built a VPN service that detects and recovers from failures automatically, uses NIST post-quantum cryptography (ML-KEM-768 + ML-DSA-65), and runs packet filtering in eBPF at the kernel level.

Key technical decisions:
- Post-quantum hybrid TLS: ML-KEM-768 for key exchange + ML-DSA-65 for signatures, tested via liboqs. Resistant to "harvest now, decrypt later" attacks.
- eBPF/XDP dataplane: 142k PPS TX on commodity hardware. Bypass userspace entirely for packet filtering.
- MAPE-K self-healing loop: Monitor → Analyze → Plan → Execute → Verify. Detects anomalies, generates signed healing commands (HMAC or JWT-SVID), and verifies recovery.
- Zero-trust identity: SPIRE/SPIFFE mTLS for workload attestation. Each mesh node has a verifiable cryptographic identity.
- Ghost Transport: Anti-censorship VPN with steganographic DNS and decoy SNI for DPI bypass.

All code is open-source under Apache 2.0. The system runs locally via Docker Compose (2 nodes + SPIRE in ~30 seconds).

Current status: pilot-ready. Local stack verified, no production customers yet. Looking for contributors interested in:
- Integration testing (MAPE-K recovery paths)
- Penetration testing (PQC handshake)
- Documentation (API examples)

GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4

AMA about the technical choices.
```

## Notes

- Post on Tuesday-Thursday, 10:00-14:00 UTC for max visibility
- Best subreddits: r/netsec, r/privacy, r/selfhosted, r/programming
- Lobste.rs tags: security, networking, programming
- Don't post on Monday (too much competition)
- Include a GIF of `docker compose up` → working mesh in the comments
