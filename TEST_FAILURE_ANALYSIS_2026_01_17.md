# Test Failure Analysis & Fix Strategy - Jan 17, 2026

**Status:** 165 passing, 37 failing, 34 skipped (4.86% coverage)  
**Target:** Fix top 10-15 failures by Jan 25 (increase coverage to 15%)  
**Effort:** 16-24 engineering hours

---

## 📊 Test Failure Classification

### Category A: Missing Dependencies (Est. 12-15 tests)

**Root Cause:** External packages not installed or conditionally unavailable
- `liboqs-python` for Post-Quantum Cryptography
- `opentelemetry-*` packages for distributed tracing
- `pyzmq` for messaging
- ML frameworks (PyTorch, TensorFlow)

**Files Affected:**
- `test_liboqs_integration.py` - expects liboqs
- `test_pqc_fuzzing.py` - expects liboqs
- `test_graphsage_detector.py` - expects torch/tensorflow
- `test_causal_analysis.py` - expects torch
- Integration tests expecting specific trace backends

**Symptom:**
```
ModuleNotFoundError: No module named 'oqs'
ImportError: cannot import name 'KeyEncapsulation' from 'oqs'
```

**Fix Strategy:**
```python
# Pattern: Use try/except + @pytest.mark.skipif
try:
    import oqs
    HAS_OQS = True
except ImportError:
    HAS_OQS = False

@pytest.mark.skipif(not HAS_OQS, reason="liboqs not installed")
class TestLibOQS:
    def test_something(self):
        ...
```

**Action Items:**
- [ ] Audit all `import oqs`, `import torch`, `import tf` statements
- [ ] Wrap with try/except + skip marker
- [ ] Document which tests skip in CI vs staging
- [ ] Create `requirements-optional.txt` for dev dependencies

---

### Category B: Database/Persistence Not Configured (Est. 5-8 tests)

**Root Cause:** Tests expect real database but environment not set up
- `DATABASE_URL` environment variable not set
- PostgreSQL/SQLite not running
- Migration files not executed

**Files Affected:**
- `test_critical_paths.py` (lines 115-145) - database integration test
- Any tests using `SessionLocal` or ORM models
- `test_user_store.py` - if exists

**Symptom:**
```
sqlalchemy.exc.OperationalError: could not connect to server
FAILED test_database_integration - sqlalchemy.exc.NoSuchTableError
```

**Fix Strategy:**
```python
# Pattern: Skip if DATABASE_URL not configured
import os
import pytest

@pytest.fixture(scope="session")
def db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url

# In test:
def test_db(db_url):
    # Use db_url
    ...
```

**Action Items:**
- [ ] Find all DATABASE_URL dependencies
- [ ] Add skip conditions
- [ ] Create `conftest.py` with shared fixtures
- [ ] Document how to run DB tests locally

---

### Category C: External Service Dependencies (Est. 6-10 tests)

**Root Cause:** Tests call external APIs (Stripe, TRON, TON, Slack, etc.)
- Payment gateway APIs
- Blockchain APIs (TRON, TON)
- Alerting/monitoring services (Slack, PagerDuty)
- Third-party ML services

**Files Affected:**
- `test_critical_paths.py` (test_payment_flow_mock, etc.) - response mismatch errors
- `test_payment_verification.py` - if exists
- Tests with API mocks that don't match real responses

**Symptom:**
```
FAILED test_payment_flow_mock - AssertionError: Expected 200, got 400
```

**Fix Strategy:**
```python
# Pattern: Mock external services properly
from unittest.mock import patch, MagicMock

@patch('src.sales.payment_verification.TronScanVerifier')
def test_payment(mock_verifier):
    mock_verifier.return_value.verify.return_value = {
        'status': 'success',
        'amount': 100
    }
    # Test payment flow
    ...
```

**Action Items:**
- [ ] Find all test mismatches (grep "RESPONSE MISMATCH")
- [ ] Fix mock return values to match actual API responses
- [ ] Document expected API response formats
- [ ] Add `@pytest.mark.external` for real API tests

---

### Category D: Async/Coroutine Issues (Est. 3-5 tests)

**Root Cause:** Tests calling async functions without proper event loop
- Missing `pytest-asyncio` setup
- Mixing `async def` with sync test functions
- `await` without `async def`

**Files Affected:**
- Any test calling `asyncio.run()`
- `test_critical_paths.py` - async functions
- `test_ebpf_loader.py` - async eBPF loading

**Symptom:**
```
RuntimeError: no running event loop
TypeError: object coroutine can't be used in 'await' expression
```

**Fix Strategy:**
```python
# Pattern: Use @pytest.mark.asyncio for async tests
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

**Action Items:**
- [ ] Add `pytest-asyncio` to `requirements-dev.txt`
- [ ] Mark all async tests with `@pytest.mark.asyncio`
- [ ] Update `conftest.py` with asyncio plugin config
- [ ] Convert blocking tests to async where needed

---

### Category E: Assertion/Logic Errors (Est. 3-5 tests)

**Root Cause:** Test logic doesn't match code or expectations changed
- Assertions testing old behavior
- Expected vs actual mismatch
- Off-by-one errors, wrong assertions

**Files Affected:**
- Various security component tests
- Mock response format tests

**Symptom:**
```
AssertionError: assert [] == ['expected']
AssertionError: 429 != 200
```

**Fix Strategy:**
```python
# Pattern: Review assertion logic
def test_rate_limiting():
    # Wrong: tests 10 requests but limit is 10, so all pass
    for i in range(10):
        response = client.get("/api/endpoint")
        assert response.status_code == 200
    
    # Right: tests 11 requests so 11th should fail
    for i in range(11):
        response = client.get("/api/endpoint")
        if i < 10:
            assert response.status_code == 200
        else:
            assert response.status_code == 429
```

**Action Items:**
- [ ] Review each failing test's assertions
- [ ] Check if assertions match actual code behavior
- [ ] Update test data if behavior changed
- [ ] Document expected behavior in docstrings

---

### Category F: Missing Fixtures/Setup (Est. 2-4 tests)

**Root Cause:** Test fixtures not properly initialized
- Database session not available
- Mock clients not created
- Initialization order issues

**Files Affected:**
- Tests with complex setup
- Tests sharing state

**Symptom:**
```
AttributeError: 'NoneType' object has no attribute 'execute'
FixtureLookupError: fixture 'client' not found
```

**Fix Strategy:**
```python
# Pattern: Create proper fixtures in conftest.py
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
```

**Action Items:**
- [ ] Audit `tests/conftest.py` for completeness
- [ ] Move fixture definitions to conftest.py
- [ ] Add fixture documentation
- [ ] Create module-specific fixtures where needed

---

### Category G: API/Response Format Changes (Est. 3-4 tests)

**Root Cause:** Response format changed but tests not updated
- New fields added to responses
- Field names changed
- Response structure reorganized

**Files Affected:**
- Integration tests checking response structure
- API contract tests

**Symptom:**
```
KeyError: 'expected_field'
AssertionError: Response does not contain expected structure
```

**Fix Strategy:**
```python
# Pattern: Use flexible assertions
def test_user_response():
    response = client.get("/api/v1/user")
    data = response.get_json()
    
    # Check minimum required fields
    assert 'user_id' in data
    assert 'username' in data
    # Don't assert on api_key or other sensitive fields
```

**Action Items:**
- [ ] Document API response schemas (use Pydantic models)
- [ ] Update tests to match current schemas
- [ ] Add response validation tests
- [ ] Use OpenAPI/Swagger to document contracts

---

## 🎯 Priority Fixes (Top 15 by Impact)

### Priority 1: Critical Blockers (Fix First - Day 1-2)

**P1-1: Category A - liboqs dependency**  
**Tests Affected:** 4-5 tests  
**Effort:** 2 hours  
**Impact:** Unblocks all PQC tests  
```python
# Fix: Add @pytest.mark.skipif(not HAS_OQS) to liboqs-dependent tests
# Files: test_liboqs_integration.py, test_pqc_fuzzing.py
```

**P1-2: Category D - Async test setup**  
**Tests Affected:** 2-3 tests  
**Effort:** 1.5 hours  
**Impact:** Unblocks eBPF & async tests  
```python
# Fix: Install pytest-asyncio, mark async tests
# Files: conftest.py, test_ebpf_loader.py, test_critical_paths.py
```

**P1-3: Category F - Test fixtures**  
**Tests Affected:** 2-3 tests  
**Effort:** 1.5 hours  
**Impact:** Enables proper test isolation  
```python
# Fix: Create/update conftest.py with shared fixtures
```

---

### Priority 2: Data Layer (Fix Day 2-3)

**P2-1: Category B - Database configuration**  
**Tests Affected:** 5-8 tests  
**Effort:** 3 hours  
**Impact:** Enables database tests  
```bash
# Fix: Add skip conditions for DATABASE_URL-dependent tests
# Create fixtures for in-memory DB
```

**P2-2: Category C - External service mocks**  
**Tests Affected:** 6-10 tests  
**Effort:** 4 hours  
**Impact:** Fixes response mismatch issues  
```python
# Fix: Update mock return values to match real responses
# Files: test_critical_paths.py, payment tests
```

---

### Priority 3: Logic & Setup (Fix Day 3-4)

**P3-1: Category E - Assertion fixes**  
**Tests Affected:** 3-5 tests  
**Effort:** 2 hours  
**Impact:** Fixes logic errors  

**P3-2: Category G - Response format**  
**Tests Affected:** 3-4 tests  
**Effort:** 2 hours  
**Impact:** Ensures API contracts**

---

## 📋 Execution Plan

### Day 1 (Jan 18-19): Quick Wins (6-8 fixes)

**Tasks:**
1. [ ] Add skip conditions for liboqs tests (30 min)
2. [ ] Configure pytest-asyncio (30 min)
3. [ ] Create conftest.py with basic fixtures (1 hour)
4. [ ] Fix 3-4 assertion logic errors (1.5 hours)
5. [ ] Add DATABASE_URL skip conditions (30 min)

**Expected Results:**
- 6-8 tests now passing
- Coverage: 4.86% → ~6.5%
- All P1-1, P1-2, P1-3 complete

---

### Day 2 (Jan 20): Data Layer (8-10 fixes)

**Tasks:**
1. [ ] Review all external service mocks (1 hour)
2. [ ] Fix mock return values (2 hours)
3. [ ] Update response assertions (1 hour)
4. [ ] Add response format tests (1 hour)
5. [ ] Document API schemas (1 hour)

**Expected Results:**
- 8-10 tests fixed
- Coverage: 6.5% → ~10%
- All P2-1, P2-2 complete

---

### Day 3 (Jan 21-22): Final Polish (6-8 fixes)

**Tasks:**
1. [ ] Review remaining logic errors (1 hour)
2. [ ] Fix response format issues (2 hours)
3. [ ] Update fixtures if needed (1 hour)
4. [ ] Run full test suite (30 min)
5. [ ] Document test results (30 min)

**Expected Results:**
- 6-8 tests fixed
- Coverage: 10% → ~15%
- All P3-1, P3-2 complete

---

## 🔍 Testing & Verification

### Before Making Changes
```bash
# Current status
pytest tests/ -v --tb=short 2>&1 | tee test_run_baseline.log
pytest tests/ --co -q | wc -l  # Count all tests
pytest tests/ -x  # Stop on first failure to see root cause
```

### After Each Fix
```bash
# Verify fix didn't break anything
pytest tests/ -v --tb=short
pytest tests/ -k "test_name" -v  # Test specific function
pytest tests/ --cov=src --cov-report=term-missing
```

### Final Verification (Jan 23)
```bash
# Full regression test
pytest tests/ -v --tb=short --cov=src --cov-report=html
# Coverage should be 10-15% minimum
```

---

## 📚 Resources & Reference

### Test Structure
```
tests/
├── conftest.py              ← Shared fixtures (needs update)
├── unit/
│   ├── security/           ← 15+ security tests
│   ├── ml/                 ← GraphSAGE, causal analysis
│   ├── network/            ← Mesh, eBPF
│   └── other/              ← Utils, storage, etc.
└── integration/
    ├── test_critical_paths.py    ← 7 tests (3 response mismatch)
    ├── test_payment_verification.py
    └── other/
```

### Key Dependencies for Tests
```
pytest==8.0.0
pytest-asyncio==0.23.0        ← NEW (needed for async tests)
pytest-cov==4.1.0
pytest-mock==3.12.0
unittest-mock==1.5.0          ← Already included
```

### Common Pytest Markers
```python
@pytest.mark.skipif(condition, reason="why")
@pytest.mark.asyncio           # For async tests
@pytest.mark.slow              # For slow tests
@pytest.mark.integration       # For integration tests
@pytest.mark.external          # For tests needing external services
```

---

## 📄 Test Failure Log Template

For each failing test, document:

```markdown
### Test: test_name
**File:** path/to/test_file.py:line_number
**Category:** A/B/C/D/E/F/G
**Current Status:** FAILING
**Root Cause:** [description]
**Fix:** [specific code change]
**Effort:** [hours]
**Status:** [ ] TODO [ ] IN PROGRESS [ ] DONE
**Notes:** [any additional context]
```

---

## 🚀 Implementation Notes

### Safety Practices
1. **Make one change at a time** - commit/test after each fix
2. **Keep original tests** - don't delete, just skip if needed
3. **Add comments** explaining why tests skip
4. **Document dependencies** in conftest.py
5. **Use fixtures** for reusable test setup

### Avoid Common Mistakes
- ❌ Don't remove failing tests - skip them instead
- ❌ Don't modify production code to pass tests
- ❌ Don't hardcode test data - use factories/fixtures
- ❌ Don't assume external services are available
- ❌ Don't ignore async/await syntax requirements

---

## 📈 Success Metrics

| Metric | Current | Day 1 | Day 2 | Day 3 | Target |
|--------|---------|-------|-------|-------|--------|
| **Passing Tests** | 165 | 171 | 177 | 182 | 190+ |
| **Failing Tests** | 37 | 31 | 25 | 19 | <10 |
| **Coverage %** | 4.86% | 6.5% | 10% | 15% | 75% |
| **Test Execution** | 65.99s | ~63s | ~65s | ~67s | <60s |

---

## 📞 Questions for Team

1. **Which tests are highest priority for your use case?**
   - Security tests?
   - Payment/integration tests?
   - Performance tests?

2. **Can we skip some tests in CI?**
   - Tests requiring expensive external services
   - Tests needing ML model training

3. **What's the timeline pressure?**
   - Should we parallelize test fixes?
   - Any blocking issues for customer1?

---

## Next Steps

1. ✅ Create this analysis document (DONE)
2. [ ] Assign Category A-G fixes to team members
3. [ ] Run pytest with verbose output to identify actual failures
4. [ ] Start with Priority 1 quick wins (Day 1)
5. [ ] Daily progress update to CONTINUITY.md

---

*Document created: Jan 17, 2026, 20:48 CET*  
*Purpose: Guide test failure resolution Jan 18-25*  
*Target: 37 failing → <10 failing, 4.86% → 15% coverage*
