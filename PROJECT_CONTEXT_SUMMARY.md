# x0tta6bl4 Project - Full Context Overview

## Project Identity
**Project Name:** x0tta6bl4  
**Version:** 3.4.0  
**License:** Apache-2.0  
**Authors:** x0tta6bl4 Team <contact@x0tta6bl4.com>

## Core Concept
x0tta6bl4 is a self-healing mesh-architecture platform featuring:
- Zero-Trust security model
- Post-Quantum Cryptography (PQC) integration
- DAO-governance system with quadratic voting
- CI/CD automation
- ML Extensions including RAG, LoRA, Anomaly Detection, and Smart Decisions

## Technical Stack

### Core Technologies
- **Web Framework:** FastAPI 0.119.1 with Uvicorn 0.38.0
- **Language:** Python 3.10+
- **Data Validation:** Pydantic 2.12.3
- **Security:** bcrypt 5.0.0, PyJWT 2.10.1, cryptography 45.0.3
- **Monitoring:** Prometheus, OpenTelemetry
- **Machine Learning:** PyTorch 2.9.0, scikit-learn 1.7.2, sentence-transformers 5.1.2
- **Cryptography:** liboqs (quantum-resistant algorithms)
- **Networking:** eBPF, Batman-adv mesh, WebSocket transport
- **Storage:** Redis, IPFS, distributed KV stores

### Key Features

#### Security Architecture
- **Post-Quantum Cryptography:** Kyber and Dilithium algorithms via liboqs
- **Zero-Trust:** SPIFFE/SPIRE for workload identity, mTLS communication
- **Self-Protection:** Auto-isolation, Byzantine detection, continuous verification
- **Password Security:** bcrypt hashing (MD5 vulnerability fixed)

#### Self-Healing System
- **MAPE-K Architecture:** Monitor-Analyze-Plan-Execute-Knowledge cycle
- **eBPF Acceleration:** Real-time network monitoring and anomaly detection
- **Adaptive Recovery:** Dynamic MTTR optimization, parallel recovery execution
- **Knowledge Base:** Immutable audit trail, knowledge storage v2

#### Federated Learning
- **Decentralized Training:** Collaborative model training without data sharing
- **Consensus Mechanism:** Raft algorithm for federated learning orchestration
- **Privacy-Preserving:** Secure aggregation, differential privacy
- **GraphSAGE Integration:** Graph neural network for anomaly detection

#### AI/ML Capabilities
- **RAG System:** Retrieval-Augmented Generation with semantic search
- **LoRA:** Lightweight fine-tuning of large language models
- **Anomaly Detection:** Hybrid system combining statistical and ML approaches
- **Causal Analysis:** Graph-based causal inference for root cause analysis

#### Governance
- **DAO System:** Decentralized autonomous organization with quadratic voting
- **Feature Flags:** Dynamic feature management with sandbox testing
- **A/B Testing:** Experimentation framework for feature validation

#### Network Architecture
- **Mesh VPN:** Decentralized mesh network with Batman-adv
- **Traffic Obfuscation:** Domain fronting, faketls, shadowsocks
- **eBPF Optimization:** Dynamic load balancing, traffic shaping
- **PQC Tunnels:** Quantum-resistant VPN tunnels

### Project Structure

#### Source Code Layout
```
src/
├── adapters/          - External system adapters
├── ai/                - AI/ML components
├── cli/               - Command-line interface
├── consensus/         - Raft consensus algorithm
├── core/              - Core application logic
├── data_sync/         - CRDT-based data synchronization
├── enterprise/        - RBAC, multi-tenancy
├── federated_learning - FL orchestration
├── ledger/            - Blockchain ledger
├── ml/                - Machine learning models
├── monitoring/        - Prometheus/OpenTelemetry
├── network/           - eBPF, mesh VPN
├── quantum/           - Quantum computing integration
├── rag/               - Retrieval-Augmented Generation
├── sales/             - Payment integration
├── security/          - PQC, mTLS, SPIFFE
├── self_healing/      - MAPE-K self-healing
├── services/          - Service layer
├── simulation/        - Digital twin simulation
└── storage/           - IPFS, KV stores
```

### Current Status

#### Test Coverage
- **Current Coverage:** 16.39% (36,823 total lines)
- **Goal:** 75% minimum coverage
- **Testing Framework:** pytest with coverage reporting
- **Slow Tests:** Marked with @pytest.mark.slow decorator

#### Key Health Metrics
- **Core App:** 62% coverage
- **Error Handler:** 86% coverage
- **Health Module:** 68% coverage
- **Thread Safe Stats:** 93% coverage

#### Active Development
- **Main Branch:** Currently on version 3.4.0
- **Deployment:** Production-ready with Docker, Kubernetes, and Helm charts
- **CI/CD:** GitLab CI pipeline with deployment automation

### Critical Issues (from Technical Audit)

#### High Priority
1. **Web Security (MD5):** ALREADY FIXED - replaced with bcrypt
2. **Test Coverage:** Currently at 16.4%, needs to reach 75%
3. **Code Duplication:** Removed src/mape_k/ and src/mapek/ directories

#### Medium Priority
4. **Dependency Management:** Production dependencies verification
5. **Prometheus Metrics:** Duplicate timeseries issue in error handler
6. **Alerting System:** AlertManager integration tests failing

### Recent Improvements

#### Security Fixes
- **Password Hashing:** Changed from MD5 to bcrypt (12 rounds)
- **Security Hardening:** Added production hardening checks

#### Test Infrastructure
- **Coverage Configuration:** Updated pytest.ini with --cov-fail-under=75
- **Test Files Added:** tests/unit/self_healing/test_self_healing_manager.py

#### Build System
- **pyproject.toml:** Centralized dependency management with optional dependency groups
- **.coveragerc:** Coverage exclusion patterns for tests and __pycache__

### Future Roadmap

#### Q1 2026
- Achieve 75% test coverage
- Implement password migration from MD5 to bcrypt
- Add integration tests for mesh networking
- Enhance PQC security testing

#### Q2 2026
- Improve ML model performance
- Add support for additional post-quantum algorithms
- Enhance federated learning scalability
- Improve eBPF performance monitoring

### Quick Links
- **API Docs:** `/docs` (Swagger UI)
- **Health Check:** `/health`
- **Metrics:** `/metrics`
- **GitLab:** https://gitlab.com/x0tta6bl4/x0tta6bl4