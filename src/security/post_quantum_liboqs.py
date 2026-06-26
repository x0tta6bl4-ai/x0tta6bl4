"""
Deprecated compatibility shim for legacy liboqs PQC imports.

New code should import from ``src.security.pqc``.  This module stays importable
because production checks, fixtures, and older integrations still reference
``src.security.post_quantum_liboqs``.
"""
from __future__ import annotations

from src.security.pqc import *  # noqa: F401,F403

