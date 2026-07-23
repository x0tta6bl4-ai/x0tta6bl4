# x0tta6bl4 — Open Source Announcement

Copy-paste ready for Reddit, Hacker News, or Telegram.

---

## Reddit (r/selfhosted, r/netsec, r/privacy)

**Title:** x0tta6bl4: Self-healing mesh VPN with post-quantum cryptography (open source)

**Body:**

I built a VPN service that heals itself. When a node goes down, the MAPE-K control loop detects the failure, plans a recovery action, and executes it automatically — no human intervention.

**Key features:**
- **Post-Quantum Cryptography** — ML-KEM-768 + ML-DSA-65 (NIST FIPS 203/204)
- **Self-healing mesh** — Automatic failure detection and recovery
- **eBPF/XDP dataplane** — Kernel-level packet processing
- **Zero-trust** — SPIRE/SPIFFE workload identity
- **Docker ready** — `docker compose up` → working mesh in 60 seconds

**Quick start:**
```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4/quickstart
docker compose up -d
./demo.sh
```

**What you'll see:**
- 2 mesh nodes connected
- PQC handshake established
- Validation passed (16/16 checks)
- HTML report generated

**Links:**
- GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
- Docs: https://github.com/x0tta6bl4-ai/x0tta6bl4/tree/main/docs
- API examples: https://github.com/x0tta6bl4-ai/x0tta6bl4/blob/main/docs/api/QUICKSTART.md

Looking for feedback on the architecture and code quality. Issues and PRs welcome!

---

## Hacker News (Show HN)

**Title:** Show HN: x0tta6bl4 – Self-healing mesh VPN with post-quantum crypto

**Body:**

https://github.com/x0tta6bl4-ai/x0tta6bl4

x0tta6bl4 is a self-healing mesh VPN that uses post-quantum cryptography (ML-KEM-768 + ML-DSA-65). When a node fails, the MAPE-K control loop automatically detects and recovers — no human intervention.

Key technical decisions:
- eBPF/XDP for kernel-level packet filtering
- SPIRE/SPIFFE for zero-trust workload identity
- Prometheus metrics for observability
- Docker Compose for easy deployment

Quick start: `git clone` → `docker compose up` → `./demo.sh`

Built as an independent engineering research project. Would love feedback from the HN community on the architecture.

---

## Telegram (short version)

**x0tta6bl4** — self-healing mesh VPN с постквантовой криптографией.

Когда нода падает, система сама восстанавливается. ML-KEM-768 + ML-DSA-65 (NIST FIPS). eBPF/XDP. Docker ready.

Запуск: `docker compose up -d && ./demo.sh`

GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4

---

## Usage Notes

1. **Reddit:** Post to r/selfhosted first (most relevant). Wait 1 week before posting to r/netsec.
2. **Hacker News:** Post during US business hours (14:00-18:00 UTC) for max visibility.
3. **Telegram:** Share in privacy/VPN channels where you're already active.
4. **Do NOT:** Cold email, spam, or post to unrelated communities.
