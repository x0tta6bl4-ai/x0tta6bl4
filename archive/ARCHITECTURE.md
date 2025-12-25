# x0tta6bl4 Architecture

## Overview

x0tta6bl4 is a **post-quantum secure, self-healing mesh network** with decentralized governance.

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
│                            ▲                                     │
│     ┌──────────────────────┼──────────────────────┐             │
│     │                      │                      │             │
│   [VPS1]◄──── PQC ────►[VPS2]◄──── PQC ────►[VPS3]             │
│   Exit Node            Relay Node           Exit Node           │
│     ▲                      ▲                      ▲             │
│     │                      │                      │             │
│     └──────────[LOCAL NODE]──────────────────────┘             │
│                Entry Point                                       │
│                    ▲                                             │
│                    │                                             │
│               [USER CLIENT]                                      │
│              SOCKS5 Proxy                                        │
└─────────────────────────────────────────────────────────────────┘
```

## 6-Layer Architecture

### Layer 1: Mesh Network
- **Protocol**: SOCKS5 multi-hop chaining
- **Discovery**: Automatic peer discovery via bootstrap nodes
- **Health**: Latency monitoring every 30 seconds
- **Failover**: Automatic route switching on node failure

### Layer 2: Security (Post-Quantum)
- **Key Exchange**: Kyber768 (NIST FIPS 203, Level 3)
- **Data Encryption**: AES-256-GCM
- **Performance**: 1418x faster than RSA-2048
- **Quantum-Safe**: Protected against quantum computer attacks

### Layer 3: Governance (DAO)
- **Voting**: Quadratic voting (√tokens = votes)
- **Platform**: Snapshot (off-chain) + Aragon (on-chain)
- **Token**: X0T (ERC-20 on Base Sepolia)
- **Treasury**: Multi-sig controlled by DAO

### Layer 4: Data
- **Storage**: Distributed with replication
- **Integrity**: Cryptographic verification
- **Privacy**: No raw data transmission (federated learning ready)

### Layer 5: AI/ML
- **Anomaly Detection**: GraphSAGE GNN (planned)
- **Prediction**: Node failure prediction with 96% recall (planned)
- **Optimization**: Latency-based routing

### Layer 6: Index
- **Search**: Hybrid BM25 + vector embeddings
- **Edge**: LEANN with Product Quantization (40% RAM reduction)

---

## Post-Quantum Cryptography

### Why Kyber768?

| Algorithm | Quantum-Safe | NIST Status | Speed vs RSA |
|-----------|--------------|-------------|--------------|
| RSA-2048 | ❌ No | Deprecated | Baseline |
| ECC P-256 | ❌ No | Deprecated | 10x faster |
| **Kyber768** | ✅ Yes | FIPS 203 (2024) | **1418x faster** |

### Key Sizes

```
Kyber768:
  Public Key:   1184 bytes
  Private Key:  2400 bytes
  Ciphertext:   1088 bytes
  Shared Secret: 32 bytes → AES-256 key
```

### Benchmark Results

```
Operation           Kyber768    RSA-2048    Speedup
─────────────────────────────────────────────────────
Key Generation      0.12ms      376ms       3000x
Encapsulation       0.07ms      0.25ms      3.4x
Decapsulation       0.07ms      2.94ms      41x
─────────────────────────────────────────────────────
TOTAL               0.27ms      380ms       1418x
```

---

## Multi-Hop Routing

### SOCKS5 Chaining

```
Client Request:
  1. Client → Local Node (SOCKS5 handshake)
  2. Local → VPS1 (SOCKS5 + PQC tunnel)
  3. VPS1 → VPS2 (SOCKS5 + PQC tunnel)
  4. VPS2 → Target (direct connection)
  
Response:
  Target → VPS2 → VPS1 → Local → Client
```

### Route Selection

1. **Latency-based**: Prefer nodes with lowest latency
2. **Health-based**: Skip nodes that failed health check
3. **Diversity**: Use geographically distributed paths
4. **Failover**: Automatic switch on connection failure

---

## Token Economics (X0T)

### Earning (Node Operators)

| Activity | Reward |
|----------|--------|
| Relay 1 packet | 0.0001 X0T |
| Epoch reward (hourly) | 10,000 X0T pool |
| Uptime bonus (99%+) | +10% |

### Spending (Users)

| Service | Cost |
|---------|------|
| VPN (1 GB) | 1 X0T |
| Monthly (1 TB) | ~1,000 X0T |

### Deflationary

- 1% burned on every transaction
- Total supply: 1,000,000,000 X0T

---

## Self-Healing Metrics

| Metric | Current | Target H1 | Target H2 | Target H3 |
|--------|---------|-----------|-----------|-----------|
| MTTR | ~20s | 9s | 7.6s | 5s |
| MTTD | ~5s | 2s | 1s | 0.5s |
| Recovery Rate | 90% | 99% | 99.9% | 99.99% |

### MAPE-K Loop

```
Monitor → Analyze → Plan → Execute → Knowledge
   ↑                                    │
   └────────────────────────────────────┘
```

1. **Monitor**: Beacon packets every 500ms
2. **Analyze**: Detect anomalies (latency spike, packet loss)
3. **Plan**: Calculate alternative routes
4. **Execute**: Switch traffic to new route
5. **Knowledge**: Update reputation scores

---

## Deployment

### Quick Start

```bash
# Start local VPN node
./scripts/x0t-cli.sh start

# Test connection
curl -x socks5://127.0.0.1:10809 http://ifconfig.me
```

### Production (Docker)

```bash
docker build -f Dockerfile.vpn -t x0t-node .
docker run -d -p 10809:10809 -e NODE_ID=node-1 x0t-node
```

### Scaling

```bash
# Deploy new node to VPS
./scripts/deploy_node.sh user@vps-ip
```

---

## Security Model

### Threat Model (STRIDE)

| Threat | Mitigation |
|--------|------------|
| **S**poofing | PKI authentication, PQC signatures |
| **T**ampering | AES-256-GCM integrity |
| **R**epudiation | Blockchain audit trail |
| **I**nformation Disclosure | End-to-end encryption |
| **D**enial of Service | Multi-path routing, rate limiting |
| **E**levation of Privilege | DAO governance, multi-sig |

### Zero Trust Principles

1. Never trust, always verify
2. Assume breach
3. Verify explicitly
4. Least privilege access

---

## Roadmap

### Horizon 1 (0-6 months) ✅ Partially Complete
- [x] PQC Kyber768 integration
- [x] Multi-hop mesh routing
- [x] DAO smart contract
- [ ] MTTR < 9 seconds
- [ ] Chaos engineering tests

### Horizon 2 (6-12 months)
- [ ] GraphSAGE anomaly detection
- [ ] Federated Reinforcement Learning
- [ ] SASE integration
- [ ] 100+ nodes

### Horizon 3 (12-24 months)
- [ ] Full PQC infrastructure
- [ ] Autonomous network management
- [ ] Cross-chain DAO federation
- [ ] 6G integration readiness

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
