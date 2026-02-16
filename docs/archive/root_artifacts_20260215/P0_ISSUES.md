# 🔴 P0 (Critical) Issues - Sprint Action Items

**Status**: Active  
**Created**: 2026-01-25  
**Owner**: x0tta6bl4  
**Target**: Complete by 2026-01-31

---

## P0#1: Fix API Startup & /health Endpoint
**Priority**: 🔴 CRITICAL  
**Effort**: 4h  
**Status**: IN_PROGRESS

### Problem
- API hangs on startup (timeout after 30s)
- /health endpoint never responds
- Blocking: Cannot test any API features

### Root Cause
- Likely circular import or blocking operation in app initialization
- src/core/app.py imports many modules that may hang

### Solution
1. Trace app initialization step-by-step
2. Identify and remove blocking operations
3. Implement async initialization
4. Verify startup < 5 seconds
5. Test: `curl http://localhost:8000/health` → HTTP 200

### Acceptance Criteria
- ✓ `python -m uvicorn src.core.app:app --port 8000` starts in <5s
- ✓ GET /health returns `{"status": "ok", "version": "3.1.0"}`
- ✓ 3+ integration tests pass (test_api_startup, test_health_endpoint, test_health_deps)
- ✓ No hanging imports

### Tests Required
```python
# project/tests/test_p0_api.py
def test_api_import_no_hang():
    """App should import without timeout"""
    
@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health returns 200"""
    
@pytest.mark.asyncio 
async def test_health_response_format():
    """Response has status and version fields"""
```

---

## P0#2: Database Credentials from ENV (Not Hardcoded)
**Priority**: 🔴 CRITICAL  
**Effort**: 2h  
**Status**: BLOCKED (need P0#1)

### Problem
- Database credentials hardcoded in code
- Security violation: credentials in git history
- Cannot change DB without code changes

### Root Cause
- No environment variable loading at startup
- .env file not used or not loaded

### Solution
1. Identify all hardcoded database URLs/credentials
2. Move to environment variables (DB_URL, DB_USER, DB_PASS)
3. Create .env.example with placeholders
4. Update pyproject.toml to load python-dotenv
5. Implement BaseSettings from pydantic

### Acceptance Criteria
- ✓ No plaintext DB credentials in src/ files
- ✓ All creds come from environment (not git)
- ✓ .env.example documents required variables
- ✓ 5+ tests verify ENV loading (test_env_postgres, test_env_redis, etc.)
- ✓ git grep for passwords returns 0 results (except test mocks)

### Tests Required
```python
# project/tests/test_p0_env.py
def test_db_url_from_env():
    """DB_URL env var is used"""
    
def test_missing_env_var_fails():
    """Missing required env raises error"""
```

---

## P0#3: Implement /status Endpoint (Autonomic State)
**Priority**: 🔴 CRITICAL  
**Effort**: 3h  
**Status**: BLOCKED (need P0#1)

### Problem
- No way to query system health/status
- Autonomic loop status unknown
- Cannot monitor self-healing progress

### Root Cause
- /status endpoint stub exists but returns nothing
- MAPE-K loop state not exposed to API

### Solution
1. Add status fields: loop_running, loop_last_iteration, heap_usage, mesh_peers
2. Connect to MAPE-K loop state
3. Return JSON with all metrics
4. Add to Prometheus metrics export

### Acceptance Criteria
- ✓ GET /status returns HTTP 200
- ✓ Response includes: status, version, loop_running, timestamp
- ✓ Response validates against StatusResponse schema
- ✓ 5+ tests validate response fields

### Tests Required
```python
# project/tests/test_p0_status.py
def test_status_has_required_fields():
    """Response has status, version, loop_running"""
```

---

## P0#4: mTLS TLS 1.3 Enforcement
**Priority**: 🔴 CRITICAL  
**Effort**: 6h  
**Status**: BLOCKED (need P0#1)

### Problem
- TLS 1.3 enforcement incomplete
- Clients can connect without mTLS
- Security: No mutual authentication

### Root Cause
- SecurityHeadersMiddleware exists but doesn't enforce TLS 1.3
- Client certificate verification missing

### Solution
1. Add SSL context configuration (TLS 1.3 only)
2. Require client certificates in production
3. Validate SPIFFE SVIDs (when SPIRE available)
4. Reject non-TLS connections
5. Add test fixture for mTLS clients

### Acceptance Criteria
- ✓ API refuses non-TLS connections
- ✓ TLS version < 1.3 rejected
- ✓ Clients without certs rejected in prod
- ✓ 8+ tests verify enforcement

### Tests Required
```python
# project/tests/test_p0_mtls.py
def test_tls_version_enforced():
    """Only TLS 1.3 accepted"""
    
def test_client_cert_required():
    """Request without client cert rejected"""
```

---

## P0#5: Test Coverage to 75%
**Priority**: 🔴 CRITICAL  
**Effort**: 12h  
**Status**: IN_PROGRESS (9/50 tests written)

### Problem
- Coverage at 11% (target: 75%)
- 33,705 of 38,060 statements untested
- Missing: API tests, DB tests, security tests, mesh tests

### Root Cause
- Only 9 bootstrap tests exist
- Test structure just created, needs expansion

### Solution
1. Write 50+ additional tests covering:
   - API endpoints (15 tests)
   - Database connectivity (8 tests)
   - Security/mTLS (10 tests)
   - Mesh networking (10 tests)
   - MAPE-K loop (7 tests)
2. Target coverage ≥75% total
3. Fix any blocking issues found

### Acceptance Criteria
- ✓ `pytest --cov=src --cov-report=term` shows ≥75%
- ✓ All 50+ tests pass (green)
- ✓ No warnings in pytest output
- ✓ Coverage gap analysis complete

### Tests Required
```python
# project/tests/test_p0_coverage.py (15 endpoint tests)
# project/tests/test_p0_db.py (8 database tests)
# project/tests/test_p0_security.py (10 security tests)
# project/tests/test_p0_mesh.py (10 mesh tests)
# project/tests/test_p0_mape.py (7 loop tests)
```

---

## Implementation Order
1. **P0#1 (TODAY)** → Unblock API startup
2. **P0#2 (TODAY)** → Fix security issue
3. **P0#3 (TOMORROW)** → Add monitoring endpoints  
4. **P0#4 (TOMORROW)** → TLS enforcement
5. **P0#5 (THIS WEEK)** → Coverage to 75%

## Daily Checklist
- [ ] API starts in <5s
- [ ] /health endpoint responds
- [ ] /status endpoint responds
- [ ] No hardcoded credentials visible
- [ ] TLS 1.3 enforced in logs
- [ ] Coverage metric shows progress
- [ ] All tests passing (`pytest -v`)

## Success Metrics
| Metric | Target | Current |
|--------|--------|---------|
| API Startup Time | <5s | ∞ (hangs) |
| /health Response | 200 OK | No response |
| /status Response | 200 OK | No response |
| Hardcoded Creds | 0 files | Unknown |
| TLS 1.3 Enforcement | ✓ Yes | Partial |
| Test Coverage | 75% | 11% |

---

**Last Updated**: 2026-01-25 by GitHub Copilot  
**Next Review**: Daily standup (2026-01-26)
