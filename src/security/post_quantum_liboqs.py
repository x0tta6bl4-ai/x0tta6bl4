"""
DEPRECATED shim. Use src.security.pqc instead.

    # Old
    from src.security.post_quantum_liboqs import LIBOQS_AVAILABLE, LibOQSBackend
    # New
    from src.security.pqc import LIBOQS_AVAILABLE, LibOQSBackend
"""
from src.security.pqc import (  # noqa: F401
    LIBOQS_AVAILABLE,
    LibOQSBackend,
    HybridPQEncryption,
    PQAlgorithm,
    PQKeyPair,
    PQCiphertext,
    PQMeshSecurityLibOQS,
    is_liboqs_available,
)
