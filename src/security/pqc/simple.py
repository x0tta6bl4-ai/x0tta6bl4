"""
DEPRECATED shim. Use src.security.pqc.simple instead.

    # Old
    from libx0t.crypto.pqc import PQC
    # New
    from src.security.pqc.simple import PQC

This shim is maintained for backward compatibility only.
It will be removed in a future version.
"""
import warnings

warnings.warn(
    "libx0t.crypto.pqc is deprecated. Use src.security.pqc.simple instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from canonical location
from src.security.pqc.simple import PQC  # noqa: F401

__all__ = ["PQC"]
