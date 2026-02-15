# x0tta6bl4

Self-healing decentralized mesh network with post-quantum cryptography.

## Architecture

- **FastAPI** application at `src/core/app.py` (entry point: `uvicorn src.core.app:app`)
- **MAPE-K** autonomic self-healing loop (`src/self_healing/`, `src/core/mape_k_loop.py`)
- **Mesh networking** via Yggdrasil + Batman-adv (`src/network/`)
- **Post-quantum crypto**: ML-KEM-768, ML-DSA-65, AES-256-GCM (`src/security/`, `src/crypto/`)
- **Zero-trust**: SPIFFE/SPIRE identity, device attestation, ABAC policy (`src/security/spiffe/`)
- **GraphSAGE** anomaly detection with rule-based fallback (`src/ml/`)
- **DAO governance** with quadratic voting (`src/dao/`)
- **Federated learning** with Byzantine fault tolerance (`src/federated_learning/`)

## Key Conventions

- Python 3.10+, FastAPI, pytest
- Test files: `tests/unit/{module}/test_{name}_unit.py`
- Async tests use `@pytest.mark.asyncio`
- Environment variables for config (never hardcode secrets):
  - `X0TTA6BL4_PRODUCTION`, `X0TTA6BL4_SPIFFE`, `ADMIN_TOKEN`
- Mock external deps in tests: DB, network, SPIFFE
- Coverage target: 75%+ per module
- Encryption: AES-256-GCM only (no XOR, no CBC without HMAC)
- Cert validation: `cert.verify_directly_issued_by()` (never name matching)
- Password hashing: bcrypt (never MD5/SHA1)

## Running

```bash
# Tests
python3 -m pytest tests/ -v --tb=short

# App
uvicorn src.core.app:app --host 0.0.0.0 --port 8080

# Coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

## Project Skills

Domain-specific skills are in `skills/`:
- `skills/x0tta6bl4-mesh-orchestrator/` - **Core**: MAPE-K orchestration, DAO voting, PQC rotation, eBPF telemetry
- `skills/deploy-mesh-node/` - Deployment workflow (Docker/K8s/Local)
- `skills/security-audit/` - PQC + Zero-Trust + OWASP audit
- `skills/mape-k-troubleshoot/` - Self-healing diagnostics
- `skills/test-coverage-boost/` - Test coverage improvement

## Slash Commands

- `/mesh-orchestrate` - Full MAPE-K orchestration cycle (Monitor → Analyze → Plan → Execute → Verify)
- `/deploy` - Deploy mesh node to Docker/K8s/Local
- `/security-audit` - Comprehensive security audit
- `/diagnose-healing` - MAPE-K self-healing diagnostics
- `/boost-coverage` - Improve test coverage
