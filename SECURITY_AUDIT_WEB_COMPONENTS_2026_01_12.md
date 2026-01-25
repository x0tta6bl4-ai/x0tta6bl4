# Security Audit: Web Components & stripe_integration_backend.py
**Date:** 2026-01-12  
**Severity:** 🔴 **CRITICAL** — Immediate Action Required  
**Status:** In Progress  

---

## Executive Summary

A comprehensive security audit of web components and Stripe integration backend revealed **multiple critical vulnerabilities** that pose immediate risks to user data and system security:

1. **CRITICAL:** MD5 password hashing (cryptographically broken)
2. **CRITICAL:** No input validation/SQL injection risk
3. **HIGH:** CORS misconfiguration (`allow_origins=["*"]`)
4. **HIGH:** Missing rate limiting
5. **MEDIUM:** Hardcoded secrets risk

**Recommendation:** Immediate remediation required before production deployment.

---

## Vulnerabilities Discovered

### 1. 🔴 CRITICAL: MD5 Password Hashing

**File:** `/web/test/resetpass.php` (Line 35)  
**Issue:** Uses MD5 for password hashing — cryptographically broken since 2004.

```php
$password = md5($cpass);  // ❌ VULNERABLE
```

**Impact:**
- MD5 is precomputed: rainbow tables readily available
- Collisions possible: multiple inputs hash to same value
- No salt used: identical passwords produce identical hashes
- **Risk:** Account takeover via brute force (~milliseconds per hash)

**Fix:** Implement bcrypt with proper salt and work factor

```php
$password = password_hash($cpass, PASSWORD_BCRYPT, ['cost' => 12]);
// Verification:
password_verify($input_password, $password);
```

---

### 2. 🔴 CRITICAL: SQL Injection Risk

**Files:** 
- `/web/test/resetpass.php` (Lines 11-16)
- `/web/test/verify.php` (Line 18)

**Issue:** Base64-decoded user input used directly in SQL queries without proper validation

```php
$id = base64_decode($_GET['id']);  // ❌ Decoded but not validated
$code = $_GET['code'];              // ❌ No sanitization

$stmt = $user->runQuery("SELECT * FROM tbl_users WHERE userID=:uid AND tokenCode=:token");
$stmt->execute(array(":uid"=>$id,":token"=>$code));  // Parameterized (good), but no validation (bad)
```

**Impact:**
- Even with prepared statements, attacker can enumerate user IDs
- No rate limiting = unlimited brute force attempts on tokens
- Base64 is encoding, not encryption: `id=base64_encode(123)` easily reversible

**Fix:**
- Validate token format (length, character set)
- Implement rate limiting (max 5 attempts per token per hour)
- Use cryptographically random tokens (32+ bytes)
- Add token expiration (15-60 minutes)

```php
// Token format validation
if (!preg_match('/^[a-f0-9]{64}$/', $code)) {
    http_response_code(400);
    exit('Invalid token format');
}

// Rate limiting check
// if (check_rate_limit($id, 'password_reset')) { die('Too many attempts'); }

// Token expiration check
$stmt = $user->runQuery(
    "SELECT * FROM tbl_users 
     WHERE userID=:uid AND tokenCode=:token 
     AND tokenExpiry > NOW() LIMIT 1"
);
```

---

### 3. 🔴 CRITICAL: Missing CSRF Protection

**File:** `/web/test/resetpass.php`  
**Issue:** No CSRF token validation on POST requests

```php
if(isset($_POST['btn-reset-pass'])) {
    // ❌ No CSRF token check
    $pass = $_POST['pass'];
    // ...
}
```

**Impact:**
- Attacker can craft malicious page that resets victims' passwords
- Works silently: victim doesn't need to interact

**Fix:** Implement CSRF token validation

```php
session_start();

// Generate token if not exists
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

// Validate on POST
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (empty($_POST['csrf_token']) || $_POST['csrf_token'] !== $_SESSION['csrf_token']) {
        http_response_code(403);
        exit('CSRF token validation failed');
    }
}

// Include in form
echo '<input type="hidden" name="csrf_token" value="' . htmlspecialchars($_SESSION['csrf_token']) . '">';
```

---

### 4. 🟠 HIGH: CORS Misconfiguration

**File:** `/stripe_integration_backend.py` (Lines 30-36)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # ❌ INSECURE: Allows ANY origin
    allow_credentials=True,     # ❌ Combined with *, bypasses CORS
    allow_methods=["*"],        # ❌ Allows all HTTP methods
    allow_headers=["*"],        # ❌ Allows all headers
)
```

**Impact:**
- Any attacker domain can make authenticated requests
- Credentials (cookies, tokens) sent with cross-origin requests
- **Risk:** Session hijacking, unauthorized API calls

**Fix:** Whitelist specific origins

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.x0tta6bl4.com",
        "https://demo.x0tta6bl4.com",
    ],  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # Cache preflight
)
```

---

### 5. 🟠 HIGH: Missing Rate Limiting

**File:** `/stripe_integration_backend.py`  
**Issue:** No protection against brute force or DDoS attacks

```python
@app.post("/create-checkout-session")
async def create_checkout_session(price_id: str = "price_12345"):
    # ❌ No rate limiting
    try:
        checkout_session = stripe.checkout.Session.create(...)
```

**Impact:**
- Attacker can spam checkout sessions (cost injection)
- Brute force price IDs to enumerate products
- Email signup endpoint unprotected (spam)

**Fix:** Implement rate limiting via `slowapi` (already in dependencies)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/create-checkout-session")
@limiter.limit("5/minute")
async def create_checkout_session(request: Request, price_id: str = "price_12345"):
    # Limited to 5 requests per minute per IP
    ...

@app.post("/signup/email")
@limiter.limit("3/hour")
async def email_signup(email: str = Body(..., embed=True)):
    # Limited to 3 signups per hour per IP
    ...
```

---

### 6. 🟡 MEDIUM: Hardcoded Secrets Risk

**File:** `/stripe_integration_backend.py` (Lines 14-20)

```python
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

if not STRIPE_SECRET_KEY:
    raise ValueError("STRIPE_SECRET_KEY environment variable not set.")
```

**Status:** ✅ CORRECT (uses env vars, not hardcoded)  
**Improvement:** Add vault integration for secret rotation

```python
from src.security.vault_client import get_secret

STRIPE_SECRET_KEY = get_secret("stripe/secret-key")  # Auto-rotated
```

---

### 7. 🟡 MEDIUM: Missing Input Sanitization

**Files:** 
- `/web/test/resetpass.php` - Email not validated
- `/stripe_integration_backend.py` - `email` parameter unvalidated

**Impact:**
- XSS injection in email signup responses
- Invalid data stored in database

**Fix:**

```python
from pydantic import EmailStr

@app.post("/signup/email")
@limiter.limit("3/hour")
async def email_signup(email: EmailStr = Body(..., embed=True)):
    # Pydantic validates email format automatically
    print(f"INFO: Received signup email: {email}")
    # Save to database/email service
    return {"message": "Email received successfully!", "email": email}
```

---

### 8. 🟡 MEDIUM: Insufficient Error Handling

**File:** `/stripe_integration_backend.py` (Lines 97-100)

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    # ❌ Exposes internal error details to client
```

**Impact:**
- Information disclosure (stack traces, internal logic)
- Helps attackers craft targeted exploits

**Fix:**

```python
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    logger.exception("Checkout session creation failed")  # Log internally
    raise HTTPException(
        status_code=500, 
        detail="Internal server error"  # Generic message to client
    )
```

---

## Remediation Plan (Priority Order)

| Priority | Task | File(s) | Effort | Timeline |
|----------|------|---------|--------|----------|
| 🔴 P0 | Replace MD5 with bcrypt | `/web/test/resetpass.php` | 2 hours | TODAY |
| 🔴 P0 | Add token validation & rate limiting | `/web/test/*.php` | 3 hours | TODAY |
| 🔴 P0 | Add CSRF protection | `/web/test/*.php` | 2 hours | TODAY |
| 🟠 P1 | Fix CORS configuration | `/stripe_integration_backend.py` | 1 hour | TODAY |
| 🟠 P1 | Implement rate limiting | `/stripe_integration_backend.py` | 2 hours | TODAY |
| 🟠 P1 | Input validation (EmailStr) | `/stripe_integration_backend.py` | 1 hour | TODAY |
| 🟡 P2 | Improve error handling | `/stripe_integration_backend.py` | 1 hour | TODAY |
| 🟡 P2 | Add security headers | All endpoints | 1 hour | TODAY |
| 🟡 P3 | Implement secret rotation | Environment setup | 2 hours | This week |
| 🟡 P3 | Add comprehensive logging | All endpoints | 2 hours | This week |

**Total Remediation Time:** ~17 hours  
**Critical Issues (blocks production):** 3  
**High Priority Issues:** 2  

---

## Testing Recommendations

### Unit Tests
```python
# Test bcrypt password hashing
def test_password_hash():
    password = "SecurePassword123!"
    hashed = password_hash(password, PASSWORD_BCRYPT)
    assert password_verify(password, hashed)
    assert not password_verify("WrongPassword", hashed)
    
# Test rate limiting
def test_rate_limit_checkout():
    for i in range(6):
        response = client.post("/create-checkout-session", params={"price_id": "p_123"})
        if i < 5:
            assert response.status_code == 200
        else:
            assert response.status_code == 429  # Too Many Requests
```

### Security Tests
```python
# Test CSRF protection
def test_csrf_protection():
    response = client.post("/reset-password", data={"pass": "new", "confirm-pass": "new"})
    assert response.status_code == 403  # CSRF token required

# Test CORS enforcement
def test_cors_enforcement():
    response = client.options(
        "/create-checkout-session",
        headers={"Origin": "https://evil.com"}
    )
    assert "evil.com" not in response.headers.get("Access-Control-Allow-Origin", "")
```

---

## Compliance Notes

### Standards Affected
- ✅ **OWASP Top 10 2021:** Fixes A03:2021 (Injection), A07:2021 (XSS), A01:2021 (Broken Access Control)
- ✅ **PCI DSS:** Fixes password requirements (Requirement 8.2)
- ✅ **GDPR:** Improves data protection via rate limiting & input validation

---

## Next Steps

1. **Immediately (Today):** 
   - [ ] Replace MD5 with bcrypt in resetpass.php
   - [ ] Add token validation & expiration
   - [ ] Fix CORS configuration

2. **This Week:**
   - [ ] Implement rate limiting on all endpoints
   - [ ] Add CSRF protection to all forms
   - [ ] Complete input validation

3. **Next Sprint:**
   - [ ] Migrate all PHP to modern Python/FastAPI (deprecate legacy code)
   - [ ] Comprehensive security testing (SAST, DAST)
   - [ ] Third-party penetration testing

---

**Report Generated:** 2026-01-12  
**Auditor:** Copilot Security Team  
**Status:** 🚨 CRITICAL - Awaiting Remediation
