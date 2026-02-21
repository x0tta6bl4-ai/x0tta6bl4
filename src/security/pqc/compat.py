"""
Backward-Compatibility Bridge for Legacy PQC API.

Provides access to the legacy API from src.libx0t.security for smooth migration.

DEPRECATED: All new code should use src.security.pqc directly:

    # NEW (recommended)
    from src.security.pqc import PQCAdapter, PQCKeyExchange, HybridKeyExchange

    # LEGACY (still works, will warn in future)
    from src.security.pqc import LibOQSBackend, HybridPQEncryption, LIBOQS_AVAILABLE

Migration guide:
    LibOQSBackend       → PQCAdapter  (kem_alg=..., sig_alg=...)
    HybridPQEncryption  → HybridKeyExchange
    PQMeshSecurityLibOQS→ src.security.pqc.mesh.PQMeshNodeSecurity (future)
    LIBOQS_AVAILABLE    → is_liboqs_available()
    PQAlgorithm         → PQCAlgorithm
    PQKeyPair           → PQCKeyPair
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy classes from src.libx0t.security.post_quantum
# ---------------------------------------------------------------------------
try:
    from src.libx0t.security.post_quantum import (  # noqa: F401
        LIBOQS_AVAILABLE,
        LibOQSBackend,
        HybridPQEncryption,
        PQAlgorithm,
        PQKeyPair,
        PQCiphertext,
        PQMeshSecurityLibOQS,
    )
    _LEGACY_POST_QUANTUM_AVAILABLE = True
except ImportError as _e:  # pragma: no cover
    logger.debug("Legacy post_quantum classes unavailable: %s", _e)
    _LEGACY_POST_QUANTUM_AVAILABLE = False
    # Provide safe placeholders so import of this module never hard-fails
    LIBOQS_AVAILABLE = False
    LibOQSBackend = None  # type: ignore[assignment,misc]
    HybridPQEncryption = None  # type: ignore[assignment,misc]
    PQAlgorithm = None  # type: ignore[assignment,misc]
    PQKeyPair = None  # type: ignore[assignment,misc]
    PQCiphertext = None  # type: ignore[assignment,misc]
    PQMeshSecurityLibOQS = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Legacy helpers from src.libx0t.security.pqc_core
# ---------------------------------------------------------------------------
try:
    from src.libx0t.security.pqc_core import (  # noqa: F401
        PQCHybridScheme,
        get_pqc_key_exchange,
        get_pqc_digital_signature,
        get_pqc_hybrid,
        test_pqc_availability,
    )
    _LEGACY_PQC_CORE_AVAILABLE = True
except ImportError as _e:  # pragma: no cover
    logger.debug("Legacy pqc_core helpers unavailable: %s", _e)
    _LEGACY_PQC_CORE_AVAILABLE = False
    PQCHybridScheme = None  # type: ignore[assignment,misc]

    def get_pqc_key_exchange():  # type: ignore[misc]
        raise RuntimeError("pqc_core not available")

    def get_pqc_digital_signature():  # type: ignore[misc]
        raise RuntimeError("pqc_core not available")

    def get_pqc_hybrid():  # type: ignore[misc]
        raise RuntimeError("pqc_core not available")

    def test_pqc_availability():  # type: ignore[misc]
        return {"status": "unavailable", "reason": "libx0t pqc_core missing"}


__all__ = [
    # Availability flag
    "LIBOQS_AVAILABLE",
    # Legacy mesh-level classes
    "LibOQSBackend",
    "HybridPQEncryption",
    "PQMeshSecurityLibOQS",
    # Legacy types
    "PQAlgorithm",
    "PQKeyPair",
    "PQCiphertext",
    # Legacy helpers
    "PQCHybridScheme",
    "get_pqc_key_exchange",
    "get_pqc_digital_signature",
    "get_pqc_hybrid",
    "test_pqc_availability",
]
