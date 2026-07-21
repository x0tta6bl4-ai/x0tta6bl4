#!/usr/bin/env python3
"""
x0tta6bl4 Master Architecture Poster & Diagrams Generator.

Generates:
1. docs/assets/x0tta6bl4_architecture_master.svg (High-resolution 1200x800 SVG Poster)
2. docs/assets/x0tta6bl4_full_architecture.mermaid (Full 11-Layer Mermaid Diagram)
3. docs/architecture/SYSTEM_ARCHITECTURE_MAP.md (Comprehensive sitemap document)

Compliance: Web Application & Graphic Aesthetics Guidelines.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT / "docs" / "assets"
ARCH_DIR = ROOT / "docs" / "architecture"


def generate_master_poster() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ARCH_DIR.mkdir(parents=True, exist_ok=True)

    print("🎨 Generating Master Architecture Assets for x0tta6bl4...")

    # 1. Generate Full Mermaid Diagram
    mermaid_file = ASSETS_DIR / "x0tta6bl4_full_architecture.mermaid"
    mermaid_content = """graph TB
    subgraph L11["Layer 11: Verification & Truth Matrix"]
        VM["VERIFICATION_MATRIX.md<br/>(3-Tier Taxonomy: ✅ VERIFIED / 🟡 LAB / ⚪ TARGET)"]
    end

    subgraph L10["Layer 10: 24/7 Autopilot Daemons"]
        AD["run_self_healing_autopilot_cycle.py"]
        CD["self_healing_code_daemon.py"]
    end

    subgraph L9["Layer 9: User Service & Telegram Interface"]
        TB["Telegram Bot (telegram_bot_simple.py)"]
        DB["SQLite WAL Database (database.py)"]
    end

    subgraph L8["Layer 8: Proxy & Stealth Dataplane"]
        XR["Xray VLESS + Reality (NL VPS 89.125.1.107)"]
        MSK["Relay Node (MSK VPS 84.54.47.103)"]
    end

    subgraph L7["Layer 7: Post-Quantum Messaging (x0tMQ)"]
        XMQ["x0tMQ Protocol (src/swarm/)"]
        FRAME["X0tMQMAPEKFrame (NIST ML-DSA-65 Signed)"]
    end

    subgraph L6["Layer 6: Self-Healing MAPE-K Engine"]
        MON["1. Monitor (MAPEKMonitor)"]
        GNN["2. Analyze (GraphSAGE GNN Anomaly Detector)"]
        PLN["3. Plan (Bio-Evo & DPI Healing Planner)"]
        EXE["4. Execute (MAPEKExecutor)"]
    end

    subgraph L5["Layer 5: Zero-Trust SPIRE Identity"]
        SPIRE["SPIRE Server + Workload API"]
        SVID["SVIDSigner & PQCSVIDRotator"]
    end

    subgraph L4["Layer 4: Post-Quantum Cryptography Core"]
        KEM["ML-KEM-768 (NIST FIPS 203 Key Exchange)"]
        DSA["ML-DSA-65 (NIST FIPS 204 Digital Signature)"]
    end

    subgraph L3["Layer 3: Kernel eBPF/XDP Dataplane"]
        XDP["eBPF/XDP Driver Hook (6.66 ns decision)"]
        RING["AF_XDP Ring Buffers & ebpf_to_x0tmq_bridge.py"]
    end

    subgraph L2["Layer 2: Multi-Region Mesh Topology"]
        P2P["Libp2p / WireGuard P2P Tunnels"]
        PBFT["PBFT Delphi Consensus"]
    end

    subgraph L1["Layer 1: Bare-Metal Hardware & NICs"]
        NIC["Physical 10Gbps NIC / Virtual Interface"]
    end

    TB --> DB
    TB --> XR
    XR <--> MSK
    NIC --> XDP
    XDP --> RING
    RING --> XMQ
    XMQ --> FRAME
    FRAME --> SPIRE
    SPIRE --> SVID
    SVID --> KEM
    KEM --> DSA
    DSA --> MON
    MON --> GNN
    GNN --> PLN
    PLN --> EXE
    EXE --> P2P
    P2P --> PBFT
    AD --> XR
    CD --> VM
"""
    mermaid_file.write_text(mermaid_content, encoding="utf-8")
    print(f"  ✓ Generated: {mermaid_file}")

    # 2. Generate Master SVG Poster
    svg_file = ASSETS_DIR / "x0tta6bl4_architecture_master.svg"
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 850" width="100%" height="100%">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <linearGradient id="accentCyan" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#818cf8"/>
    </linearGradient>
    <linearGradient id="accentGreen" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#4ade80"/>
      <stop offset="100%" stop-color="#22c55e"/>
    </linearGradient>
    <linearGradient id="accentGold" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#f59e0b"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1200" height="850" fill="url(#bgGrad)"/>
  <rect x="15" y="15" width="1170" height="820" rx="16" fill="none" stroke="#1e293b" stroke-width="2"/>

  <!-- Title Header -->
  <text x="600" y="55" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="26" font-weight="bold" text-anchor="middle" letter-spacing="1">
    x0tta6bl4 — MASTER ARCHITECTURE MAP
  </text>
  <text x="600" y="82" fill="#94a3b8" font-family="sans-serif" font-size="14" text-anchor="middle">
    Autonomous Self-Healing Mesh · Post-Quantum Cryptography (NIST ML-KEM / ML-DSA) · eBPF/XDP Kernel Dataplane
  </text>

  <!-- Layer 1: User & Interface -->
  <rect x="50" y="110" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="75" y="140" fill="#38bdf8" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 1: USER SERVICE &amp; TELEGRAM INTERFACE</text>
  <rect x="75" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="230" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">Telegram Bot (telegram_bot_simple.py)</text>
  <rect x="405" y="152" width="310" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="560" y="175" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">SQLite WAL Database (database.py)</text>
  <rect x="735" y="152" width="390" height="36" rx="6" fill="#0f172a" stroke="#38bdf8"/>
  <text x="930" y="175" fill="#38bdf8" font-family="sans-serif" font-size="12" text-anchor="middle">VLESS+Reality Subscriptions (check_bot_user_chains PASS)</text>

  <!-- Layer 2: Transport & Proxy -->
  <rect x="50" y="220" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#818cf8" stroke-width="1.5"/>
  <text x="75" y="250" fill="#818cf8" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 2: STEALTH PROXY &amp; MESH TUNNELS</text>
  <rect x="75" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">NL Gateway (VPS 89.125.1.107 — Xray / SPIRE)</text>
  <rect x="445" y="262" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="285" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">MSK Relay (VPS 84.54.47.103 — Active 40ms)</text>
  <rect x="815" y="262" width="310" height="36" rx="6" fill="#0f172a" stroke="#818cf8"/>
  <text x="970" y="285" fill="#818cf8" font-family="sans-serif" font-size="12" text-anchor="middle">Anti-Censorship RST Detector</text>

  <!-- Layer 3: PQC & SPIRE Identity -->
  <rect x="50" y="330" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#c084fc" stroke-width="1.5"/>
  <text x="75" y="360" fill="#c084fc" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 3: POST-QUANTUM CRYPTO &amp; ZERO-TRUST IDENTITY</text>
  <rect x="75" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">NIST ML-KEM-768 &amp; ML-DSA-65 (liboqs)</text>
  <rect x="445" y="372" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="395" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">SPIRE Workload API &amp; JWT-SVID</text>
  <rect x="815" y="372" width="310" height="36" rx="6" fill="#0f172a" stroke="#c084fc"/>
  <text x="970" y="395" fill="#c084fc" font-family="sans-serif" font-size="12" text-anchor="middle">PQCSVIDRotator (Auto Key Rotation)</text>

  <!-- Layer 4: x0tMQ & eBPF Kernel -->
  <rect x="50" y="440" width="1100" height="90" rx="10" fill="url(#cardGrad)" stroke="#4ade80" stroke-width="1.5"/>
  <text x="75" y="470" fill="#4ade80" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 4: x0tMQ MESSAGING &amp; eBPF/XDP KERNEL DATAPLANE</text>
  <rect x="75" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="250" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">eBPF/XDP Driver Hook (6.66 ns decision, 0 B/op)</text>
  <rect x="445" y="482" width="350" height="36" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="620" y="505" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">x0tMQ PQC Messaging Frame (Magic 0x5830544D)</text>
  <rect x="815" y="482" width="310" height="36" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="970" y="505" fill="#4ade80" font-family="sans-serif" font-size="12" text-anchor="middle">ebpf_to_x0tmq_bridge.py (VERIFIED)</text>

  <!-- Layer 5: MAPE-K Self-Healing Engine -->
  <rect x="50" y="550" width="1100" height="110" rx="10" fill="url(#cardGrad)" stroke="#fbbf24" stroke-width="1.5"/>
  <text x="75" y="580" fill="#fbbf24" font-family="sans-serif" font-size="15" font-weight="bold">LAYER 5: AUTONOMOUS MAPE-K SELF-HEALING ENGINE</text>
  <rect x="75" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="200" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">1. Monitor</text>
  <text x="200" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKMonitor &amp; RingBuffers</text>
  
  <rect x="345" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="470" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">2. Analyze</text>
  <text x="470" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">GraphSAGE GNN Anomaly Detector</text>
  
  <rect x="615" y="595" width="250" height="48" rx="6" fill="#0f172a" stroke="#334155"/>
  <text x="740" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">3. Plan</text>
  <text x="740" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">Bio-Evo &amp; DPI Healing Planner</text>

  <rect x="885" y="595" width="240" height="48" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="1005" y="618" fill="#fbbf24" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">4. Execute</text>
  <text x="1005" y="634" fill="#94a3b8" font-family="sans-serif" font-size="10" text-anchor="middle">MAPEKExecutor (Auto Reroute)</text>

  <!-- Layer 6: Status Taxonomy Footer -->
  <rect x="50" y="675" width="1100" height="135" rx="10" fill="#020617" stroke="#334155" stroke-width="1"/>
  <text x="75" y="705" fill="#f8fafc" font-family="sans-serif" font-size="14" font-weight="bold">SINGLE SOURCE OF TRUTH — 3-TIER STATUS TAXONOMY</text>
  
  <rect x="75" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#4ade80"/>
  <text x="90" y="745" fill="#4ade80" font-family="sans-serif" font-size="13" font-weight="bold">✅ VERIFIED</text>
  <text x="90" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Automated test passing (Exit Code 0 &amp; Artifact)</text>
  <text x="90" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">PQC, eBPF Simulator, x0tMQ Bridge, Rotator</text>

  <rect x="430" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#fbbf24"/>
  <text x="445" y="745" fill="#fbbf24" font-family="sans-serif" font-size="13" font-weight="bold">🟡 VALIDATED IN LAB</text>
  <text x="445" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Tested on integration testbed / NL &amp; MSK VPS</text>
  <text x="445" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">Autonomous Loop, Ghost Bot Chains, SPIRE</text>

  <rect x="785" y="720" width="340" height="70" rx="6" fill="#0f172a" stroke="#94a3b8"/>
  <text x="800" y="745" fill="#94a3b8" font-family="sans-serif" font-size="13" font-weight="bold">⚪ TARGET</text>
  <text x="800" y="765" fill="#94a3b8" font-family="sans-serif" font-size="11">Engineering hypothesis planned for future testing</text>
  <text x="800" y="780" fill="#cbd5e1" font-family="sans-serif" font-size="10">1M+ PPS Physical NIC, 100+ Node Deployment</text>
</svg>
"""
    svg_file.write_text(svg_content, encoding="utf-8")
    print(f"  ✓ Generated: {svg_file}")

    # 3. Generate Architecture Sitemap Document
    doc_file = ARCH_DIR / "SYSTEM_ARCHITECTURE_MAP.md"
    doc_content = """# x0tta6bl4 — System Architecture Sitemap

> 📖 **Single Source of Truth:** See [`VERIFICATION_MATRIX.md`](../verification/VERIFICATION_MATRIX.md) for reproducible proof links across all subsystems.

---

## 🎨 Visual Architecture Poster

![x0tta6bl4 Master Architecture Map](../assets/x0tta6bl4_architecture_master.svg)

---

## 🏛️ Subsystem Map & Proof Links

| Layer | Component | File Path | Status | Verification Proof |
|:---|:---|:---|:---:|:---|
| **L1** | **User Interface (Telegram Bot)** | [`telegram_bot_simple.py`](../../telegram_bot_simple.py) | `🟡 VALIDATED IN LAB` | `python3 services/nl-server/ghost-access/check_bot_user_chains.py` |
| **L1** | **SQLite WAL Database** | [`database.py`](../../database.py) | `🟡 VALIDATED IN LAB` | `check_bot_user_chains.py` |
| **L2** | **Stealth Proxy (VLESS+Reality)** | [`src/services/vpn_config_generator.py`](../../src/services/vpn_config_generator.py) | `✅ VERIFIED` | `pytest tests/unit/server/test_ghost_server_unit.py` |
| **L2** | **Anti-Censorship RST Detector** | [`src/anti_censorship/tspu_rst_detector.py`](../../src/anti_censorship/tspu_rst_detector.py) | `✅ VERIFIED` | `pytest tests/unit/anti_censorship/test_tspu_rst_detector_unit.py` |
| **L3** | **Post-Quantum Crypto (PQC)** | [`src/security/pqc/`](../../src/security/pqc/) | `✅ VERIFIED` | `python3 -c "import src.security.pqc as pqc; print(pqc.is_liboqs_available())"` |
| **L3** | **PQC SVID Certificate Rotator** | [`src/security/pqc_svid_rotator.py`](../../src/security/pqc_svid_rotator.py) | `✅ VERIFIED` | `pytest tests/unit/security/test_pqc_svid_rotator_unit.py` |
| **L4** | **x0tMQ PQC Transport Bridge** | [`src/self_healing/x0tmq_mapek_bridge.py`](../../src/self_healing/x0tmq_mapek_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/self_healing/test_x0tmq_mapek_bridge_unit.py` |
| **L4** | **eBPF to x0tMQ Pipeline** | [`src/network/ebpf/ebpf_to_x0tmq_bridge.py`](../../src/network/ebpf/ebpf_to_x0tmq_bridge.py) | `✅ VERIFIED` | `pytest tests/unit/network/ebpf/test_ebpf_to_x0tmq_bridge_unit.py` |
| **L5** | **GraphSAGE GNN Anomaly Detector** | [`src/ml/graphsage_x0tmq_integrator.py`](../../src/ml/graphsage_x0tmq_integrator.py) | `✅ VERIFIED` | `pytest tests/unit/ml/test_graphsage_x0tmq_integrator_unit.py` |
| **L5** | **MAPE-K Autonomous Loop** | [`src/self_healing/mape_k/manager.py`](../../src/self_healing/mape_k/manager.py) | `🟡 VALIDATED IN LAB` | `pytest tests/test_mapek_ai_contracts_e2e.py` |
"""
    doc_file.write_text(doc_content, encoding="utf-8")
    print(f"  ✓ Generated: {doc_file}")

    print("✅ All Master Architecture Assets generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(generate_master_poster())
