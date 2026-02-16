"""Compatibility shim for moved src.network modules."""
from __future__ import annotations

from pathlib import Path

# Extend package search path to libx0t/network so imports like src.network.mesh_router keep working.
_ALT = Path(__file__).resolve().parents[2] / 'libx0t' / 'network'
if _ALT.exists():
    __path__.append(str(_ALT))
