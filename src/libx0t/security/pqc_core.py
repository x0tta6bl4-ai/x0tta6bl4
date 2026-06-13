"""
Deprecated compatibility shim for legacy PQC core imports.

Use ``src.security.pqc`` for new code.
"""
from __future__ import annotations

import warnings

from src.security.pqc.compat import (  # noqa: F401
    LIBOQS_AVAILABLE,
    PQCDigitalSignature,
    PQCHybridScheme,
    PQCKeyExchange,
    PQCKeyPair,
    PQCSignature,
    get_pqc_digital_signature,
    get_pqc_hybrid,
    get_pqc_key_exchange,
    test_pqc_availability,
)
from src.security.pqc import is_liboqs_available  # noqa: F401

warnings.warn(
    "Importing from " + "src.libx0t.security.pqc_core is deprecated. "
    "Use 'from src.security.pqc import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "LIBOQS_AVAILABLE",
    "PQCKeyPair",
    "PQCSignature",
    "PQCKeyExchange",
    "PQCDigitalSignature",
    "PQCHybridScheme",
    "get_pqc_key_exchange",
    "get_pqc_digital_signature",
    "get_pqc_hybrid",
    "test_pqc_availability",
    "is_liboqs_available",
]
