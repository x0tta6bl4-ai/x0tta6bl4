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
from __future__ import annotations

# Version
__version__ = "2.1.0"
__author__ = "x0tta6bl4 Team"

# ---------------------------------------------------------------------------
# New canonical API
# ---------------------------------------------------------------------------

# Availability
from .adapter import (
    PQCAdapter,
    get_supported_kem_algorithms,
    get_supported_sig_algorithms,
    is_liboqs_available,
)

# ---------------------------------------------------------------------------
# Backward-compatible legacy API (from compat bridge)
# ---------------------------------------------------------------------------
from .compat import (  # noqa: F401
    HybridPQEncryption,
    LibOQSBackend,
    PQAlgorithm,
    PQCHybridScheme,
    PQCiphertext,
    PQKeyPair,
    PQMeshSecurityLibOQS,
    get_pqc_digital_signature,
    get_pqc_hybrid,
    get_pqc_key_exchange,
    test_pqc_availability,
)


def __getattr__(name: str):
    if name == "LIBOQS_AVAILABLE":
        return is_liboqs_available()
    # Lazy imports for oqs classes (used by legacy code and tests)
    if name in ("KeyEncapsulation", "Signature"):
        try:
            import oqs
            return getattr(oqs, name)
        except (ImportError, AttributeError) as e:
            raise AttributeError(f"oqs.{name} not available: {e}") from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# DSA (Digital Signature Algorithm)
from .dsa import PQCDigitalSignature

# Hybrid schemes
from .hybrid import (
    HybridKeyExchange,
    HybridKeyPair,
    HybridSignature,
    HybridSignatureScheme,
)

# KEM (Key Encapsulation Mechanism)
from .kem import PQCKeyExchange

# Simple PQC wrapper (migrated from libx0t.crypto.pqc)
from .simple import PQC

# Types
from .types import (
    PQCAlgorithm,
    PQCEncapsulationResult,
    PQCKeyPair,
    PQCSignature,
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
    # Simple wrapper (migrated from libx0t.crypto.pqc)
    "PQC",
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

