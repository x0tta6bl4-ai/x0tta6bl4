"""
x0tta6bl4 Post-Quantum Cryptography Module
===========================================

CANONICAL ENTRY POINT for all PQC operations.

Provides:
- ML-KEM-768 Key Encapsulation (NIST FIPS 203)
- ML-DSA-65 Digital Signatures (NIST FIPS 204)
- Hybrid schemes (X25519+ML-KEM, Ed25519+ML-DSA)
- Backward-compatible legacy API (LibOQSBackend, HybridPQEncryption, etc.)

This module replaces all previous PQC entry points:
  src/security/post_quantum.py        → use src.security.pqc
  src/security/post_quantum_liboqs.py → use src.security.pqc
  src/security/pqc_core.py            → use src.security.pqc
  src/libx0t/security/post_quantum.py → use src.security.pqc
  src/libx0t/security/pqc_core.py     → use src.security.pqc

Usage (new API):
    from src.security.pqc import (
        PQCKeyExchange, PQCDigitalSignature,
        HybridKeyExchange, is_liboqs_available,
    )

Usage (legacy API — still supported):
    from src.security.pqc import LibOQSBackend, HybridPQEncryption, LIBOQS_AVAILABLE
"""

# Version
__version__ = "2.1.0"
__author__ = "x0tta6bl4 Team"

# ---------------------------------------------------------------------------
# New canonical API
# ---------------------------------------------------------------------------

# Availability
from .adapter import (
    is_liboqs_available,
    get_supported_kem_algorithms,
    get_supported_sig_algorithms,
    PQCAdapter,
)

# Types
from .types import (
    PQCAlgorithm,
    PQCKeyPair,
    PQCSignature,
    PQCEncapsulationResult,
)

# KEM (Key Encapsulation Mechanism)
from .kem import PQCKeyExchange

# DSA (Digital Signature Algorithm)
from .dsa import PQCDigitalSignature

# Hybrid schemes
from .hybrid import (
    HybridKeyPair,
    HybridSignature,
    HybridKeyExchange,
    HybridSignatureScheme,
)

# ---------------------------------------------------------------------------
# Backward-compatible legacy API (from compat bridge)
# ---------------------------------------------------------------------------
from .compat import (  # noqa: F401
    LIBOQS_AVAILABLE,
    LibOQSBackend,
    HybridPQEncryption,
    PQAlgorithm,
    PQKeyPair,
    PQCiphertext,
    PQMeshSecurityLibOQS,
    PQCHybridScheme,
    get_pqc_key_exchange,
    get_pqc_digital_signature,
    get_pqc_hybrid,
    test_pqc_availability,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
    # Version
    "__version__",
    # --- New canonical API ---
    # Availability
    "is_liboqs_available",
    "get_supported_kem_algorithms",
    "get_supported_sig_algorithms",
    # Adapter (raw oqs wrapper)
    "PQCAdapter",
    # Types
    "PQCAlgorithm",
    "PQCKeyPair",
    "PQCSignature",
    "PQCEncapsulationResult",
    # KEM
    "PQCKeyExchange",
    # DSA
    "PQCDigitalSignature",
    # Hybrid (new)
    "HybridKeyPair",
    "HybridSignature",
    "HybridKeyExchange",
    "HybridSignatureScheme",
    # --- Legacy API (backward-compat) ---
    "LIBOQS_AVAILABLE",
    "LibOQSBackend",
    "HybridPQEncryption",
    "PQAlgorithm",
    "PQKeyPair",
    "PQCiphertext",
    "PQMeshSecurityLibOQS",
    "PQCHybridScheme",
    "get_pqc_key_exchange",
    "get_pqc_digital_signature",
    "get_pqc_hybrid",
    "test_pqc_availability",
]
