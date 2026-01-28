# Copilot Instructions for x0tta6bl4

## 🏗️ Architecture Overview
- Modular, domain-driven: see `src/` for core (MAPE-K loop), security (SPIFFE/SPIRE, mTLS), network (batman-adv, eBPF), ML (RAG, LoRA), monitoring (Prometheus, OpenTelemetry), adapters.
- Control flow: MAPE-K autonomic loop orchestrates monitoring, analysis, planning, execution, and knowledge updates.
- Data flows: Secure identity (SPIFFE/SPIRE) → mesh routing (batman-adv/eBPF) → ML augmentation (RAG, LoRA) → metrics/tracing (Prometheus, OpenTelemetry).
- External integration: Terraform, Kubernetes, Docker, Helm for infra; Prometheus/Jaeger for observability.

## ⚡ Developer Workflow
- Install profiles: `pip install -e .`, `pip install -e ".[ml,dev,monitoring]"` (see pyproject.toml), or `make install`
- Run API: `python -m src.core.app` or `uvicorn src.core.app:app --reload --port 8000`
- Test: `pytest tests/ -v`, `pytest -m unit`, `pytest -m integration -v`, `make test`, `make test-coverage` (coverage ≥75% enforced)
- Lint/format: `make lint`, `make format` (flake8, black, mypy)
- Benchmark: `make benchmark`
- Clean: `make clean`
- Coverage gate: ≥75% (CI enforced)
- Branch naming: `feat/<scope>`, `fix/<issue>`, `perf/<area>`, `sec/<surface>`
- PRs: ≤400 lines net diff, must include tests/docs/security notes

## 🧠 AI Patterns & Prompts
- Prompt templates for RAG, mTLS, eBPF, LoRA, MAPE-K, Prometheus, OpenTelemetry, integration/security/performance tests (see codebase examples in src/self_healing/, src/monitoring/, src/security/)
- Always specify constraints (timeouts, error handling, resource bounds) and request tests.
- Import patterns: `from src.<domain> import <module>` (e.g., `from src.self_healing import mape_k`)
- Use Pydantic for API models (BaseModel, Field), type hints, async/await for non-blocking ops.
- Use FastAPI for APIs, asyncio for concurrency, logging with structlog.

## 🔒 Security & Observability
- Identity: SPIFFE/SPIRE SVID issuance, mTLS (TLS 1.3), cert rotation, policy-driven authZ.
- Metrics: Prometheus (latency, health, loop durations), exported on `/metrics` (port 9090).
- Tracing: OpenTelemetry spans, Jaeger/Zipkin export, 10% sampling in prod.
- Security tests: pytest markers (`security`), fuzzing via Hypothesis.
- PQC: ML-KEM-768 (key exchange), ML-DSA-65 (signatures), liboqs-python required in production.

## 📝 Conventions & Exclusions
- Avoid adding large binaries; legacy data in `archive/`.
- Build: pyproject.toml, Makefile for tasks.
- Artifacts: container/PyPI optional, release pipeline on `v*.*.*` tags.
- Changelog: manual enrichment in `CHANGELOG.md`.
- Roadmap: see `docs/roadmap.md` for feature priorities.

## 🧪 Health Check Example
```bash
python - <<'PY'
from fastapi.testclient import TestClient
from src.core.app import app
c = TestClient(app)
print(c.get('/health').json())
PY
# Expect: { "status": "ok", "version": "3.1.0" }
```

## 📚 Key References
- `docs/README.md`: architecture, workflow, install, test, security, release
- `SECURITY.md`: disclosure, security posture
- `docs/roadmap.md`: feature priorities
- `CHANGELOG.md`: migration history
- `CONTRIBUTING.md`: workflow, style, review

## 🧠 Мета-когнитивный подход

**КРИТИЧНО:** Применяй мета-когнитивный подход к каждой задаче.

### Перед решением задачи:

1. **СОСТАВИТЬ КАРТУ ПРОСТРАНСТВА РЕШЕНИЙ**
   - Какие подходы могут решить эту задачу?
   - Какие подходы я видел неудачными раньше?
   - Какова вероятность успеха каждого подхода?

2. **СПЛАНИРОВАТЬ ПУТЬ РАССУЖДЕНИЯ**
   - Что мне нужно выяснить в первую очередь?
   - Каких тупиков следует избегать?
   - Какие контрольные точки покажут, что я на правильном пути?

3. **ВЫПОЛНЯТЬ С ОСОЗНАНИЕМ**
   - Попробуйте разные подходы. Задокументируйте, почему.
   - Если застряли, явно вернитесь назад. Отметьте, что не сработало.
   - Когда произойдет прорыв, отметьте поворотный момент.

4. **МЕТА-АНАЛИЗ**
   - Какой алгоритм рассуждений сработал?
   - Почему неудачные подходы потерпели неудачу?
   - Что бы я сделал по-другому в следующий раз?

### Структура ответа:

```
ПРОСТРАНСТВО РЕШЕНИЙ: [отображенные подходы]
ВЫБРАННЫЙ ПУТЬ: [с обоснованием]
ЖУРНАЛ ВЫПОЛНЕНИЯ: [включая тупики]
ОТВЕТ: [окончательное решение]
МЕТА-АНАЛИТИКА: [что это показало о рассуждениях]
```

**Детальная документация:** `META_COGNITIVE_INSTRUCTIONS.md`, `МЕТА_КОГНИТИВНЫЙ_x0tta6bl4_ИНТЕГРАЦИЯ.md`

---
**For unclear or missing conventions, ask maintainers for clarification.**
