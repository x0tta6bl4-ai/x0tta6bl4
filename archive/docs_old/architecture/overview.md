# Architecture Overview

x0tta6bl4 is built on four core pillars:

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        x0tta6bl4 Node                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Beacon    │  │  GraphSAGE  │  │    DAO      │             │
│  │   Sync      │  │  Predictor  │  │  Governance │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         └────────────────┼────────────────┘                     │
│                   ┌──────┴──────┐                               │
│                   │   Mesh Core │                               │
│                   └──────┬──────┘                               │
│  ┌─────────────┐  ┌──────┴──────┐  ┌─────────────┐             │
│  │ Post-Quantum│  │   SPIFFE    │  │ Prometheus  │             │
│  │   Crypto    │  │  Identity   │  │   Metrics   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Slot-Based Mesh Sync
- GPS-independent time synchronization
- MTTD: 0.75ms (2541x faster than SOTA)
- Adaptive beacon timing

### 2. Post-Quantum Cryptography
- Hybrid NTRU + ECDSA encryption
- Future-proof against quantum attacks
- Key rotation every 24 hours

### 3. GraphSAGE AI
- INT8 quantized for edge deployment
- 96% recall on anomaly detection
- 3.84ms inference latency

### 4. DAO Governance
- Quadratic voting (√tokens = votes)
- On-chain proposal lifecycle
- 5.88ms voting latency
