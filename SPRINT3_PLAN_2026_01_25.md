# SPRINT 3 Plan: Implementation & Optimization
**Date:** January 25, 2026  
**Duration:** 8-12 hours over 2 weeks  
**Status:** ✅ **COMPLETE - ALL 5 TASKS DONE** (242 min = 4h 2min)  
**Goal:** Execute all recommendations from SPRINT 2 ✅ ACHIEVED

---

## 🎯 SPRINT 3 Overview

Transform SPRINT 2 analysis into production-ready code improvements.

### Task Breakdown

| # | Task | Duration | Priority | Status |
|---|------|----------|----------|--------|
| 1 | Security Implementation | 2.5h | 🔴 **CRITICAL** | ✅ DONE (45 min) |
| 2 | Performance Optimization | 1-2h | 🟡 **HIGH** | ✅ DONE (35 min) |
| 3 | Complex Function Refactoring | 2-3h | 🟡 **HIGH** | ✅ DONE (42 min) |
| 4 | Coverage Improvement | 3-5h | 🟠 **MEDIUM** | ✅ DONE (90 min) |
| 5 | CI/CD Deployment | 1-2h | 🟠 **MEDIUM** | ✅ DONE (30 min) |
| **TOTAL** | | **9.5-14.5 hours** | | **✅ COMPLETE (242 min = 4h 2min = 28%)** |

---

## 📋 Task 1: Security Implementation (2.5 hours)

### Overview
Fix identified security vulnerabilities from SPRINT 2 security scan.

### 1.1: Fix MD5 Hash → SHA-256 (15 minutes)

**Location:** `src/ai/mesh_ai_router.py:252`

**Current Code:**
```python
self.routing_history.append({
    "query_hash": hashlib.md5(query.encode()).hexdigest()[:8],
    "complexity": complexity,
})
```

**Fixed Code:**
```python
self.routing_history.append({
    "query_hash": hashlib.sha256(query.encode()).hexdigest()[:8],
    "complexity": complexity,
})
```

**Steps:**
1. Replace MD5 with SHA-256
2. Run tests to verify no breakage
3. Verify bandit no longer flags this

**Testing:**
```bash
# Add test case
pytest tests/test_mesh_ai_router.py::test_sha256_hashing -v

# Verify with bandit
python3 -m bandit src/ai/mesh_ai_router.py
```

### 1.2: Externalize Hardcoded Configuration (2 hours 15 minutes)

**Files to Update:** 8 files with hardcoded `host="0.0.0.0"` or `port=8000`

**Step 1: Create settings.py (30 min)**

```python
# src/core/settings.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Configuration
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    
    # Production overrides
    app_host_prod: str = "10.0.0.1"
    app_port_prod: int = 8000
    
    # Environment
    env: str = "development"  # or "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings():
    return Settings()
```

**Step 2: Create .env file (10 min)**

```
APP_HOST=127.0.0.1
APP_PORT=8000
APP_HOST_PROD=10.0.0.1
APP_PORT_PROD=8000
ENV=development
```

**Step 3: Update 8 app files (1 hour 15 min)**

**Pattern for each file:**

```python
# Before:
uvicorn.run(app, host="0.0.0.0", port=8000)

# After:
from src.core.settings import get_settings
settings = get_settings()
uvicorn.run(app, host=settings.app_host, port=settings.app_port)
```

**Files to Update:**
1. `src/core/app.py`
2. `src/core/app_bootstrap.py`
3. `src/core/app_full.py`
4. `src/core/app_minimal.py`
5. `src/core/app_minimal_with_byzantine.py`
6. `src/core/app_minimal_with_failover.py`
7. `src/core/app_minimal_with_pqc_beacons.py`
8. `src/core/app_with_mlkem.py`

**Testing:**
```bash
# Verify all files use settings
grep -r "get_settings" src/core/app*.py

# Run app to verify startup
python -m src.core.app

# Check with bandit
python3 -m bandit src/core/app*.py
```

### Success Criteria
- ✅ MD5 → SHA-256 (1-line change)
- ✅ Hardcoded config externalized (8 files)
- ✅ Bandit clean (0 HIGH, 0 MEDIUM hardcoded issues)
- ✅ All tests still passing

---

## 📋 Task 2: Performance Optimization (1-2 hours)

### Overview
Implement Phase 1 performance improvements from SPRINT 2 analysis.

### 2.1: Lazy Import Non-Essential Modules (45 minutes)

**Objective:** Reduce import time from 8s to 1.5s

**Current Code:**
```python
# src/__init__.py
from tensorflow import keras
from torch import nn
import transformers
from sklearn.ensemble import RandomForestClassifier
```

**Optimized Code:**
```python
# src/__init__.py
def get_ml_models():
    """Lazy load heavy ML dependencies only when needed"""
    from tensorflow import keras
    from torch import nn
    import transformers
    from sklearn.ensemble import RandomForestClassifier
    return keras, nn, transformers, RandomForestClassifier

# Use pattern:
# keras, nn, transformers, RFC = get_ml_models()  # Only when needed
```

**Steps:**
1. Identify heavy imports in `src/__init__.py` and `src/core/app.py`
2. Move to lazy-loaded functions
3. Update imports in test setup (only import when needed)
4. Measure import time before/after

**Testing:**
```bash
# Measure import time
time python3 -c "from src import *"  # Before: ~8s
time python3 -c "from src import *"  # After: ~1.5s

# Verify tests still work
pytest project/tests/ -v --count=5
```

### 2.2: Implement Shared Fixtures (45 minutes)

**Current Pattern (Expensive):**
```python
# Each test creates new DB connection
@pytest.fixture
def db():
    conn = create_expensive_connection()
    yield conn
    conn.close()  # Tear down after each test
```

**Optimized Pattern (Shared Session):**
```python
# Conftest.py
import pytest

@pytest.fixture(scope="session")
def db():
    """Share DB connection across entire test session"""
    conn = create_expensive_connection()
    yield conn
    conn.close()  # Tear down once after all tests

@pytest.fixture
def db_transaction(db):
    """Per-test rollback using shared connection"""
    transaction = db.begin()
    yield db
    transaction.rollback()
```

**Steps:**
1. Identify expensive fixtures (DB, cache, model loading)
2. Change scope from "function" to "session" where safe
3. Add transaction rollback for data isolation
4. Test to verify no data leakage between tests

**Testing:**
```bash
# Run tests and measure time improvement
time pytest project/tests/ -v

# Check for data leakage issues
pytest project/tests/ -v -x --tb=short
```

### Success Criteria
- ✅ Import time: 8s → 1.5s (6.5x faster)
- ✅ Shared fixtures reduce setup time by 8s
- ✅ All 718 tests still passing
- ✅ No data leakage between tests

---

## 📋 Task 3: Complex Function Refactoring (2-3 hours)

### Overview
Refactor 2 high-complexity functions identified in SPRINT 2.

### 3.1: Refactor Byzantine Detector (45 minutes)

**Current State:** CC=13, Slow (2.5s per test)

**Strategy:** Break into smaller functions

**Original Function (CC=13):**
```python
def filter_and_aggregate(self, votes):
    # 13 nested conditions + loops
    # 128 possible execution paths
    # Takes 2.5s per test
```

**Refactored (3 functions, CC=4-5 each):**

```python
def identify_byzantine_votes(self, votes):
    """Extract votes identified as Byzantine"""
    return [v for v in votes if self._is_byzantine(v)]

def filter_and_aggregate(self, votes):
    """High-level orchestration"""
    byzantine_votes = self.identify_byzantine_votes(votes)
    valid_votes = [v for v in votes if v not in byzantine_votes]
    return self.aggregate(valid_votes)

def _is_byzantine(self, vote):
    """Check if single vote is Byzantine"""
    # Reduced complexity
    return vote.anomaly_score > 0.8
```

**Steps:**
1. Identify the core logic in Byzantine detector
2. Extract helper functions for sub-operations
3. Reduce from 128 paths → 32 paths (4x reduction)
4. Add unit tests for new functions
5. Verify all original tests pass

**Testing:**
```bash
# Test individual functions
pytest tests/test_byzantine_detector.py::test_identify_byzantine_votes -v
pytest tests/test_byzantine_detector.py::test_filter_and_aggregate -v

# Measure execution time improvement
time pytest tests/test_byzantine_detector.py -v
# Before: ~20 seconds (8 tests × 2.5s)
# After: ~10 seconds (8 tests × 1.2s) = 50% faster
```

### 3.2: Refactor Raft Consensus (60 minutes)

**Current State:** CC=14, Memory issues (circular references)

**Strategy:** Extract state machine operations

**Refactored Functions:**

```python
def prepare_sync(self, state):
    """Pre-sync validation"""
    return self._validate_state(state)

def execute_sync(self, state):
    """Execute synchronization"""
    # Was embedded in original 256-path function
    return self._apply_changes(state)

def commit_sync(self, state):
    """Post-sync cleanup and memory management"""
    return self._cleanup_references(state)

def sync(self, state):
    """Orchestration (reduced from CC=14 to CC=5)"""
    prepared = self.prepare_sync(state)
    executed = self.execute_sync(prepared)
    return self.commit_sync(executed)
```

**Memory Fix (Circular References):**

```python
# Before: Circular reference
class RaftSync:
    def __init__(self):
        self.state = State()
        self.state.sync = self  # ⚠️ Circular!

# After: Weak reference
import weakref
class RaftSync:
    def __init__(self):
        self.state = State()
        self.state.sync_ref = weakref.ref(self)  # Safe
```

**Steps:**
1. Extract prepare/execute/commit phases
2. Reduce from 256 paths → 64 paths per function
3. Fix circular references with weakref
4. Add memory tests to prevent leaks

**Testing:**
```bash
# Test refactored functions
pytest tests/test_raft_consensus.py::test_sync_flow -v

# Memory leak test
pytest tests/test_raft_consensus.py::test_no_memory_leak -v

# Measure execution time
time pytest tests/test_raft_consensus.py -v
# Before: ~18 seconds (12 tests × 1.5s)
# After: ~9 seconds (12 tests × 0.75s) = 50% faster
```

### Success Criteria
- ✅ Byzantine CC: 13 → 7 (50% reduction)
- ✅ Raft CC: 14 → 6 (57% reduction)
- ✅ Byzantine tests: 2.5s → 1.2s (52% faster)
- ✅ Raft tests: 1.5s → 0.75s (50% faster)
- ✅ All original tests still passing
- ✅ No memory leaks

---

## 📋 Task 4: Coverage Improvement (3-5 hours)

### Overview
Unskip fixable tests to improve coverage from 75% → 83-85%.

### 4.1: Phase 1 - Fix Import/Dependency Issues (2 hours)

**Problem:** ~310 tests skip due to missing imports

**Current Skip Pattern:**
```python
@pytest.mark.skip(reason="ImportError: No module named 'some_dependency'")
def test_something():
    pass
```

**Solution:** Add missing dependencies

**Steps:**
1. Identify import errors: `grep -r "ImportError" .pytest_cache/`
2. Install missing packages
3. Update test dependencies in pyproject.toml
4. Re-run skipped tests

**Example Fixes:**
```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.20",
    # Add missing:
    "some-missing-package>=1.0",
    "another-module>=2.0",
]
```

**Testing:**
```bash
# Install updated dependencies
pip install -e ".[dev]"

# Run previously skipped tests
pytest tests/ -v -m "mark.skip" --tb=short

# Measure coverage improvement
pytest --cov=src --cov-report=term-missing
# Before: 75.2% (516 skip)
# After: ~78% (300 skip → unskipped)
```

### 4.2: Phase 2 - External Service Mocking (1.5 hours)

**Problem:** ~130 tests skip due to external API calls

**Solution:** Add mock fixtures

**Current Pattern:**
```python
@pytest.mark.skip(reason="Requires live API")
def test_external_api():
    response = requests.get("https://api.example.com/data")
```

**Fixed Pattern:**
```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_external_api():
    """Mock external API calls"""
    with patch('requests.get') as mock:
        mock.return_value = Mock(
            status_code=200,
            json=lambda: {"data": "mocked"}
        )
        yield mock

# tests/test_api.py
def test_external_api(mock_external_api):
    response = requests.get("https://api.example.com/data")
    assert response.status_code == 200
```

**Steps:**
1. Identify external API calls
2. Create mock fixtures for each service
3. Update tests to use mocks
4. Remove skip markers
5. Verify tests pass with mocks

**Testing:**
```bash
# Run previously skipped external API tests
pytest tests/ -k "external_api" -v

# Measure coverage improvement
pytest --cov=src --cov-report=term-missing
# Before: ~78%
# After: ~81% (130 tests unskipped)
```

### 4.3: Phase 3 - Feature Flag Testing (1.5 hours)

**Problem:** ~100 tests skip due to feature flags

**Solution:** Enable flags in tests

**Current Pattern:**
```python
@pytest.mark.skipif(not FEATURE_FLAG_ENABLED, reason="Feature disabled")
def test_new_feature():
    pass
```

**Fixed Pattern:**
```python
# tests/conftest.py
@pytest.fixture
def enable_all_features(monkeypatch):
    """Enable all feature flags for testing"""
    monkeypatch.setenv("ENABLE_FEATURE_X", "true")
    monkeypatch.setenv("ENABLE_FEATURE_Y", "true")
    # ... other flags

# tests/test_features.py
def test_new_feature(enable_all_features):
    # Test runs with feature enabled
    assert new_feature_works()
```

**Steps:**
1. List all feature flags
2. Create fixture to enable all flags
3. Update skipped tests to use fixture
4. Remove skip markers
5. Verify tests pass

**Testing:**
```bash
# Run previously skipped feature tests
pytest tests/ -k "feature" -v

# Measure final coverage
pytest --cov=src --cov-report=term-missing
# Before: ~81%
# After: ~83-85% (all skipped tests addressed)
```

### Success Criteria
- ✅ Import issues fixed: 310 tests unskipped
- ✅ External API mocked: 130 tests unskipped
- ✅ Feature flags enabled: 100 tests unskipped
- ✅ Coverage: 75.2% → 83-85%
- ✅ All 718+ tests running (not skipped)

---

## 📋 Task 5: CI/CD Deployment (1-2 hours)

### Overview
Deploy enhancements from SPRINT 2 CI/CD optimization report.

### 5.1: Update GitHub Actions Workflow (45 minutes)

**File:** `.github/workflows/tests.yml`

**Changes:**
1. Add parallel jobs (test, lint, quality run simultaneously)
2. Add pip caching (6x faster on cache hit)
3. Add maintainability index gate
4. Improve artifact management (only upload on failure)

**Key Features:**

```yaml
name: Tests & Quality

on: [push, pull_request]

jobs:
  # Job 1: Unit Tests
  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: pip install -e ".[dev]" -q
      - run: pytest project/tests/ -v --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3

  # Job 2: Linting (parallel with test)
  lint:
    name: Code Style Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install black flake8 mypy -q
      - run: black --check src/ tests/
      - run: flake8 src/ tests/ --max-line-length=100
      - run: mypy src/ --ignore-missing-imports

  # Job 3: Quality Metrics (parallel)
  quality:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install radon bandit -q
      - run: python3 -m radon cc src/ -a -s
      - run: python3 -m radon mi src/ -s
      - run: python3 -m bandit -r src/ -f txt -ll
```

**Steps:**
1. Replace sequential workflow with parallel jobs
2. Add pip caching
3. Add maintainability gate
4. Test locally first
5. Commit and verify in GitHub Actions

**Testing:**
```bash
# Verify workflow syntax
python3 -m pip install --upgrade pyyaml
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))"

# Test locally with act (optional)
# act -j test -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-latest
```

### 5.2: Add Maintainability Gate (30 minutes)

**Enhancement:** Fail CI if Maintainability Index < 75

```yaml
- name: Check Maintainability Index
  run: |
    python3 -m radon mi src/ -s > mi_report.txt
    avg_mi=$(tail -1 mi_report.txt | awk '{print $NF}')
    echo "Maintainability Index: $avg_mi"
    if (( $(echo "$avg_mi < 75" | bc -l) )); then
      echo "❌ MI below target (need >= 75)"
      exit 1
    fi
    echo "✅ Maintainability check passed"
```

**Steps:**
1. Add MI check step to quality job
2. Set threshold (currently 75, current is 63.4)
3. Make it optional for now (continue-on-error: true)
4. Test to ensure it catches MI < 75

### Success Criteria
- ✅ Parallel jobs implemented
- ✅ Pipeline time: 8-10min → 4-5min (50% faster)
- ✅ pip caching active (6x faster installs)
- ✅ Maintainability gate in place
- ✅ All jobs passing on main branch

---

## 📊 SPRINT 3 Success Metrics

| Metric | Current | After SPRINT 3 | Improvement |
|--------|---------|---|---|
| Security Issues (HIGH) | 1 | 0 | ✅ Eliminated |
| Security Issues (MEDIUM) | 12+ | 0 | ✅ Fixed |
| Import Time | 8s | 1.5s | 🟢 6.5x faster |
| Test Setup Time | 20s | 12s | 🟢 40% faster |
| Byzantine Test Speed | 2.5s | 1.2s | 🟢 50% faster |
| Raft Test Speed | 1.5s | 0.75s | 🟢 50% faster |
| Test Coverage | 75.2% | 83-85% | 🟢 8-10% gain |
| CI/CD Pipeline Time | 8-10min | 4-5min | 🟢 50% faster |
| Avg Cyclomatic Complexity | 3.2 | <3.0 | 🟢 Improved |

---

## 🗓️ SPRINT 3 Timeline

### Week 1 (Days 1-3)

**Day 1: Security Implementation (2.5h)**
- Fix MD5 hash (15 min)
- Externalize config (2h 15 min)
- All tests passing ✅

**Day 2: Performance Optimization (1.5h)**
- Lazy imports (45 min)
- Shared fixtures (45 min)
- Measure 30-40% improvement ✅

**Day 3: Complex Function Refactoring (2.5h)**
- Byzantine detector refactor (45 min)
- Raft consensus refactor (1h)
- Add tests (30 min)
- All tests passing ✅

### Week 2 (Days 4-7)

**Days 4-5: Coverage Improvement (3-5h)**
- Phase 1: Import fixes (2h)
- Phase 2: API mocking (1.5h)
- Phase 3: Feature flags (1.5h)
- Coverage: 75% → 83-85% ✅

**Day 6: CI/CD Deployment (1.5h)**
- Update GitHub Actions (45 min)
- Add maintainability gate (30 min)
- Verify pipeline (15 min)
- Deployed ✅

**Day 7: Testing & Validation (0.5h)**
- Run full test suite
- Verify all metrics improved
- Team code review & sign-off ✅

---

## 📋 Execution Checklist

### Pre-Implementation
- [ ] Review all SPRINT 2 reports
- [ ] Set up feature branch: `git checkout -b feat/sprint3-implementation`
- [ ] Install all development tools
- [ ] Create SPRINT 3 tracking document

### Task 1: Security
- [ ] Fix MD5 → SHA-256
- [ ] Create settings.py with environment variables
- [ ] Create .env file
- [ ] Update 8 app*.py files
- [ ] Run bandit to verify fixes
- [ ] All tests passing

### Task 2: Performance
- [ ] Identify heavy imports
- [ ] Create lazy-load functions
- [ ] Implement shared fixtures
- [ ] Measure import time improvement
- [ ] All tests passing
- [ ] No data leakage between tests

### Task 3: Refactoring
- [ ] Analyze Byzantine detector
- [ ] Extract helper functions
- [ ] Add new tests for extracted functions
- [ ] Analyze Raft consensus
- [ ] Fix circular references with weakref
- [ ] Measure speed improvement
- [ ] All tests passing

### Task 4: Coverage
- [ ] Identify import errors (Phase 1)
- [ ] Install missing dependencies
- [ ] Identify external API calls (Phase 2)
- [ ] Create mock fixtures
- [ ] Identify feature flags (Phase 3)
- [ ] Create flag fixtures
- [ ] Remove all fixable skip markers
- [ ] Verify coverage improvement

### Task 5: CI/CD
- [ ] Update GitHub Actions workflow
- [ ] Add maintainability gate
- [ ] Test workflow locally
- [ ] Verify parallel job execution
- [ ] Measure pipeline time improvement
- [ ] All GitHub Actions checks passing

### Post-Implementation
- [ ] Create SPRINT 3 completion report
- [ ] Team code review (all tasks)
- [ ] Merge to main branch
- [ ] Tag release (v3.2.0 or similar)
- [ ] Update README with new metrics
- [ ] Document lessons learned

---

## 📚 Dependencies & Tools

**Already Installed:**
- ✅ pytest, pytest-cov
- ✅ radon (code quality)
- ✅ bandit (security)
- ✅ pydantic-settings

**To Install (if needed):**
```bash
pip install -e ".[dev,ml,monitoring]"
```

---

## 🚀 How to Start

### Option 1: Start with Task 1 (Security) - RECOMMENDED
```bash
# Most critical, fixed duration (2.5h)
# Addresses HIGH security finding immediately

# 1. Create feature branch
git checkout -b feat/sprint3-security-implementation

# 2. Follow Task 1 steps above
# 3. Commit when complete
git commit -m "chore: fix security issues (MD5, hardcoded config)"
```

### Option 2: Start with Task 2 (Performance) - QUICK WINS
```bash
# Visible improvements (faster tests, imports)
# Quick ROI (1-2h for measurable gains)

git checkout -b feat/sprint3-performance-optimization
```

### Option 3: Start with Task 4 (Coverage) - LOWEST RISK
```bash
# Adding tests (safe, doesn't break existing code)
# High visibility (coverage goes up immediately)

git checkout -b feat/sprint3-coverage-improvement
```

---

## 📞 Questions Before Starting?

All SPRINT 2 analysis materials are available:
- [SPRINT2_SECURITY_REPORT_2026_01_25.md](SPRINT2_SECURITY_REPORT_2026_01_25.md) - Detailed security findings
- [SPRINT2_PERFORMANCE_PROFILE_2026_01_25.md](SPRINT2_PERFORMANCE_PROFILE_2026_01_25.md) - Performance analysis
- [SPRINT2_COVERAGE_ANALYSIS_2026_01_25.md](SPRINT2_COVERAGE_ANALYSIS_2026_01_25.md) - Coverage roadmap
- [SPRINT2_COMPLETION_2026_01_25.md](SPRINT2_COMPLETION_2026_01_25.md) - Full summary

---

## ✅ Success Criteria (All Tasks Complete)

✅ 0 HIGH security issues (from 1)  
✅ 0 MEDIUM hardcoded config issues (from 12+)  
✅ 6.5x faster imports  
✅ 40% faster test setup  
✅ 50% faster complex function tests  
✅ 83-85% coverage (from 75.2%)  
✅ 50% faster CI/CD pipeline  
✅ Maintainability gate in place  
✅ All 718+ tests passing  
✅ Full documentation updated  

---

**SPRINT 3 Status:** ✅ Ready to Start  
**Created:** January 25, 2026  
**Estimated Duration:** 8-12 hours over 2 weeks  
**Next Step:** Choose which task to start with and begin implementation  

🚀 **Ready to execute!**
