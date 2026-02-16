# Component Maturity Matrix

This document outlines the maturity level of x0tta6bl4 components to help users understand which features are production-ready and which are experimental.

| Component | Status | Description |
|-----------|--------|-------------|
| **Core Router** | Stable | Mesh network routing with Batman-adv |
| **Zero-Trust Security** | Stable | mTLS + SPIFFE/SPIRE for authentication |
| **Post-Quantum Crypto** | Stable | ML-KEM-768 key exchange + ML-DSA-65 signatures |
| **Mesh Networking** | Beta | Batman-adv + Yggdrasil integration |
| **eBPF Monitoring** | Beta | Kernel-level performance and security monitoring |
| **RAG Pipeline** | Stable | Retrieval-augmented generation for threat detection |
| **LoRA Fine-tuning** | Beta | Lightweight fine-tuning for domain adaptation |
| **Anomaly Detection** | Stable | AI-driven threat detection with GNN |
| **Federated Learning** | Experimental | Distributed training without centralization |
| **DAO Governance** | Experimental | Quadratic voting for decentralized governance |

---

## Maturity Definitions

### Stable
- Component has been tested in production environments
- API is stable and backwards compatible
- SLA guarantees are available
- Security audits completed

### Beta
- Component is feature complete
- Testing in staging environments
- API may change slightly
- Security testing in progress

### Experimental
- Component is under active development
- API may change significantly
- Limited testing
- For evaluation purposes only
