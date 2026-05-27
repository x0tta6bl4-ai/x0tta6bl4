"""
Deprecated compatibility shim for legacy PQC imports.

New code should import from ``src.security.pqc``.  This module stays importable
because deployment scripts, fixtures, and older integrations still reference
``src.security.post_quantum``.
"""

from src.security.pqc import *  # noqa: F401,F403
