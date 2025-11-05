# x0tta6bl4

Decentralized self‑healing mesh intelligence platform integrating secure identity (SPIFFE/SPIRE), adaptive networking (batman‑adv + eBPF), federated / RAG‑augmented ML, and autonomous MAPE‑K control loops.

> Current Version: **v1.0.0‑restructured**  
> Migration: Completed 7‑phase modernization (see `MIGRATION_PROGRESS.md`, `CHANGELOG.md`).

---
## ✨ Key Features
- **Zero Trust Mesh:** SPIFFE/SPIRE identities, mutual TLS, policy‑driven authorization.
- **Adaptive Networking:** batman‑adv dynamic routing + optional eBPF visibility layer.
- **Intelligent Control Loop:** MAPE‑K autonomic cycle (Monitor, Analyze, Plan, Execute, Knowledge).
- **Hybrid ML Stack:** RAG pipeline (vector + semantic retrieval) + LoRA fine‑tuning adapters.
- **Observability First:** Prometheus metrics + OpenTelemetry tracing hooks.
- **Modular Architecture:** Logical domains in `src/` (core, security, network, ml, monitoring, adapters).
- **Automated Quality:** CI (lint, type, tests, coverage), security scanning, performance benchmarks, release pipeline.
- **AI Development Aids:** Curated prompt library in `docs/COPILOT_PROMPTS.md` to standardize generation.

---
## 🗂 Repository Structure
```
src/
  core/          # Autonomic loop, orchestration primitives
  security/      # Identity, authZ/N, cert/service credentials
  network/       # Mesh routing, eBPF helpers, topology logic
  ml/            # RAG components, model adapters, embedding ops
  monitoring/    # Metrics, tracing, health instrumentation
  adapters/      # External service / protocol adapters

tests/
  unit/          # Fast isolated tests
  integration/   # Cross‑component behavior
  security/      # Threat & fuzz tests
  performance/   # Benchmarks & regression timing

infra/
  terraform/     # Provision foundational cloud / networking
  networking/    # Mesh + overlay plumbing (batman-adv, cilium)
  security/      # SPIFFE/SPIRE deployment, PKI rotation
  k8s/           # Kubernetes manifests (staging/prod overlays)
  docker/        # Container build artifacts
  helm/          # Helm charts (if packaging enabled)

archive/         # Legacy + artifacts (safeguarded, excluded from active context)
```

---
## 🚀 Quick Start
### 1. Clone
```bash
git clone <repo-url>
cd x0tta6bl4
```
### 2. Choose Install Profile
| Profile | Command | Notes |
|---------|---------|-------|
| Core (minimal) | `pip install -e .` | API + security + metrics |
| + ML | `pip install -e ".[ml]"` | Adds PyTorch / Transformers (large) |
| + Dev | `pip install -e ".[dev]"` | Testing & tooling |
| Full stack | `pip install -e ".[ml,dev,monitoring]"` | Everything except experimental |
| Experimental (quantum) | `pip install -e ".[quantum]"` | Optional research layer |

### 3. Run Dev API (placeholder)
```bash
python -m src.core.app
# or
uvicorn src.core.app:app --reload --port 8000
```
Visit: http://localhost:8000/health

---
## 🧪 Testing
```bash
pytest -m unit
pytest -m integration -v
pytest --cov=src --cov-report=term-missing
```
Markers: `unit`, `integration`, `security`, `performance` (see `pytest.ini`).

Coverage gate: ≥75% (CI enforced).

---
## 🔐 Security & Trust
| Aspect | Mechanism |
|--------|-----------|
| Identity | SPIFFE/SPIRE SVID issuance |
| Transport | mTLS (TLS 1.3), cert rotation policy |
| AuthZ | Policy + identity pattern validation |
| Integrity | Hash / signature pipelines (roadmap) |
| Dependency Risk | Weekly Safety + Bandit scans |

Disclosure policy: see `SECURITY.md`.

---
## 📊 Observability
- **Metrics:** Prometheus (request latency, mesh health, loop cycle durations)
- **Tracing:** OpenTelemetry spans for control loop + network adaptation
- **Benchmarks:** Automated regression guard via `benchmarks.yml`

---
## 🧠 AI Assistance
Use `docs/COPILOT_PROMPTS.md` for:
- RAG & embedding logic scaffolds
- mTLS handshake flows
- eBPF telemetry samplers
- LoRA fine‑tuning patterns

Guidelines: Be explicit with constraints (timeouts, error handling, complexity bounds). Always request tests.

---
## 🛠 Development Workflow
1. Branch naming: `feat/<scope>`, `fix/<issue>`, `perf/<area>`, `sec/<surface>`
2. Keep PRs under ~400 lines net diff
3. Include: tests, docs, security considerations section
4. Pass CI (lint, type, tests, coverage) before review
5. Avoid adding large binaries (prefer artifact registry)

Commit style (conventional-ish):
```
feat(network): adaptive TQ scoring heuristic
fix(security): reject expired SVID pre-auth
perf(ml): reuse embedding cache window
```

---
## 📦 Release & Versioning
- Semantic Versioning (MAJOR.MINOR.PATCH)
- Automated release pipeline on `v*.*.*` tags
- Changelog generated & enriched manually (`CHANGELOG.md`)
- Artifacts optionally published (container / PyPI)

---
## 🗺 Roadmap (High Level)
| Area | Near Term | Mid Term |
|------|-----------|----------|
| Networking | Dynamic eBPF congestion probe | Multi-path adaptive routing |
| ML | RAG caching + HNSW tuning | Federated differential privacy |
| Security | Policy engine hardening | Attestation pipeline |
| Observability | Mesh topology dashboard | Anomaly detection loop |
| Governance | DAO vote snapshot tooling | Tokenized adaptive incentives |

Detailed: `ROADMAP.md` (if present) / future addition.

---
## 🤝 Contributing
See `CONTRIBUTING.md` (workflow, style, review expectations). Always run full test suite + static checks locally first.

---
## ⚠️ Large / Archived Data
Heavy legacy materials (CAD, media, historical backups) are isolated under `archive/`. Avoid re‑introducing large binary assets into active modules.

---
## 🧪 Minimal Health Check Example
After install:
```bash
python - <<'PY'
from fastapi.testclient import TestClient
from src.core.app import app
c = TestClient(app)
print(c.get('/health').json())
PY
```
Expected: `{ "status": "ok", "version": "1.0.0" }`

---
## 📬 Contact / Security
Security disclosures: see `SECURITY.md`.  
General issues: open GitHub issue with `area:<domain>` label.  

---
## © License
(Choose appropriate license — TODO placeholder)

---
*This repository is now in stabilized post‑migration state. Incremental feature work should emphasize: small diffs, test coverage growth, and security posture tightening.*
