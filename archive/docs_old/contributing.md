# Contributing to x0tta6bl4

Thank you for investing time into improving the decentralized mesh intelligence platform.
The post‑migration architecture emphasizes clarity, modularity, reliability, and security. Please follow the guidelines below to keep the system consistent and high‑quality.

---
## 🔄 Branch Strategy
| Purpose | Pattern | Example |
|---------|---------|---------|
| Feature | `feat/<scope>` | `feat/rag-cache-layer` |
| Fix | `fix/<scope>` | `fix/mtls-expiry-check` |
| Performance | `perf/<scope>` | `perf/hnsw-batch-ingest` |
| Security | `sec/<surface>` | `sec/jwt-claim-enforce` |
| Refactor | `ref/<area>` | `ref/ml-vector-abstraction` |
| Documentation | `docs/<topic>` | `docs/observability-guide` |
| Chore / Infra | `chore/<item>` | `chore/update-deps-2025w46` |

Avoid working directly on `main`. Keep branches focused; prefer ≤400 net changed lines.

---
## ✅ Pull Request Checklist
Before marking a PR ready for review:
- [ ] Linked issue (or clear context summary in description)
- [ ] Meaningful title (prefixed with Conventional style)
- [ ] Clear motivation + concise design notes
- [ ] Tests added/updated (unit + integration if cross‑module)
- [ ] Coverage does not drop (≥75% gate remains passing)
- [ ] Types clean (`mypy` passes, no new ignores unless justified)
- [ ] Lint passes (`flake8` / style toolchain)
- [ ] Security impact assessed (auth, input validation, identity trust boundaries)
- [ ] Performance implications considered (esp. ML / vector ops)
- [ ] Docs updated (README section / inline docstrings / CHANGELOG if user‑facing)
- [ ] No large binaries or accidental secrets

---
## 🧪 Testing Standards
| Layer | Scope | Location | Notes |
|-------|-------|----------|-------|
| Unit | Pure functions, adapters, fast logic | `tests/unit/` | <100ms each ideal |
| Integration | Cross‑module, network simulation | `tests/integration/` | Use fixtures & ephemeral resources |
| Security | AuthZ bypass, fuzz, malformed inputs | `tests/security/` | Hypothesis, boundary cases |
| Performance | Benchmark critical paths | `tests/performance/` | Guard against regressions |

Run locally:
```bash
pytest -m unit
pytest -m integration -v
pytest --cov=src --cov-report=term-missing
```
Benchmark example:
```bash
pytest tests/performance/ --benchmark-only --benchmark-autosave
```

---
## 🧬 Code Style & Quality
- Python: Follow `pep8` + pragmatic readability (line soft limit ~100 chars)
- Docstrings: Google style or concise single‑line for trivial functions
- Type hints: Required for all public functions/classes
- Error handling: Raise domain‑specific exceptions (define in module `exceptions.py` per domain if complexity grows)
- Logging: Use structured logging (future enhancement) — for now prefer consistent `logger.<level>("context action", extra={...})`

---
## 🔐 Security Expectations
| Topic | Guideline |
|-------|-----------|
| Identity | Always verify SVID / identity claims before trust escalation |
| Input | Validate external input (length, type, normalization) |
| Cryptography | Use libs only (no custom crypto) |
| Secrets | Never commit; rely on runtime secret stores / env |
| Dependencies | Let CI handle vulnerability scans (Safety/Bandit) |
| Authorization | Fail closed; explicit allow rules |

Report vulnerabilities privately (see `SECURITY.md`).

---
## 🧩 Architecture Principles
1. **Separation:** Keep domains isolated (security vs ml vs network).  
2. **Explicitness:** Make cross‑domain boundaries visible (adapters).  
3. **Determinism First:** Optimize clarity; later optimize speed.  
4. **Resilience:** Defensive coding around networking & identity.  
5. **Observability:** Expose metrics + traces near new complexity.  
6. **Extensibility:** Compose via clear interfaces; avoid deep inheritance chains.  

---
## 🧠 AI Assistance Usage
When using AI (Copilot, etc.):
- Seed context with domain file + a prompt from `docs/COPILOT_PROMPTS.md`
- Always request: tests, error handling, type hints, docstring
- Review for security & data handling assumptions

---
## 🗃 Commit Message Format
```
<type>(<scope>): <concise imperative summary>

[optional body explaining rationale / tradeoffs]
[optional footer: Closes #123 / BREAKING CHANGE: ...]
```
Types: feat, fix, perf, refactor, docs, chore, test, build, ci, sec.

Examples:
```
feat(ml): add approximate batch vector normalization
fix(security): enforce SVID lifetime upper bound
perf(network): reduce path recomputation frequency
```

---
## 🔄 Dependency Management
- Add runtime deps to `[project.dependencies]` in `pyproject.toml`.
- Add optional domain deps under proper extras group.
- Do NOT pin overly narrow unless required (security / reproducibility reasons). Use `<major+1` bounds.
- Regenerate lock artifacts (future: if lock added) in isolated environment.

---
## 🧪 Example Local Validation Script
```bash
#!/usr/bin/env bash
set -euo pipefail
pytest -m unit
pytest -m integration -q
flake8 src tests
mypy src
pytest --cov=src --cov-fail-under=75
```

---
## 🛡 Review Philosophy
| Category | Reviewer Focus |
|----------|----------------|
| Correctness | Edge cases, failure modes, invariants |
| Simplicity | Avoid premature abstraction / over‑generalization |
| Security | Identity misuse, unchecked input, secret handling |
| Observability | Metrics/tracing present for complex logic |
| Testing | Negative + boundary path coverage |
| Performance | Hot path changes justified & measured |

---
## 🚨 Breaking Changes
Document in `CHANGELOG.md` with: WHAT changed, WHY, MIGRATION steps.

---
## 🧾 License & CLA
(If project later adopts CLA, document here.)

---
## 🙌 Thanks
Consistent, incremental contributions keep the mesh adaptive, reliable, and auditable. Bring clarity → ship faster.
