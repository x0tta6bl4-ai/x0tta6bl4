# Demo Video Script: x0tta6bl4 Post-Quantum Mesh

**Duration:** 5-7 minutes
**Audience:** Yandex engineers, DePIN community, grant committees

---

## Scene 1: Title + Problem (30s)

**Screen:** Terminal with title card

```
x0tta6bl4: Post-Quantum Secure Mesh Infrastructure
The First PQC-Ready DePIN Transport Layer
```

**Voiceover:** "Every byte of data on Yandex infrastructure is encrypted with RSA or Elliptic Curve Cryptography. These algorithms will be broken by quantum computers. x0tta6bl4 solves this today."

---

## Scene 2: Live Health Check (30s)

**Command:**
```bash
curl -s http://89.125.1.107:8000/health | python3 -m json.tool
```

**Expected output:**
```json
{
  "status": "ok",
  "version": "3.4.0",
  "uptime_seconds": 86400,
  "pqc_enabled": true,
  "ebpf_active": true,
  "mape_k_loop": "healthy"
}
```

**Voiceover:** "Production instance running v3.4.0 with post-quantum cryptography enabled."

---

## Scene 3: PQC Handshake Demo (60s)

**Command:**
```bash
python3 scripts/ops/run_pqc_demo.py --verbose
```

**Show:**
1. ML-KEM-768 key exchange between two nodes
2. ML-DSA-65 signature verification
3. Hybrid fallback to X25519+ML-KEM
4. Handshake timing: <50ms

**Voiceover:** "Post-quantum key exchange using NIST FIPS 203 ML-KEM-768. The hybrid mode maintains backward compatibility with classical endpoints."

---

## Scene 4: eBPF Throughput (60s)

**Command:**
```bash
# Show eBPF programs loaded
bpftool prog list | grep x0tta6bl4

# Run benchmark
python3 scripts/ops/run_pqc_demo.py --ebpf-benchmark
```

**Show:**
1. eBPF programs attached to NIC (enp8s0)
2. XDP filter active
3. Throughput: 142k TX PPS / 49k RX PPS
4. Latency: <1ms kernel-level processing

**Voiceover:** "eBPF/XDP operates at the kernel level, processing packets before they reach the TCP stack. 142,000 packets per second on a standard Intel NIC."

---

## Scene 5: MAPE-K Self-Healing (90s)

**Command:**
```bash
# Show current node health
python3 -c "
from src.self_healing import MAPEKMonitor
m = MAPEKMonitor()
print(m.status())
"

# Simulate failure
python3 scripts/ops/mttr_chaos_report.py --scenario node_crash

# Show recovery
python3 -c "
from src.self_healing import SelfHealingManager
mgr = SelfHealingManager()
print(f'MTTD: {mgr.last_mttd_ms}ms')
print(f'MTTR: {mgr.last_mttr_seconds}s')
print(f'Recovery plan: {mgr.last_recovery_action}')
"
```

**Show:**
1. Node health monitoring active
2. Simulated failure detected in <20ms
3. Causal analysis identifies root cause
4. Recovery action executed automatically
5. MTTR < 3 minutes

**Voiceover:** "MAPE-K autonomously detects failures in under 20 milliseconds, performs causal analysis using GraphSAGE ML, and executes recovery — no human intervention needed."

---

## Scene 6: Architecture Overview (30s)

**Screen:** ASCII architecture diagram

```
┌─────────────────────────────────────────────┐
│              Control Plane (FastAPI)         │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ PQC TLS │ │ MAPE-K   │ │ DAO Governance│ │
│  │ Engine  │ │ Loop     │ │ (X0T Token)  │ │
│  └────┬────┘ └────┬─────┘ └──────┬───────┘ │
│       │           │              │           │
├───────┴───────────┴──────────────┴───────────┤
│              Data Plane (eBPF/XDP)           │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ │
│  │ XDP Mesh │ │ Ghost Pulse│ │ Bandwidth  │ │
│  │ Filter   │ │ (DPI Bypass│ │ Monitor    │ │
│  └──────────┘ └────────────┘ └────────────┘ │
└─────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │ Yggdrasil│
    │ IPv6 Mesh│
    └─────────┘
```

---

## Scene 7: Call to Action (30s)

**Screen:** GitHub repo + contact info

```
GitHub:  https://github.com/x0tta6bl4-ai/x0tta6bl4
Demo:    http://89.125.1.107:8000/health
License: Apache-2.0
Status:  REAL_READINESS_READY 70/70
```

**Voiceover:** "x0tta6bl4 — the post-quantum transport layer for the DePIN economy. Open source. Production-ready. Quantum-resistant."

---

## Recording Notes

- Use `asciinema` for terminal recordings
- Use `ffmpeg` for final assembly
- Add background music (royalty-free)
- Total recording time: ~15 minutes (edit to 5-7)
- Export: 1080p, H.264, 30fps

## Tools Needed

```bash
# Terminal recording
pip install asciinema

# Record session
asciinema rec demo_cast.agc

# Convert to GIF
agg demo_cast.agc demo.gif --cols 120 --rows 40

# Or convert to MP4
ffmpeg -i demo_cast.agc -c:v libx264 demo.mp4
```
