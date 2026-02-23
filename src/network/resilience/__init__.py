"""
Network Resilience Module.

Implements Rajant-inspired "Make-Make-Make-Never-Break" principle
for zero-downtime mesh networking with Cisco-like trust scores.

Key Components:
- MakeNeverBreakEngine: Aggressive multi-path establishment
- TrustAwareMAPEK: Trust score integration with MAPE-K loop
- WANOverlayPQC: Post-quantum cryptography for WAN overlay
"""

from .make_never_break import (
    MakeNeverBreakEngine,
    NetworkPath,
    PathMetrics,
    PathState,
    PathType,
    ResilienceConfig,
)

from .trust_mapek_integration import (
    TrustAwareMAPEK,
    TrustEvent,
    TrustPolicy,
)

from .wan_overlay_pqc import (
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
