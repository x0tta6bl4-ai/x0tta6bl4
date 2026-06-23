"""
Network Module.

Provides networking components for mesh infrastructure:
- Resilience: Make-Never-Break path management with trust scores
- PQC: Post-quantum cryptography for secure tunnels
"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

# Extend package search path to libx0t/network so imports like src.network.mesh_router keep working.
_ALT = Path(__file__).resolve().parents[2] / 'libx0t' / 'network'
if _ALT.exists():
    __path__.append(str(_ALT))

_LAZY_SUBMODULES = frozenset({"firstparty_vpn"})

from .resilience import (
    # Core resilience
    MakeNeverBreakEngine,
    NetworkPath,
    PathMetrics,
    PathState,
    PathType,
    ResilienceConfig,
    # Trust integration
    TrustAwareMAPEK,
    TrustEvent,
    TrustPolicy,
    # WAN Overlay with PQC
    CryptoMode,
    TunnelState,
    PQCKeyPair,
    ClassicalKeyPair,
    HybridKeyBundle,
    TunnelConfig,
    TunnelSession,
    WANOverlayPQC,
)

__all__ = [
    # Core resilience
    "MakeNeverBreakEngine",
    "NetworkPath",
    "PathMetrics",
    "PathState",
    "PathType",
    "ResilienceConfig",
    # Trust integration
    "TrustAwareMAPEK",
    "TrustEvent",
    "TrustPolicy",
    # WAN Overlay with PQC
    "CryptoMode",
    "TunnelState",
    "PQCKeyPair",
    "ClassicalKeyPair",
    "HybridKeyBundle",
    "TunnelConfig",
    "TunnelSession",
    "WANOverlayPQC",
    "firstparty_vpn",
]


def __getattr__(name: str) -> ModuleType:
    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_SUBMODULES)
