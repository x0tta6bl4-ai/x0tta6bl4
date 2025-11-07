# Copilot Instructions for x0tta6bl4

## 🏗️ Architecture Overview
- Modular, domain-driven: see `src/` for core (MAPE-K loop), security (SPIFFE/SPIRE, mTLS), network (batman-adv, eBPF), ML (RAG, LoRA), monitoring (Prometheus, OpenTelemetry), adapters.
- Control flow: MAPE-K autonomic loop orchestrates monitoring, analysis, planning, execution, and knowledge updates.
- Data flows: Secure identity (SPIFFE/SPIRE) → mesh routing (batman-adv/eBPF) → ML augmentation (RAG, LoRA) → metrics/tracing (Prometheus, OpenTelemetry).
- External integration: Terraform, Kubernetes, Docker, Helm for infra; Prometheus/Jaeger for observability.

## ⚡ Developer Workflow
- Install profiles: `pip install -e .`, `pip install -e ".[ml,dev,monitoring]"` (see README.md)
- Run API: `python -m src.core.app` or `uvicorn src.core.app:app --reload --port 8000`
- Test: `pytest -m unit`, `pytest -m integration -v`, `pytest --cov=src --cov-report=term-missing`
- Coverage gate: ≥75% (CI enforced)
- Branch naming: `feat/<scope>`, `fix/<issue>`, `perf/<area>`, `sec/<surface>`
- PRs: ≤400 lines net diff, must include tests/docs/security notes

## 🧠 AI Patterns & Prompts
- Use `docs/COPILOT_PROMPTS.md` for prompt templates: RAG, mTLS, eBPF, LoRA, MAPE-K, Prometheus, OpenTelemetry, integration/security/performance tests.
- Always specify constraints (timeouts, error handling, resource bounds) and request tests.
- Import patterns: `from src.<domain> import <module>` (see COPILOT_PROMPTS.md)
- Use Pydantic for API models, type hints, async/await for non-blocking ops.

## 🔒 Security & Observability
- Identity: SPIFFE/SPIRE SVID issuance, mTLS (TLS 1.3), cert rotation, policy-driven authZ.
- Metrics: Prometheus (latency, health, loop durations), exported on `/metrics` (port 9090).
- Tracing: OpenTelemetry spans, Jaeger/Zipkin export, 10% sampling in prod.
- Security tests: pytest markers (`security`), fuzzing via Hypothesis.

## 📝 Conventions & Exclusions
- Avoid adding large binaries; legacy data in `archive/`.
- Artifacts: container/PyPI optional, release pipeline on `v*.*.*` tags.
- Changelog: manual enrichment in `CHANGELOG.md`.
- Roadmap: see `ROADMAP.md` for feature priorities.

## 🧪 Health Check Example
```bash
python - <<'PY'
from fastapi.testclient import TestClient
from src.core.app import app
c = TestClient(app)
print(c.get('/health').json())
PY
# Expect: { "status": "ok", "version": "1.0.0" }
```

## 📚 Key References
- `README.md`: architecture, workflow, install, test, security, release
- `docs/COPILOT_PROMPTS.md`: prompt templates, import/type/async patterns
- `SECURITY.md`: disclosure, security posture
- `ROADMAP.md`: feature priorities
- `CHANGELOG.md`: migration history
- `CONTRIBUTING.md`: workflow, style, review

---
**For unclear or missing conventions, ask maintainers for clarification.**
