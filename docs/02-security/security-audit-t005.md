# T005 Security Audit Report: libx0t/
**Agent**: agent-2 (claude-code-session-main)
**Date**: 2026-02-15
**Scope**: 143 Python files, 51,635 LOC in /mnt/projects/libx0t/
**Status**: COMPLETE

---

## EXECUTIVE SUMMARY

libx0t/ is a refactored extraction of core/network modules from src/. The library provides post-quantum mesh networking with obfuscation, Byzantine fault tolerance, and VPN leak protection.

**Overall assessment**: Production-grade infrastructure code with **good security posture** but several issues requiring attention.

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 4 | Action required |
| HIGH | 5 | Fix this sprint |
| MEDIUM | 6 | Backlog |
| LOW | 3 | Informational |

---

## CRITICAL FINDINGS

### C1. SSL/TLS verification completely disabled
**File**: `libx0t/network/obfuscation/domain_fronting.py:121-122`
```python
self.context.check_hostname = False
self.context.verify_mode = ssl.CERT_NONE  # MITM vulnerable
```
**Fix**: Use `CERT_REQUIRED` with custom CA bundle. Hostname check can be off for fronting, but cert chain MUST be validated.

### C2. PQC stub returns hardcoded dummy keys
**File**: `libx0t/crypto/pqc.py:24-44`
```python
def generate_keypair(self):
    if self.liboqs_available:
        return b"real_pub", b"real_priv"  # TODO: not implemented!
    return b"sim_pub", b"sim_priv"       # identical across ALL instances
```
**Impact**: Every node gets the same "keys". Even the liboqs=True branch is unimplemented.
**Fix**: Implement real liboqs KEM calls or raise NotImplementedError. Never return static bytes.

### C3. tunnel.py "encryption" is plaintext wrapping
**File**: `libx0t/network/tunnel.py:56-67`
```python
encrypted_data = b"ENC[" + data + b"]"  # Not encryption at all
```
**Fix**: Use `pqc_tunnel.py` (which has real AES-256-GCM) or remove the fake encryption code entirely.

### C4. FakeTLS/Shadowsocks/DomainFronting socket.socket subclass bug
**Files**: `libx0t/network/obfuscation/faketls.py:28`, `shadowsocks.py`, `domain_fronting.py`
```python
self.timeout = sock.gettimeout()  # timeout is read-only C descriptor!
```
**Impact**: Silent failure. Timeout behavior undefined. Potential deadlocks.
**Fix**: Use composition instead of subclassing socket.socket. Store timeout in `_timeout` attribute.

---

## HIGH FINDINGS

### H1. Empty default for JWT secret
**File**: `libx0t/network/proxy_auth_middleware.py:206`
```python
self.secret = secret or os.environ.get("PROXY_JWT_SECRET", "")
```
**Fix**: Raise ValueError if PROXY_JWT_SECRET is unset. Empty string = no auth.

### H2. PQC tunnel fallback uses XOR + SHA256 (no AEAD)
**File**: `libx0t/network/pqc_tunnel.py:74-77,114-120`
When liboqs is unavailable, falls back to `XOR(data, SHA256(key))`. No authentication.
**Fix**: Use AES-256-GCM from `cryptography` library as fallback (already a dependency).

### H3. No replay protection in socket wrappers
**Files**: `libx0t/network/obfuscation/shadowsocks.py`, `faketls.py`
No sequence numbers, nonces, or MACs on wrapped packets.
**Fix**: Add per-session nonce counter and HMAC.

### H4. Discovery protocol trusts untrusted JSON
**File**: `libx0t/network/discovery/protocol.py:287`
```python
obj = json.loads(data.decode("utf-8"))  # No schema validation
```
**Fix**: Validate JSON schema before constructing DiscoveryMessage. Handle KeyError/ValueError.

### H5. Gossip rate limit too lenient
**File**: `libx0t/network/byzantine/signed_gossip.py:206-214`
10 msg/sec per sender — easy to flood.
**Fix**: Reduce to 2 msg/sec with token bucket.

---

## MEDIUM FINDINGS

### M1. Demo secrets in logging config
**File**: `libx0t/core/logging_config.py:315-316`
`Password=secret123` and `token=abc123def456` used as test strings.
**Fix**: Guard behind `if __name__ == "__main__"`.

### M2. 0.0.0.0 bind addresses (acknowledged)
Multiple files use `host="0.0.0.0"` with `# nosec B104` comments. Acceptable for server processes but ensure firewalls are configured.

### M3. Inconsistent SSL context creation
Multiple files create SSL contexts with different security policies.
**Fix**: Create a shared `create_secure_ssl_context()` utility.

### M4. Credentials could leak in exception tracebacks
**File**: `libx0t/network/residential_proxy_manager.py`
`proxy.to_url()` includes username:password. If exception propagates, credentials appear in logs.
**Fix**: Override `__repr__` on ProxyEndpoint to mask credentials.

### M5. X-Forwarded-For IP spoofing in rate limiter
**File**: `libx0t/core/rate_limit_middleware.py:239-242`
```python
forwarded = request.headers.get("X-Forwarded-For")
if forwarded:
    return forwarded.split(",")[0].strip()  # Trusts client header
```
**Fix**: Only trust X-Forwarded-For behind known reverse proxies.

### M6. Unused `import os` in crypto/pqc.py
Minor but indicates incomplete implementation.

---

## LOW FINDINGS

### L1. Yggdrasil mock uses `random` instead of `secrets`
**File**: `libx0t/network/yggdrasil_client.py` — acceptable for mock/dev code.

### L2. No socket timeout on tunnel.py connect()
**File**: `libx0t/network/tunnel.py:21-26` — blocking connect without timeout.

### L3. `x0t/` directory is empty
`libx0t/x0t/` exists but contains no files. Should be removed or populated.

---

## POSITIVE FINDINGS (What's done right)

| Area | Assessment |
|------|-----------|
| No hardcoded production secrets | PASS - all secrets from env vars |
| No SQL injection vectors | PASS - 0 matches |
| No `pickle.loads` / `eval` / `exec` | PASS - clean |
| No insecure `random` for crypto | PASS - uses `secrets` module |
| SafeSubprocess with command whitelist | EXCELLENT |
| Request validation middleware | EXCELLENT - SQL/XSS/injection patterns |
| Log redaction patterns | GOOD - masks passwords/tokens/keys |
| Shadowsocks uses ChaCha20-Poly1305 | GOOD - proper AEAD |
| pqc_tunnel.py uses AES-256-GCM | GOOD - NIST FIPS 203 compliant |
| Byzantine quorum validation | GOOD - 67% threshold |

---

## RECOMMENDED ACTION PLAN

| Priority | Issue | Owner | Estimate |
|----------|-------|-------|----------|
| P0 | C1: Fix domain_fronting SSL | agent-2 | 30min |
| P0 | C2: Implement real PQC in crypto/pqc.py | agent-2 | 2h |
| P0 | C3: Replace tunnel.py fake encryption | agent-1 | 1h |
| P0 | C4: Fix socket subclass timeout | agent-3 | 1h |
| P1 | H1: Require JWT secret | agent-2 | 15min |
| P1 | H2: PQC tunnel fallback → AES-GCM | agent-2 | 1h |
| P1 | H3: Add replay protection | agent-3 | 2h |
| P1 | H4: Validate discovery JSON | agent-3 | 1h |
| P1 | H5: Tighten gossip rate limit | agent-3 | 30min |
| P2 | M1-M6: Medium issues | mixed | backlog |

---

## FILES AUDITED

```
libx0t/__init__.py                           ✅ clean
libx0t/core/ (47 files, ~18K LOC)           ⚠️ M1, M5
libx0t/crypto/ (2 files, 50 LOC)            🔴 C2
libx0t/network/ (94 files, ~33K LOC)        🔴 C1, C3, C4; ⚠️ H1-H5
libx0t/examples/ (1 file)                    ✅ demo only
libx0t/x0t/ (empty)                          ℹ️ L3
```
