"""
Network Module.

Provides networking components for mesh infrastructure:
- Resilience: Make-Never-Break path management with trust scores
- PQC: Post-quantum cryptography for secure tunnels
"""
from __future__ import annotations

from pathlib import Path

# Extend package search path to libx0t/network so imports like src.network.mesh_router keep working.
_ALT = Path(__file__).resolve().parents[2] / 'libx0t' / 'network'
if _ALT.exists():
    __path__.append(str(_ALT))

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
]
