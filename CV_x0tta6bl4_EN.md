# Curriculum Vitae

## x0tta6bl4 — AI Systems Architect & Agent Orchestrator

**Location:** Crimea, Russia  
**Contact:** @x0tta6bl4_ai (Telegram) · x0tta6bl4.ai@gmail.com  
**Portfolio:** github.com/x0tta6bl4-ai  
**Target role:** AI Systems Architect / Agent Orchestrator / TPM (AI)

---

### Summary

Systems architect specializing in AI agent orchestration. I don't write code — I design architecture, manage AI agents (Claude, GPT-4, Codex) as a development team, and build validation pipelines.

Flagship project: a mesh platform with post-quantum cryptography, eBPF/XDP dataplane, and autonomous self-healing — **1M lines of code, zero lines hand-written**.

---

### Key Case: x0tta6bl4 Mesh Platform

| | |
|---|---|
| **Role** | System Architect, AI Agent Orchestrator |
| **Timeline** | 2025–2026 (18 months, part-time) |
| **Budget** | $0 |
| **AI Tools** | Claude, GPT-4, Codex, Dependabot |

**Architecture:** 11-layer system — from kernel-level eBPF/XDP to Solidity DAO.

**My scope:**
- System architecture design and technology selection
- System prompts and context engineering for AI agents
- LLM-as-a-Judge — automated cross-validation of generated code
- Chaos engineering, system integration, security auditing

**AI agents scope:**
- 1M lines Python + 22K lines Go generated from my specifications
- Algorithm implementation (PQC handshake, Ghost Transport, MAPE-K)
- Unit/integration tests (~340K lines)
- Refactoring and vulnerability remediation

**Results:**
- 1,012,493 lines, 7,636 files, 1,033 commits
- PQC handshake <50ms (ML-KEM-768 + ML-DSA-65, liboqs 0.15)
- eBPF/XDP throughput: 142K PPS TX on Intel i5 + r8169
- Self-healing: MTTD <20s, MTTR ~3min
- 7 Docker containers, 7 systemd services running
- 29/29 ZTCR chaos tests passed, 0 High vulnerabilities
- Dependencies: 342 → 72 (supply chain security)

---

### Technical Stack

| Category | Stack |
|---|---|
| **Architecture** | Distributed systems, Zero Trust, MAPE-K, PBFT |
| **Cryptography** | PQC (ML-KEM/ML-DSA), SPIRE/SPIFFE mTLS, ChaCha20 |
| **Networking** | eBPF/XDP, AF_XDP, WireGuard, Ghost Transport |
| **AI/ML** | PyTorch, GNN, scikit-learn, LLM-as-a-Judge |
| **Infrastructure** | Docker, systemd, Prometheus, GitHub Actions |
| **Languages (project)** | Python 71%, C 20%, Go 1.2%, Shell |

---

### Core Competencies

1. **Code-Focused Prompt Engineering** — structured system prompts that make AI agents generate deterministic, secure, production-grade code
2. **Agentic CI/CD (LLM-as-a-Judge)** — pipelines where one AI model validates and reviews another's output
3. **Heterogeneous System Integration** — assembling kernel-level C, Go binaries, and Python into a single operational stack
4. **Supply Chain Security** — dependency auditing, attack surface minimization

---

### Why Me

I am not a coder. I am an architect who manages an AI-powered development team. My value is in designing arbitrarily complex systems, decomposing them for AI agents, and delivering a working product — without hand-writing a single line. One architect = a team of 5-10 developers in throughput.

---

*All metrics verified via git, Docker, systemd, pytest, and Bandit.*
