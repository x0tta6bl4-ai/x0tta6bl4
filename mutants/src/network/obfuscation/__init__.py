"""
Obfuscation Module Init.
"""
from .base import TransportManager, ObfuscationTransport
from .simple import SimpleXORTransport
from .faketls import FakeTLSTransport
from .shadowsocks import ShadowsocksTransport
from .domain_fronting import DomainFrontingTransport
from .traffic_shaping import TrafficShaper, TrafficProfile, TrafficAnalyzer, TRAFFIC_PROFILES

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
