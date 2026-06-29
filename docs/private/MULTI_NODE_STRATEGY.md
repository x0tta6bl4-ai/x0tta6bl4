# 🗺️ x0tta6bl4 Multi-Node Strategy (Saturday Deployment)

**Goal:** Expand the x0tta6bl4 Quantum Shield VPN from a single-node setup to a 3-node distributed mesh network.

## 🏗️ Node Architecture

| Node ID | Location | Role | Resources | Planned IP |
|---------|----------|------|-----------|------------|
| `ghost-nl-01` | Netherlands (NL) | **Master/Orchestrator** + Gateway | Current NL Server | `89.125.1.107` |
| `ghost-ru-01` | Russia (RU-MSK) | **Entry Node** (Low Latency for CIS) | 1 CPU, 1GB RAM | `TBD (Sat)` |
| `ghost-us-01` | USA / Singapore | **Exit Node** (Geoblocking bypass) | 1 CPU, 0.5GB RAM | `TBD (Sat)` |

---

## 🔗 Connection Topology

```
User → Ghost Pulse → RU (entry) → Yggdrasil → NL (master) → Yggdrasil → US (exit) → Internet
```

1. **Transport**: `GhostPulseTransport` (ChaCha20-Poly1305 + Timing Obfuscation)
2. **Encryption**: Hybrid PQC (X25519 + ML-KEM-768) + ML-DSA-65 authentication
3. **Routing**: Yggdrasil (IPv6 over UDP) for internal mesh communication
4. **Acceleration**: eBPF/XDP on all nodes
5. **Discovery**: mDNS/DNS-SD + UDP multicast for automatic peer discovery
6. **Self-Healing**: MAPE-K loop with GraphSAGE hybrid anomaly detection

---

## 🛠️ Saturday Deployment Checklist

### Phase 1: Provisioning (Saturday 10:00 - 11:00)
- [ ] Purchase 2 VPS on ProfitServer (Moscow + USA/SG)
- [ ] Install **Ubuntu 24.04 LTS** on both
- [ ] Add SSH keys and tighten security (UFW, Fail2Ban)
- [ ] Record IPs in `scripts/deploy_multi_node.sh` (ENTRY_IP, EXIT_IP)

### Phase 2: Core Installation (Saturday 11:00 - 12:00)
- [ ] Run `scripts/deploy_multi_node.sh entry $MASTER_IP` on RU node
- [ ] Run `scripts/deploy_multi_node.sh exit $MASTER_IP` on US node
- [ ] Verify: `systemctl status x0tta-ghost-vpn yggdrasil x0t-agent`
- [ ] Exchange PQC keys: `scripts/exchange_pqc_keys.sh`

### Phase 3: Mesh Integration (Saturday 12:00 - 13:00)
- [ ] Verify Yggdrasil: `yggdrasilctl getSelf` on all nodes
- [ ] Test connectivity: `yggdrasilctl ping <ipv6>` between nodes
- [ ] Configure `iptables` for multi-hop routing
- [ ] Run `make mesh-health` from control plane

### Phase 4: Monitoring & UI (Saturday 13:00 - 14:00)
- [ ] Update `monitoring/prometheus-mesh.yml` with real IPs
- [ ] Start Prometheus + Grafana on NL
- [ ] Update `keyboards.py` with location selection menu
- [ ] Update `vpn_config_generator.py` for multi-node configs
- [ ] Launch "Location Selection" for all active users

---

## 📦 Deployment Package (Ready)

| File | Purpose | Status |
|------|---------|--------|
| `scripts/deploy_multi_node.sh` | Full node onboarding script | ✅ Ready |
| `scripts/exchange_pqc_keys.sh` | PQC key exchange trigger | ✅ Ready |
| `Dockerfile.ghost-vpn` | VPN server Docker image | ✅ Ready |
| `infra/systemd/x0tta-ghost-vpn.service` | VPN systemd service | ✅ Ready |
| `infra/systemd/x0tta-ghost-watchdog.service` | VPN watchdog | ✅ Ready |
| `monitoring/prometheus-mesh.yml` | Prometheus 3-node config | ✅ Ready |
| `Makefile` mesh targets | `mesh-build`, `mesh-deploy-*`, `mesh-health` | ✅ Ready |

---

## 🛡️ Reliability & Self-Healing

- **MAPE-K Master**: `ghost-nl-01` monitors health of RU and US
- **Failover**: If RU goes down, Bot automatically switches user to NL direct connection
- **DPI Defense**: Each node uses a different `PULSE_SEED` to vary traffic patterns
- **mDNS Discovery**: Nodes automatically find each other on local network
- **Health Monitoring**: 30s unhealthy → 120s auto-remove stale peers
- **Conflict Resolution**: Duplicate peers from multiple sources resolved automatically

---

## 🔐 Security Stack

- **PQC**: ML-KEM-768 (key exchange) + ML-DSA-65 (authentication)
- **TLS**: Hybrid TLS 1.3 + PQC
- **Zero Trust**: SPIFFE/SPIRE identity verification
- **eBPF**: Kernel-level packet filtering and DPI bypass
- **VPN**: ChaCha20-Poly1305 + timing obfuscation

---

## 📊 What Changed Today (2026-06-20)

All core components implemented and tested:

| Component | Commit | Tests |
|-----------|--------|-------|
| PQC handshake + ML-DSA-65 auth | `9847166df` | 15/15 |
| SPIFFE JWT-SVID integration | `1c44440ec` | 13/13 |
| eBPF PQC datapath | `cb984643a` | 14/14 |
| GraphSAGE hybrid detection | `415bfb4bf` | 14/14 |
| Mesh dashboard | `25648dd33` | 16/16 |
| mDNS discovery + conflict resolution | `426035e55` + `0cd1a0ab0` | 19/19 |
| Prometheus metrics | `b39618ae6` | 15/15 |
| **Total** | **9 commits** | **All PASS** |
