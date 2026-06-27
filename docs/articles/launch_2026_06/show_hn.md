# Show HN: x0tta6bl4 – Honest, Post-Quantum Mesh VPN

Hi HN,

We’re building **x0tta6bl4**, an autonomous, post-quantum mesh network.

A few weeks ago, we faced a hard truth: our internal metrics and performance claims were slipping into "hallucination territory" – simulations were being reported as reality. In a project built on cryptographic trust, this was unacceptable.

We hit the reset button. We purged every unverified claim, introduced an **Honest Mode** readiness gate, and established a **Reality Baseline** on physical hardware (Intel NICs).

**What makes it different:**
- **Post-Quantum Security**: Hybrid TLS 1.3 + ML-KEM (Kyber) rotation is live.
- **eBPF Dataplane**: Kernel-level DPI bypass and traffic obfuscation via XDP.
- **Autonomous Healing**: A MAPE-K loop that detects and repairs mesh anomalies in <20s.
- **No Bullshit Metrics**: Our baseline is 142k PPS. It’s not millions (yet), but it’s real, it’s verified, and it’s running on a physical Intel NIC.

**The Product:**
We’ve launched our first B2C application on this stack: **Quantum Shield VPN**. You can try it via our Telegram bot [@x0tta6bl4_bot](https://t.me/x0tta6bl4_bot).

**Open Source & Verifiable:**
Every claim in our repo is evidence-gated. You can run `python3 scripts/ops/check_real_readiness.py` to verify our current state yourself.

Repo: https://github.com/x0tta6bl4-ai/x0tta6bl4

Would love to hear your thoughts on autonomous networking and PQC deployment in the wild.
