# x0tta6bl4 — System Architecture Sitemap

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
