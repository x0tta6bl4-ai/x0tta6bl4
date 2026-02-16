"""Compatibility shim for moved src.core modules."""
from __future__ import annotations

from pathlib import Path

# Extend package search path to libx0t/core so imports like src.core.app keep working.
_ALT = Path(__file__).resolve().parents[2] / 'libx0t' / 'core'
if _ALT.exists():
    __path__.append(str(_ALT))
