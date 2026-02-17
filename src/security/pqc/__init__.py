"""
x0tta6bl4 Post-Quantum Cryptography Module
===========================================

Unified PQC implementation providing:
- ML-KEM-768 Key Encapsulation (NIST FIPS 203)
- ML-DSA-65 Digital Signatures (NIST FIPS 204)
- Hybrid schemes (X25519+ML-KEM, Ed25519+ML-DSA)

This module consolidates 3 previous implementations:
- src/security/pqc_core.py
- src/crypto/pqc_crypto.py
- src/security/pqc/pqc_adapter.py

Usage:
    from src.security.pqc import (
        PQCKeyExchange,
        PQCDigitalSignature,
        HybridKeyExchange,
        HybridSignatureScheme,
        is_liboqs_available,
    )
    
    # Check availability
    if is_liboqs_available():
        # KEM
        kem = PQCKeyExchange()
        keypair = kem.generate_keypair()
        ciphertext, secret = kem.encapsulate(peer_public_key)
        
        # DSA
        dsa = PQCDigitalSignature()
        sig_keypair = dsa.generate_keypair()
        signature = dsa.sign(message, sig_keypair.secret_key)
        
        # Hybrid
        hybrid = HybridKeyExchange()
        hybrid_keypair = hybrid.generate_keypair()
"""

# Version
__version__ = "2.0.0"
__author__ = "x0tta6bl4 Team"

# Check availability
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

# Public API
__all__ = [
    # Version
    "__version__",
    # Availability
    "is_liboqs_available",
    "get_supported_kem_algorithms",
    "get_supported_sig_algorithms",
    # Adapter
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
    # Hybrid
    "HybridKeyPair",
    "HybridSignature",
    "HybridKeyExchange",
    "HybridSignatureScheme",
]
