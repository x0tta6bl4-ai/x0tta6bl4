"""
Deprecated compatibility shim for legacy PQC core imports.

New code should import from ``src.security.pqc``.  This module stays importable
while runtime code and external integrations move to the canonical package.
"""
from __future__ import annotations

from src.security.pqc import *  # noqa: F401,F403

