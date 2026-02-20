"""
DEPRECATED shim. Use src.security.pqc instead.

    # Old
    from src.security.pqc_core import PQCKeyExchange, PQCDigitalSignature
    # New
    from src.security.pqc import PQCKeyExchange, PQCDigitalSignature
"""
from src.security.pqc import (  # noqa: F401
    PQCKeyExchange,
    PQCDigitalSignature,
    PQCHybridScheme,
    PQCAdapter,
    PQCAlgorithm,
    PQCKeyPair,
    PQCSignature,
    LIBOQS_AVAILABLE,
    is_liboqs_available,
    get_pqc_key_exchange,
    get_pqc_digital_signature,
    get_pqc_hybrid,
    test_pqc_availability,
)
