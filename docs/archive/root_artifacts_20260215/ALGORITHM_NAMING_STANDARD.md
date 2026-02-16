# Algorithm Naming Standard

**Date:** December 30, 2025  
**Status:** ✅ **STANDARDIZED**

---

## NIST Standard Names (Primary)

x0tta6bl4 uses **NIST FIPS 203/204 standard names** as primary:

### Key Encapsulation (FIPS 203 - ML-KEM)
- **ML-KEM-512** (NIST Level 1) - default for low-security
- **ML-KEM-768** (NIST Level 3) - **default, recommended** ✅
- **ML-KEM-1024** (NIST Level 5) - default for high-security

### Digital Signatures (FIPS 204 - ML-DSA)
- **ML-DSA-44** (NIST Level 2) - default for low-security
- **ML-DSA-65** (NIST Level 3) - **default, recommended** ✅
- **ML-DSA-87** (NIST Level 5) - default for high-security

---

## Legacy Name Support (Backward Compatibility)

For backward compatibility, legacy names are automatically mapped to NIST names:

### Legacy → NIST Mapping

**KEM Algorithms:**
- `Kyber512` → `ML-KEM-512`
- `Kyber768` → `ML-KEM-768`
- `Kyber1024` → `ML-KEM-1024`

**Signature Algorithms:**
- `Dilithium2` → `ML-DSA-44`
- `Dilithium3` → `ML-DSA-65`
- `Dilithium5` → `ML-DSA-87`

---

## Implementation Details

### Automatic Mapping

All PQC adapters automatically map legacy names to NIST names:

```python
# Both work identically:
backend = LibOQSBackend(kem_algorithm="ML-KEM-768")  # ✅ Preferred
backend = LibOQSBackend(kem_algorithm="Kyber768")     # ✅ Legacy (auto-mapped)
```

### Default Values

All default algorithm parameters use NIST names:
- `PQCAdapter`: `kem_alg="ML-KEM-768"`, `sig_alg="ML-DSA-65"`
- `LibOQSBackend`: `kem_algorithm="ML-KEM-768"`, `sig_algorithm="ML-DSA-65"`
- `PQMeshSecurityLibOQS`: `kem_algorithm="ML-KEM-768"`, `sig_algorithm="ML-DSA-65"`

---

## Files Updated

### Core Files:
- ✅ `src/security/pqc/pqc_adapter.py` - Defaults updated, legacy mapping added
- ✅ `src/security/post_quantum_liboqs.py` - Defaults updated, legacy mapping added
- ✅ `src/network/pqc_tunnel.py` - Default updated, fallback added
- ✅ `src/security/pqc/key_rotation.py` - Defaults updated, legacy mapping added
- ✅ `src/security/pqc/hybrid_tls.py` - Default updated
- ✅ `src/network/mesh_router.py` - Log message updated
- ✅ `src/network/byzantine/signed_gossip.py` - NIST name with legacy fallback
- ✅ `src/core/app_minimal_with_pqc_beacons.py` - NIST name with legacy fallback

---

## Migration Guide

### For New Code:
**Always use NIST names:**
```python
# ✅ Correct
backend = LibOQSBackend(kem_algorithm="ML-KEM-768", sig_algorithm="ML-DSA-65")
```

### For Existing Code:
**Legacy names still work (auto-mapped):**
```python
# ✅ Still works (backward compatible)
backend = LibOQSBackend(kem_algorithm="Kyber768", sig_algorithm="Dilithium3")
```

### Recommended:
**Update to NIST names when possible:**
```python
# Before:
backend = LibOQSBackend(kem_algorithm="Kyber768")

# After:
backend = LibOQSBackend(kem_algorithm="ML-KEM-768")  # More explicit, future-proof
```

---

## Benefits

1. **Compliance**: Uses official NIST FIPS 203/204 names
2. **Future-proof**: Aligned with standard terminology
3. **Backward compatible**: Legacy names still work
4. **Clear documentation**: NIST names are self-documenting

---

*Standardized: December 30, 2025*

