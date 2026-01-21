# Continuity Guide – x0tta6bl4 Project

**Last Updated**: January 14, 2026  
**Purpose**: Enable seamless project continuation across work sessions  
**Status**: Phase 4 Planning & Preparation

---

## Quick Status Summary

| Metric | Value | Status |
|--------|-------|--------|
| **Production Readiness** | 85% | ✅ Complete |
| **Test Pass Rate** | 98.5% (258/261) | ✅ Excellent |
| **Code Quality** | PEP 8 Clean, 100% type hints | ✅ High |
| **Current Phase** | P0/P1 Complete, P4 Pending | ⏳ Ready |
| **Last Major Work** | Jan 12-14, 2026 | 📅 Recent |

---

## Key Documentation Files

**Quick Reference**:
- `.zencoder/QUICK_STATUS.txt` – Executive summary (1 page)
- `.zencoder/LATEST_ACHIEVEMENTS.md` – Full P0/P1 details (400+ lines)
- `.zencoder/rules/repo.md` – Technical repository overview
- `.zencoder/technical-debt-analysis.md` – Identified technical debt

**Project Roadmap**:
- `docs/roadmap.md` – Phase breakdown (P0-P3)
- `README.md` – Project overview
- `docs/architecture/` – System design docs
- `docs/security/` – Security implementation guides

**Implementation Guides** (P0/P1 work):
- `docs/P1_OPENTELEMETRY_TRACING_GUIDE.md` – Tracing system
- `docs/P1_MAPE_K_TUNING_GUIDE.md` – Self-learning loop
- `docs/P1_RAG_HNSW_OPTIMIZATION_GUIDE.md` – Vector search optimization
- `docs/PROMETHEUS_METRICS.md` – Metrics reference

---

## Getting Back to Work

### Step 1: Understand Current State (5 minutes)
```bash
# Read quick status
cat .zencoder/QUICK_STATUS.txt

# Check test status
make test  # Should show 258/261 passing

# Verify environment
python -c "import src.core.app; print('✅ Project loads')"
```

### Step 2: Identify What You're Working On (2 minutes)

**If continuing Phase 4 (Hardening)**:
- Focus: Load testing, HA configuration, multi-region strategy
- Key files: `src/core/app.py`, `infra/k8s/`, `tests/performance/`
- Read: `.zencoder/technical-debt-analysis.md` (Performance & Optimization section)

**If fixing bugs**:
- Review failed test output: `pytest tests/ -v --tb=short`
- Check lint/type: `make lint` + `make typecheck`

**If adding features**:
- Verify no conflicts with roadmap
- Reference: `docs/roadmap.md` P2/P3 sections
- Follow patterns: Look at `src/monitoring/`, `src/security/`, `src/rag/`

**If updating docs**:
- Update relevant guide in `docs/`
- Update `.zencoder/LATEST_ACHIEVEMENTS.md` if major work
- Run: `make lint` (docstring validation)

### Step 3: Review Changes & Test (5-10 minutes)

```bash
# Before committing anything:
pytest tests/ -v --tb=short        # Full test suite
make lint                          # Code quality
make typecheck                     # Type checking
make format                        # Auto-format code
```

---

## Critical Files to Know

### Core Application
- **`src/core/app.py`** (1362 lines) – Main FastAPI entry point
- **`src/core/mape_k.py`** – MAPE-K autonomic loop
- **`pyproject.toml`** – Dependencies, test config, build metadata

### Security (P0 Complete)
- **`src/security/spiffe/`** – SPIFFE/SPIRE integration
  - `spire_server_config.py` – SPIRE server setup
  - `mtls/mtls_enforcer.py` – TLS 1.3 enforcement
  - `mtls/svid_verifier.py` – SVID verification
- **`.github/workflows/security-scan.yml`** – Security scanning in CI

### Observability (P1 Complete)
- **`src/monitoring/metrics.py`** (500+ lines) – Prometheus metrics
- **`src/monitoring/opentelemetry_extended.py`** (430+ lines) – Distributed tracing
- **`src/rag/batch_retrieval.py`** + **`semantic_cache.py`** – RAG optimization
- **`src/core/mape_k_*.py`** (3 files) – Self-learning tuning
- **`prometheus/prometheus.yml`** – Metrics scrape config

### Kubernetes (P0 Complete)
- **`infra/k8s/base/`** – Base manifests
- **`infra/k8s/overlays/staging/`** – Staging environment
- **`scripts/setup_k8s_staging.sh`** – K8s setup automation

### Testing
- **`tests/`** (50+ files, 261 tests)
  - `unit/` – Unit tests
  - `integration/` – Integration tests
  - `security/` – Security validation
  - `performance/` – Load testing
  - `chaos/` – Resilience tests

---

## Phase 4 Roadmap (Next Priority)

### Phase 4: Hardening & Production Release (Target: February 2026)

**Week 1: Load Testing**
- Set up 1000+ node mesh simulation
- Measure MAPE-K cycle time under load
- Identify bottlenecks (CPU, memory, latency)
- Update performance baselines
- Files to modify: `tests/performance/`, `benchmarks/`

**Week 2: High Availability**
- Redis clustering (failover, replication)
- PostgreSQL replication (primary/standby)
- Kubernetes pod replicas (multi-zone)
- Database migration strategy
- Files to modify: `docker-compose.yml`, `infra/k8s/`, `src/core/app.py`

**Week 3: Multi-Region Strategy**
- Deployment templates (AWS, GCP, Azure)
- Data replication across regions
- Failover mechanisms
- Cost optimization
- Files to create: `deploy/multi-region/`, `docs/deployment/multi-region.md`

**Week 4: Performance Optimization & Staging**
- Apply learnings from load testing
- Optimize identified bottlenecks
- Full staging smoke tests
- Documentation & runbooks
- Files: Various (determined by load test results)

---

## Common Tasks & Commands

### Running Tests
```bash
# All tests
pytest tests/ -v

# By category
pytest tests/unit -m unit
pytest tests/integration -m integration
pytest tests/security -m security
pytest tests/performance -m performance

# With coverage
pytest tests/ --cov=src --cov-report=html

# Run via Makefile
make test
```

### Code Quality
```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/ --max-line-length=120

# Type check
mypy src/ --ignore-missing-imports

# Combined
make format && make lint
```

### Docker & Compose
```bash
# Start full stack
docker compose -f staging/docker-compose.quick.yml up

# Build image
docker build -t x0tta6bl4:3.3.0 .

# Run tests in Docker
docker compose -f deploy/docker-compose.test.yml up

# Cleanup
docker system prune -a --volumes
```

### Kubernetes
```bash
# Setup staging
make k8s-staging

# Check status
kubectl get pods -n x0tta6bl4

# View logs
kubectl logs -f -n x0tta6bl4 deployment/x0tta6bl4

# Run smoke tests
make k8s-test
```

### SPIRE & Security
```bash
# SPIRE development setup
make spire-dev

# Generate test SVIDs
python scripts/test_spiffe_integration.py

# Security scanning
make security-scan
```

---

## How to Add New Features (Follow Pattern)

### 1. Check Roadmap
```bash
# Review priorities
cat docs/roadmap.md | grep "^| [0-9]"
```

### 2. Look at Similar Code
Example: Adding a new metric collector?
```bash
# Examine existing collectors
grep -r "class.*Collector" src/monitoring/
# Examine tests
ls tests/integration/test_prometheus_*
```

### 3. Write Tests First
```bash
# Create test file
touch tests/integration/test_my_feature.py

# Write test cases
# Run: pytest tests/integration/test_my_feature.py -v
```

### 4. Implement Feature
Follow patterns from similar components (check imports, error handling, logging)

### 5. Verify Quality
```bash
# Format
black tests/integration/test_my_feature.py src/my_feature.py

# Type hints
mypy src/my_feature.py --ignore-missing-imports

# Tests
pytest tests/integration/test_my_feature.py -v

# Coverage
pytest --cov=src.my_feature --cov-report=term
```

### 6. Update Docs
- Add module docstring
- Update relevant guide in `docs/`
- Update `.zencoder/LATEST_ACHIEVEMENTS.md` if major

---

## Troubleshooting Quick Reference

### Tests Failing
```bash
# 1. Get detailed output
pytest tests/failing_test.py -vv --tb=long

# 2. Check if it's a dependency issue
pip install -e ".[all]"

# 3. Check if it's a flaky test
pytest tests/failing_test.py -v -x --count=5

# 4. Check recent changes
git log --oneline -20 src/
```

### Type Errors
```bash
# Run mypy with full output
mypy src/ --show-error-codes --show-error-context

# Fix one module at a time
mypy src/core/app.py
```

### Performance Issues
```bash
# Run with profiler
python -m cProfile -s cumtime -m src.core.app

# Check metrics
curl http://localhost:8080/metrics | head -50

# View Prometheus
# Open http://localhost:9090
```

### Docker Issues
```bash
# Check logs
docker logs x0tta6bl4_api_1

# Rebuild
docker build --no-cache -t x0tta6bl4:3.3.0 .

# Debug shell
docker run -it x0tta6bl4:3.3.0 /bin/bash
```

---

## Code Patterns to Follow

### Error Handling
```python
try:
    result = do_something()
except SpecificError as e:
    logger.error(f"Failed to do something: {e}", extra={"error_code": "E001"})
    raise  # or return default value

logger.info("Success", extra={"duration_ms": elapsed})
```

### Async/Await
```python
async def my_handler(request):
    async with some_resource:
        result = await async_operation()
    return result
```

### Metrics
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency', ['endpoint'])

@REQUEST_LATENCY.time()
async def my_endpoint():
    REQUEST_COUNT.labels(endpoint='/api/v1/endpoint', status='200').inc()
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

logger.info("Event with context", extra={
    "component": "mape_k",
    "phase": "monitor",
    "metrics_count": 150
})
```

---

## Session Checklist

When starting a new session:

- [ ] Read `.zencoder/QUICK_STATUS.txt` (2 min)
- [ ] Run `make test` to verify baseline (5 min)
- [ ] Check `git status` for uncommitted changes
- [ ] Read relevant docs for what you're working on
- [ ] Create TODOs if tackling multi-step task
- [ ] Work in focused sessions (1-2 hours max per item)
- [ ] Run full quality check before committing: `make lint && make test`

After work session:

- [ ] All tests passing (`make test`)
- [ ] Code formatted (`make format`)
- [ ] No type errors (`make typecheck`)
- [ ] Updated docs if major changes
- [ ] Updated `.zencoder/LATEST_ACHIEVEMENTS.md` for significant work
- [ ] Commit with clear message including phase/item reference

---

## Key Contacts & Resources

**Project Structure**: Multi-repo mono-repo (40+ Python modules, 2 Solidity contracts)  
**Deployment**: Docker, Kubernetes (K3s/minikube), Cloud-ready  
**Observability Stack**: Prometheus, Grafana, Jaeger/Tempo, OpenTelemetry  
**Security**: SPIFFE/SPIRE, mTLS TLS 1.3, Zero-Trust, Post-Quantum Crypto  
**Testing**: pytest (261+ tests), ~85% code coverage  

**For Questions**:
- Architecture: `docs/architecture/`
- Security: `docs/security/` + `docs/SECURITY.md`
- Deployment: `docs/deployment/` + `scripts/`
- API: `docs/api/` (auto-generated from FastAPI docstrings)

---

## Version Information (Current State)

- **Python**: 3.10+ (3.11 prod, 3.12 mesh nodes)
- **Project**: v3.3.0 (Python) + v1.0.0 (Smart Contracts)
- **Key Dependencies**:
  - FastAPI 0.119.1, Pydantic 2.12.3
  - PyTorch 2.9.0, Transformers 4.57.1
  - LibOQS 0.10.0 (post-quantum crypto)
  - OpenZeppelin 5.0.0 (smart contracts)
- **Last Updated**: January 14, 2026

---

## Next Session Preparation

### If You're Continuing Phase 4 Work:

1. **Load Testing** (Priority 1):
   - Goal: Simulate 1000+ node mesh
   - Files: `tests/performance/`, `benchmarks/`
   - Read: `.zencoder/technical-debt-analysis.md` section 1.1-1.3
   - Time: 2-3 hours initial setup

2. **High Availability** (Priority 2):
   - Goal: Redis + PostgreSQL clustering
   - Files: `docker-compose.yml`, `infra/k8s/`, `src/core/app.py`
   - Read: `docs/deployment/` existing patterns
   - Time: 3-4 hours per component

3. **Performance Optimization** (Based on load test results):
   - Apply discovered bottlenecks
   - Update baselines in `benchmarks/`
   - Document in new `docs/performance-optimization.md`

### If You're Fixing Issues:

1. Review failed tests: `pytest tests/ -v --tb=short`
2. Identify root cause (code, config, environment)
3. Write/update test case
4. Fix implementation
5. Full test suite: `pytest tests/ -v`

---

## Conclusion

**x0tta6bl4 is at 85% production readiness** with:
- ✅ P0 Security & Infrastructure complete
- ✅ P1 Observability complete
- ✅ 261+ tests at 98.5% pass rate
- ✅ Clean codebase (PEP 8, full type hints)
- ⏳ Phase 4 Hardening ready to begin

**Continue with confidence**. The foundation is solid. Focus Phase 4 on load testing to validate architecture under production scale.
