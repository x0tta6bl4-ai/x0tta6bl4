"""
Obfuscation Module Init.
"""

from .base import ObfuscationTransport, TransportManager
from .domain_fronting import DomainFrontingTransport
from .faketls import FakeTLSTransport
from .shadowsocks import ShadowsocksTransport
from .simple import SimpleXORTransport
from .traffic_shaping import (TRAFFIC_PROFILES, TrafficAnalyzer,
                              TrafficProfile, TrafficShaper)

# Register default transports
TransportManager.register("xor", SimpleXORTransport)
TransportManager.register("faketls", FakeTLSTransport)
TransportManager.register("shadowsocks", ShadowsocksTransport)
TransportManager.register("domain_fronting", DomainFrontingTransport)

__all__ = [
    "TransportManager",
    "ObfuscationTransport",
    "SimpleXORTransport",
    "FakeTLSTransport",
    "ShadowsocksTransport",
    "DomainFrontingTransport",
    "TrafficShaper",
    "TrafficProfile",
    "TrafficAnalyzer",
    "TRAFFIC_PROFILES",
]
