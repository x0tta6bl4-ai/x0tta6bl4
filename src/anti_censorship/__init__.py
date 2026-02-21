"""
Anti-Censorship Module for x0tta6bl4 MaaS Platform
==================================================

Comprehensive censorship circumvention toolkit including:
- Domain Fronting for DNS/TLS bypass
- Multi-layer traffic obfuscation
- CDN integration for connection masking
- Pluggable transports (obfs4, meek, snowflake)
"""

from src.anti_censorship.stego_mesh import StegoMeshProtocol
from src.anti_censorship.domain_fronting import (
    DomainFrontingClient,
    CDNProvider,
    FrontingConfig,
)
from src.anti_censorship.obfuscation import (
    TrafficObfuscator,
    ObfuscationLayer,
    ObfuscationConfig,
)
from src.anti_censorship.transports import (
    PluggableTransport,
    TransportType,
    TransportConfig,
    OBFS4Transport,
    MeekTransport,
    SnowflakeTransport,
)
from src.anti_censorship.censorship_detector import (
    CensorshipDetector,
    DetectionResult,
    BlockingType,
)

__all__ = [
    # Steganographic Mesh
    "StegoMeshProtocol",
    # Domain Fronting
    "DomainFrontingClient",
    "CDNProvider",
    "FrontingConfig",
    # Obfuscation
    "TrafficObfuscator",
    "ObfuscationLayer",
    "ObfuscationConfig",
    # Pluggable Transports
    "PluggableTransport",
    "TransportType",
    "TransportConfig",
    "OBFS4Transport",
    "MeekTransport",
    "SnowflakeTransport",
    # Censorship Detection
    "CensorshipDetector",
    "DetectionResult",
    "BlockingType",
]
