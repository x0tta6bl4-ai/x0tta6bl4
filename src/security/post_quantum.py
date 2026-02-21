"""
Compatibility alias. Redirects to src.libx0t.security.post_quantum.

For new code use src.security.pqc instead:
    from src.security.pqc import LibOQSBackend, HybridPQEncryption, LIBOQS_AVAILABLE
"""
import sys
from importlib import import_module

# Preserve sys.modules-level redirect so that patch('src.security.post_quantum.X')
# still works in existing tests (they patch attributes on the libx0t module via this alias).
_legacy_module = import_module("src.libx0t.security.post_quantum")
sys.modules[__name__] = _legacy_module
