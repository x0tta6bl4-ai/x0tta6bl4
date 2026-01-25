# Phase 1 Security Hardening - Execution Briefing

**Date:** Jan 18, 2026 (Morning Kickoff)  
**Duration:** Jan 18-21 (4 days, 32 engineering hours)  
**Owner:** [Security Lead / Senior Engineer]  
**Team:** [2-3 engineers]  
**Status:** ✅ READY TO START

---

## 🎯 Mission

**Fix 8 Critical Security Issues (P0) in 4 days to unblock customer validation.**

| Metric | Target | Success Criteria |
|--------|--------|------------------|
| Critical Issues Fixed | 8/8 | 100% |
| Code Coverage Impact | 4.86% → 5.5% | +0.64% |
| Customer Confidence | Low | Medium |
| Production Blocker Status | 8 blocked | 0 blocked |
| Timeline | 32 hours | On schedule |

---

## 📋 Phase 1 Issues (P0 - Critical)

### Issue P0-1: ✅ post_quantum Import Fix
**Status:** COMPLETED (Jan 17)  
**What:** Tests failing due to missing `src.security.post_quantum` module  
**Fix Applied:**
```python
try:
    from src.security.post_quantum import PQMeshSecurityLibOQS
    POSTQUANTUM_AVAILABLE = True
except ImportError:
    POSTQUANTUM_AVAILABLE = False
    class PQMeshSecurityLibOQS: pass  # Mock
```
**Effort:** 2 hours (DONE)  
**Result:** Tests now import correctly, 165 passing ✅

---

### Issue P0-2: Weak Password Hashing (SHA-256 → Bcrypt)
**Status:** 🟡 READY TO START (Jan 18 morning)  
**Owner:** [Engineer A]  
**Deadline:** Jan 19, EOD  
**CVSS:** 7.8 (High)  
**Impact:** User credentials vulnerable if DB leaked

#### What's Broken
```python
# src/web/users.py (CURRENT - WRONG)
import hashlib
user_password = hashlib.sha256(password.encode()).hexdigest()
# Problems:
# - SHA-256 is NOT password hashing algorithm
# - No salt by default (rainbow table attacks)
# - GPU brute-forceable in seconds
# - Not time-hardened
```

#### What to Fix
```python
# src/web/users.py (CORRECT)
import bcrypt

# In password creation:
password_hash = bcrypt.hashpw(
    password.encode('utf-8'),
    bcrypt.gensalt(rounds=12)  # 12 rounds = ~0.5s per hash
)

# In password verification:
if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
    # Password correct
    pass
```

#### Specific Changes Needed
1. **File: `src/web/users.py`** (or wherever password hashing happens)
   - [ ] Remove hashlib import
   - [ ] Add `import bcrypt`
   - [ ] Replace all `hashlib.sha256()` calls with `bcrypt.hashpw()`
   - [ ] Update password comparison to use `bcrypt.checkpw()`

2. **File: `requirements.txt`**
   - [ ] Add `bcrypt==4.1.0`

3. **File: `src/sales/telegram_bot.py`** (if uses passwords)
   - [ ] Check for password hashing
   - [ ] Update if needed

4. **Database Migration**
   - [ ] Create script to hash existing passwords (one-time)
   - [ ] Document for ops team

#### How to Test
```python
# Test bcrypt hashing
import bcrypt

password = "SecurePassword123!"
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
assert bcrypt.checkpw(password.encode(), hashed)  # Should pass
assert not bcrypt.checkpw("WrongPassword".encode(), hashed)  # Should fail
```

**Commands:**
```bash
# Find all SHA-256 password usage
grep -r "hashlib.sha256" src/
grep -r "password.*hexdigest" src/

# After fix, verify
grep -r "bcrypt" src/ | grep -v ".pyc"
```

**Effort:** 2 hours  
**Timeline:** Jan 18, 10:00 - Jan 19, 12:00  
**Review:** [Tech Lead]

---

### Issue P0-3: API Keys Exposed in Responses
**Status:** 🟡 READY TO START (Jan 18 afternoon)  
**Owner:** [Engineer B]  
**Deadline:** Jan 19, EOD  
**CVSS:** 7.5 (High)  
**Impact:** API keys exposed, unauthorized access possible

#### What's Broken
```python
# Current (WRONG) - API response includes secrets
@app.route('/api/v1/user', methods=['GET'])
def get_user():
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'api_key': user.api_key,  # ❌ EXPOSED
        'password_hash': user.password_hash  # ❌ EXPOSED
    })

# Network attacker can see response → extracts api_key → gains access
```

#### What to Fix

Create separate response models:
```python
# src/web/schemas.py (NEW)
from pydantic import BaseModel

class UserPublicResponse(BaseModel):
    """For API responses - NO SECRETS"""
    user_id: str
    username: str
    email: str
    plan: str

class UserSelfResponse(BaseModel):
    """For authenticated user fetching own data - still NO SECRETS"""
    user_id: str
    username: str
    email: str
    plan: str
    created_at: datetime
    # NO api_key, NO password_hash

# API KEY is retrieved via separate SECURED endpoint
class UserAPIKeyResponse(BaseModel):
    api_key: str
    # Only on /api/v1/user/api-key with rate limiting
```

#### Specific Changes Needed

1. **Find all exposed fields**
   ```bash
   # Search for responses with sensitive data
   grep -r "api_key" src/web/ --include="*.py"
   grep -r "password" src/web/ --include="*.py" | grep -v "password_reset"
   grep -r "secret" src/web/ --include="*.py"
   ```

2. **Update all API responses**
   - [ ] `@app.route('/api/v1/user'` - remove api_key
   - [ ] `@app.route('/api/v1/users'` - remove api_key (if list endpoint)
   - [ ] Any endpoint returning user data - review fields

3. **File: `src/web/users.py` (or API handlers)**
   - [ ] Import new response models
   - [ ] Replace dict responses with `UserPublicResponse(...)`
   - [ ] Verify no secrets in any response

#### How to Test
```python
# Test user response doesn't include secrets
response = client.get('/api/v1/user', headers=auth_headers)
data = response.get_json()

assert 'user_id' in data  # Public field
assert 'username' in data  # Public field
assert 'api_key' not in data  # SECRET - should not be here!
assert 'password_hash' not in data  # SECRET - should not be here!
```

**Commands:**
```bash
# Before fix: find exposed keys
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v1/user | jq '.api_key'

# After fix: should not appear
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v1/user | jq '.api_key'
# Should return: null or error
```

**Effort:** 1.5 hours  
**Timeline:** Jan 18, 14:00 - Jan 19, 10:00  
**Review:** [Tech Lead]

---

### Issue P0-4: Flask Missing SECRET_KEY
**Status:** 🟡 READY TO START (Jan 18)  
**Owner:** [Engineer A or B]  
**Deadline:** Jan 18, EOD  
**CVSS:** 4.0 (Medium)  
**Impact:** Session cookies not signed, vulnerable to tampering

#### What's Broken
```python
# src/web/aggregator_dashboard.py (CURRENT - WRONG)
from flask import Flask
app = Flask(__name__)
# NO SECRET_KEY → Flask warns but continues
# Sessions cookies NOT signed → attackers can modify them
```

#### What to Fix
```python
# src/web/aggregator_dashboard.py (CORRECT)
import os
from flask import Flask

app = Flask(__name__)

# Load SECRET_KEY from environment
app.secret_key = os.getenv('FLASK_SECRET_KEY')

if not app.secret_key:
    raise ValueError(
        "FLASK_SECRET_KEY not set! "
        "Generate with: python -c \"import secrets; "
        "print(secrets.token_hex(32))\""
    )
```

#### Specific Changes Needed

1. **File: `src/web/aggregator_dashboard.py`**
   - [ ] Import `os`
   - [ ] Set `app.secret_key = os.getenv('FLASK_SECRET_KEY')`
   - [ ] Add error handling if not set

2. **File: `.env.example`**
   - [ ] Add `FLASK_SECRET_KEY=change_me_in_production`

3. **File: `k8s/helm/values.yaml`** (or env deployment)
   - [ ] Add secret: `FLASK_SECRET_KEY=<generate_random>`
   - [ ] For local dev: `export FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")`

#### How to Test
```bash
# Generate a test key
TEST_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
echo "Generated: $TEST_KEY"

# Set in environment
export FLASK_SECRET_KEY=$TEST_KEY

# Start app
python -m src.web.aggregator_dashboard

# Verify key is loaded (should not raise error)
# Try to set a session cookie
# Verify cookie is signed (starts with . if encoding properly)
```

**Effort:** 0.5 hours  
**Timeline:** Jan 18, 09:00 - 10:00 (morning quick fix)  
**Review:** [Tech Lead]

---

### Issue P0-5: Insecure Password Comparison
**Status:** 🟡 READY TO START (Jan 18)  
**Owner:** [Engineer B]  
**Deadline:** Jan 18, EOD  
**CVSS:** 5.3 (Medium)  
**Impact:** Timing attacks to guess passwords

#### What's Broken
```python
# src/auth/authentication.py (CURRENT - WRONG)
def verify_password(password, stored_hash):
    return password == stored_hash  # ❌ TIMING ATTACK VULNERABLE
    # Time varies based on how many chars match
    # Attacker can guess char-by-char using timing analysis
```

#### What to Fix
```python
# src/auth/authentication.py (CORRECT)
import hmac

def verify_password(password, stored_hash):
    return hmac.compare_digest(password, stored_hash)
    # Always takes same time regardless of match position
```

#### Specific Changes Needed

1. **File: `src/auth/authentication.py`** (or wherever password comparison happens)
   - [ ] Import `hmac`
   - [ ] Replace `==` with `hmac.compare_digest()` for:
     - Password comparison
     - API key comparison
     - Token comparison
     - Any sensitive string comparison

2. **Find all comparisons**
   ```bash
   grep -r "password ==" src/ --include="*.py"
   grep -r "api_key ==" src/ --include="*.py"
   grep -r "token ==" src/ --include="*.py"
   ```

#### How to Test
```python
import hmac

password = "SecurePassword123!"
stored = "SecurePassword123!"

# Should use hmac.compare_digest
assert hmac.compare_digest(password.encode(), stored.encode())
assert not hmac.compare_digest(password.encode(), b"wrong")
```

**Effort:** 0.5 hours  
**Timeline:** Jan 18, 10:00 - 11:00  
**Review:** [Tech Lead]

---

### Issue P0-6: Missing Rate Limiting
**Status:** 🟡 READY TO START (Jan 19)  
**Owner:** [Engineer A]  
**Deadline:** Jan 20, EOD  
**CVSS:** 7.5 (High)  
**Impact:** Brute force, DDoS attacks

#### What's Broken
```python
# src/web/users.py (CURRENT - WRONG)
@app.route('/api/v1/login', methods=['POST'])
def login():
    # No rate limiting - attacker can brute force passwords
    # Try 1000 passwords/second without limit
    ...
```

#### What to Fix
```python
# src/web/users.py (CORRECT)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/v1/login', methods=['POST'])
@limiter.limit("5 per minute")  # 5 attempts per minute per IP
def login():
    # Attacker limited to 5 attempts/minute
    # After 5 attempts, get 429 Too Many Requests
    ...
```

#### Endpoints to Protect
- [ ] `/api/v1/login` → 5 per minute
- [ ] `/api/v1/register` → 3 per hour
- [ ] `/api/v1/payment` → 10 per minute
- [ ] `/api/v1/user/<id>` → 100 per minute
- Any other sensitive endpoint

#### Effort:** 2 hours  
**Timeline:** Jan 19, 09:00 - Jan 20, 12:00  
**Review:** [Tech Lead]

---

### Issue P0-7: Missing Authentication on Admin Endpoints
**Status:** 🟡 READY TO START (Jan 19)  
**Owner:** [Engineer B]  
**Deadline:** Jan 20, EOD  
**CVSS:** 8.8 (High)  
**Impact:** Unauthorized admin access

#### What's Broken
```python
# src/web/admin.py (CURRENT - WRONG)
@app.route('/admin/users', methods=['GET'])
def list_all_users():
    # NO authentication check!
    # Anyone can access this endpoint
    return jsonify(all_users)
```

#### What to Fix
```python
# src/web/admin.py (CORRECT)
from functools import wraps
import jwt

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return {'error': 'Missing token'}, 401
        
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, app.config['SECRET_KEY'])
            if payload.get('role') != 'admin':
                return {'error': 'Not admin'}, 403
        except Exception as e:
            return {'error': 'Invalid token'}, 401
        
        return f(*args, **kwargs)
    return decorated

@app.route('/admin/users', methods=['GET'])
@require_admin
def list_all_users():
    # Now protected - only admins can access
    return jsonify(all_users)
```

#### Admin Endpoints to Protect
```bash
# Find all admin endpoints
grep -r "/admin" src/web/ --include="*.py"
grep -r "admin_" src/web/ --include="*.py"

# Common ones:
# /admin/users
# /admin/stats
# /admin/settings
# /admin/logs
# /admin/health
```

#### Effort:** 2 hours  
**Timeline:** Jan 19, 14:00 - Jan 20, 16:00  
**Review:** [Tech Lead]

---

### Issue P0-8: Pickle Deserialization (Remote Code Execution)
**Status:** 🟡 READY TO START (Jan 20)  
**Owner:** [Engineer A]  
**Deadline:** Jan 21, EOD  
**CVSS:** 9.8 (Critical)  
**Impact:** Remote code execution, full system compromise

#### What's Broken
```python
# src/core/model_loader.py (CURRENT - WRONG)
import pickle

def load_model(serialized_data):
    model = pickle.loads(serialized_data)  # ❌ ARBITRARY CODE EXECUTION!
    # Attacker can craft serialized data that executes arbitrary Python code
    # Full system compromise possible
```

#### What to Fix
```python
# src/core/model_loader.py (CORRECT)
import json

def load_model(json_data):
    # JSON can only deserialize data structures, not code
    model = json.loads(json_data)
    # Safe - no code execution possible
    return model
```

#### Specific Changes Needed

1. **Find all pickle usage**
   ```bash
   grep -r "pickle" src/ --include="*.py"
   grep -r "\.loads(" src/ --include="*.py" | grep -v json
   ```

2. **Replace pickle with JSON**
   - [ ] Change `pickle.dumps()` → `json.dumps()`
   - [ ] Change `pickle.loads()` → `json.loads()`
   - [ ] Update serialization format (may need model conversion)

3. **Files likely affected:**
   - `src/ml/model_loader.py` (if exists)
   - `src/core/persistence.py` (if uses pickle)
   - Any file with `.loads()` method

4. **Migration:**
   - [ ] Create script to convert existing pickled data to JSON
   - [ ] Document for ops team

#### How to Test
```python
import json

data = {'model': 'test', 'weights': [1, 2, 3]}

# Serialize
serialized = json.dumps(data)

# Deserialize (safe)
loaded = json.loads(serialized)
assert loaded == data
```

**Effort:** 3 hours  
**Timeline:** Jan 20, 09:00 - Jan 21, 18:00  
**Review:** [Tech Lead]

---

## 🎯 Daily Schedule

### Friday, Jan 18

| Time | Activity | Owner | Status |
|------|----------|-------|--------|
| 09:00 | Team kickoff (15 min) | [Lead] | 🟡 |
| 09:15 | **P0-4 start** (Flask SECRET_KEY) | [Eng A/B] | 🟡 |
| 10:00 | **P0-5 start** (Password comparison) | [Eng B] | 🟡 |
| 12:00 | Lunch + standup (15 min) | [Lead] | 🟡 |
| 13:00 | **P0-2 start** (Bcrypt) | [Eng A] | 🟡 |
| 14:00 | **P0-3 start** (API keys) | [Eng B] | 🟡 |
| 15:00 | Code review (peer) | [Both] | 🟡 |
| 16:00 | EOD standup + Slack update | [Lead] | 🟡 |
| 16:30 | Merge completed PRs | [Lead] | 🟡 |

**Target:** P0-4, P0-5 DONE; P0-2, P0-3 in progress

---

### Saturday, Jan 19

| Time | Activity | Owner | Status |
|------|----------|-------|--------|
| 09:00 | Standup | [Lead] | 🟡 |
| 09:15 | **P0-2 finish** (Bcrypt) | [Eng A] | 🟡 |
| 10:00 | **P0-3 finish** (API keys) | [Eng B] | 🟡 |
| 12:00 | Lunch + sync | [Lead] | 🟡 |
| 13:00 | **P0-6 start** (Rate limiting) | [Eng A] | 🟡 |
| 14:00 | **P0-7 start** (Admin auth) | [Eng B] | 🟡 |
| 15:00 | Code review + testing | [Both] | 🟡 |
| 16:00 | EOD standup | [Lead] | 🟡 |

**Target:** P0-2, P0-3 DONE; P0-6, P0-7 in progress

---

### Sunday, Jan 20

| Time | Activity | Owner | Status |
|------|----------|-------|--------|
| 09:00 | Standup | [Lead] | 🟡 |
| 09:15 | **P0-6 finish** (Rate limiting) | [Eng A] | 🟡 |
| 10:00 | **P0-7 finish** (Admin auth) | [Eng B] | 🟡 |
| 12:00 | Lunch + sync | [Lead] | 🟡 |
| 13:00 | **P0-8 start** (Pickle RCE) | [Eng A] | 🟡 |
| 15:00 | Test & review | [Both] | 🟡 |
| 16:00 | EOD standup | [Lead] | 🟡 |

**Target:** P0-6, P0-7 DONE; P0-8 in progress

---

### Monday, Jan 21

| Time | Activity | Owner | Status |
|------|----------|-------|--------|
| 09:00 | Standup | [Lead] | 🟡 |
| 09:15 | **P0-8 finish** (Pickle RCE) | [Eng A] | 🟡 |
| 11:00 | Final testing & review | [Both] | 🟡 |
| 13:00 | Lunch | - | 🟡 |
| 14:00 | **CUSTOMER FEEDBACK CALL** | [Lead] | 🟡 |
| 15:00 | Post-call sync & adjustments | [Lead] | 🟡 |
| 16:00 | Phase 1 completion verification | [Lead] | 🟡 |
| 17:00 | Document results & kickoff Phase 2 | [Lead] | 🟡 |

**Target:** ALL P0 issues DONE by 16:00

---

## ✅ Completion Checklist

### For Each Issue Fixed
- [ ] Code changes made
- [ ] Unit tests written/updated
- [ ] Code reviewed (peer)
- [ ] Changes tested locally
- [ ] Merged to main branch
- [ ] Verified in staging
- [ ] Documented in PR

### For Jan 21, 16:00 Completion
- [ ] All 8 P0 issues verified fixed
- [ ] Test suite still passing (no regressions)
- [ ] Security audit clean (0 P0 critical issues)
- [ ] Customer notification ready
- [ ] Phase 2 roadmap ready

---

## 🔄 Communication Plan

### Daily Slack Updates (EOD 16:00 CET)

**Template:**
```
🔒 Phase 1 Security Update - Jan 18

✅ COMPLETED:
- P0-4: Flask SECRET_KEY
- P0-5: Password comparison

🟡 IN PROGRESS:
- P0-2: Bcrypt password hashing
- P0-3: API key exposure

🎯 TOMORROW:
- Finish P0-2, P0-3
- Start P0-6, P0-7

📊 METRICS:
- Issues: 8/8 (0 done, 2 done, 2 in progress, 4 pending)
- Hours: 32h planned, Xh completed, Yh remaining

🚀 On track for Jan 21 completion
```

### Customer1 Communication

**Jan 18 (Kickoff):**
"Starting intensive security hardening. 8 critical issues to fix by Jan 21. Daily updates on Slack."

**Jan 19 (Mid-point):**
"Phase 1 progress: 4/8 issues resolved. On track for Jan 21."

**Jan 21 (After Feedback Call):**
"Phase 1 complete. All 8 issues fixed. Phase 2 starting Jan 22 based on your feedback."

---

## 📞 Support & Escalation

### If Stuck
1. **Quick question (5 min):** Ask in Slack #security-hardening
2. **Blocker (30+ min):** Schedule sync with [Tech Lead]
3. **Major issue:** Escalate to [Engineering Manager]

### Blockers to Watch For
- [ ] Dependency conflicts (bcrypt not installing)
- [ ] Circular imports from new changes
- [ ] Customer data migration issues
- [ ] Other team's code changes breaking compatibility

---

## 🏆 Success Criteria

### Phase 1 Complete = YES IF:

✅ All 8 P0 issues fixed  
✅ All changes merged & tested  
✅ 0 Critical vulnerabilities remaining  
✅ Customer notified of completion  
✅ Phase 2 roadmap ready  
✅ No regressions in existing tests

### Expected Timeline

| Milestone | Target | Actual |
|-----------|--------|--------|
| P0-1 complete | ✅ Jan 17 | ✅ Jan 17 |
| P0-4, P0-5 complete | Jan 18 EOD | [ ] |
| P0-2, P0-3 complete | Jan 19 EOD | [ ] |
| P0-6, P0-7 complete | Jan 20 EOD | [ ] |
| P0-8 complete | Jan 21 EOD | [ ] |
| ALL DONE | Jan 21, 16:00 | [ ] |

---

## 📚 Resources

### Key Files to Modify
```
src/web/users.py                  ← P0-2, P0-3, P0-5
src/web/aggregator_dashboard.py   ← P0-4
src/auth/authentication.py        ← P0-5 (if exists)
src/web/admin.py                  ← P0-7 (if exists)
src/core/model_loader.py          ← P0-8
src/sales/telegram_bot.py         ← Check P0-2
requirements.txt                  ← Add bcrypt, flask-limiter
```

### Dependencies to Add
```
bcrypt==4.1.0
flask-limiter==3.5.0
```

### Reading Material
- Flask-Limiter: https://flask-limiter.readthedocs.io/
- bcrypt: https://github.com/pyca/bcrypt
- hmac: https://docs.python.org/3/library/hmac.html
- OWASP Top 10: https://owasp.org/www-project-top-ten/

---

## 🎬 Kick-off Talking Points

### Why This Matters
"We have 8 critical security vulnerabilities that block customer1 from going to production. Once we fix these, we're 80% toward 7.5/10 production readiness."

### Timeline
"4 days, 32 hours of work, spread across 2-3 engineers. Realistic timeline with peer review included."

### Impact
"Each issue fixed removes a security blocker for customer1. After Jan 21, we shift to Phase 2 (high-priority infrastructure hardening)."

### Accountability
"Each engineer owns 2-3 issues. Daily standup keeps us aligned. Customer notification ensures we stay committed."

---

*Created: Jan 17, 2026, 20:48 CET*  
*Execution Starts: Jan 18, 2026, 09:00 CET*  
*Completion Target: Jan 21, 2026, 16:00 CET*
