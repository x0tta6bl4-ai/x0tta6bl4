---
name: test-coverage-boost
description: >
  Systematically improves test coverage for x0tta6bl4 modules.
  Use when user says "increase coverage", "add tests", "improve testing",
  "write unit tests", "boost coverage", "untested code", or
  "coverage report". Identifies uncovered code and generates focused tests.
metadata:
  author: x0tta6bl4
  version: 1.0.0
  category: testing
  tags: [testing, coverage, pytest, quality]
---

# Test Coverage Boost

## Instructions

### Step 1: Measure Current Coverage

Run coverage report to identify gaps:

```bash
python3 -m pytest tests/ --cov=src --cov-report=term-missing --tb=short -q
```

Parse the output to find modules with lowest coverage. Focus on:
- Modules below 75% coverage (project minimum threshold)
- Critical modules (security, core, network) regardless of percentage
- Recently changed files (check `git diff --name-only HEAD~5`)

### Step 2: Prioritize by Impact

Rank uncovered modules by criticality:

**P0 - Must cover** (security/correctness impact):
- `src/security/` - All security modules
- `src/core/` - Core application logic
- `src/api/` - API endpoints (attack surface)

**P1 - Should cover** (reliability impact):
- `src/network/` - Mesh networking
- `src/self_healing/` - MAPE-K loop
- `src/consensus/` - RAFT consensus

**P2 - Nice to cover** (quality improvement):
- `src/ml/` - ML models
- `src/dao/` - Governance
- `src/monitoring/` - Metrics

### Step 3: Generate Tests (Iterative)

For each uncovered module, follow this pattern:

1. **Read the source file** to understand its public API
2. **Identify test categories**:
   - Initialization / construction
   - Happy path (normal operation)
   - Edge cases (empty input, None, boundary values)
   - Error handling (invalid input, exceptions)
   - Integration points (mocked external dependencies)

3. **Write tests** following project conventions:
   - File: `tests/unit/{module}/test_{filename}_unit.py`
   - Use `pytest` with `unittest.mock` for mocking
   - Mark async tests with `@pytest.mark.asyncio`
   - Set environment variables at module level:
     ```python
     os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
     os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
     os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")
     ```
   - Use try/except ImportError with `pytest.skip` for optional dependencies
   - Group tests in classes by feature: `TestClassName`, `TestFeatureName`

4. **Run tests** to verify they pass:
   ```bash
   python3 -m pytest tests/unit/{module}/test_{filename}_unit.py -v --tb=short
   ```

5. **Re-measure coverage** for the module:
   ```bash
   python3 -m pytest tests/ --cov=src/{module} --cov-report=term-missing -q
   ```

6. **Repeat** until module reaches 75%+ coverage

### Step 4: Validate All Tests Pass

```bash
python3 -m pytest tests/ -v --tb=short -q
```

All existing tests must continue to pass. New tests must not break old ones.

## Test Patterns for x0tta6bl4

### Mocking external services
```python
from unittest.mock import patch, MagicMock, AsyncMock

# Mock database
@patch("src.api.users.users_db", new_callable=MagicMock)
def test_something(mock_db):
    mock_db.find_one.return_value = {"id": "1", "email": "a@b.com"}
    ...

# Mock async operations
@pytest.mark.asyncio
async def test_async_op():
    with patch("src.module.async_func", new_callable=AsyncMock) as mock:
        mock.return_value = {"status": "ok"}
        result = await some_function()
        assert result["status"] == "ok"
```

### Testing torch-dependent code
```python
def _make_detector(**kwargs):
    """Handle environments where torch_geometric fails."""
    try:
        return GraphSAGEAnomalyDetector(**kwargs)
    except Exception:
        import src.ml.graphsage_anomaly_detector as _mod
        orig = _mod._TORCH_AVAILABLE
        _mod._TORCH_AVAILABLE = False
        try:
            return GraphSAGEAnomalyDetector(**kwargs)
        finally:
            _mod._TORCH_AVAILABLE = orig
```

### Testing FastAPI endpoints
```python
from fastapi.testclient import TestClient
from src.core.app import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
```

## Quality Checklist

Before marking coverage work as done:
- [ ] All new tests pass independently (`pytest test_file.py -v`)
- [ ] All existing tests still pass (`pytest tests/ -q`)
- [ ] No tests depend on execution order
- [ ] External services are mocked (DB, network, filesystem)
- [ ] Async tests use `@pytest.mark.asyncio`
- [ ] Coverage for target module is 75%+
